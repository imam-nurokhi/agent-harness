"""GitHub write access for the harness — branch, PR to dev, merge on approval.

The owner's rule, stated 2026-09-19:

    commit+push dilakukan ke branch baru dan hanya bisa dibuatkan PR untuk
    merge ke branch dev saja, merge PR hanya bisa dilakukan jika saya approved
    by telegrambot

So three gates, each enforced here and each tested:

1. **Push only to a fresh, namespaced branch.** Agents never push to an
   existing shared branch. Branch names are minted here (`ah/<task>-<stamp>`)
   so an agent cannot choose `dev` and cannot collide with a human's branch.
2. **A pull request may target `dev` and nothing else.** main/master/staging/
   production are refused by name, and anything that is not literally `dev` is
   refused by default -- an allowlist, not a blocklist, so a new protected
   branch tomorrow is safe without a code change.
3. **A merge needs an approval recorded by the Telegram button.** `merge()`
   will not call GitHub without an approval file written by the owner's tap;
   passing the PR number alone does nothing. The approval names the exact
   repo, PR number and head SHA, so an approval cannot be replayed onto a PR
   that has changed since the owner looked at it.

The token (GITHUB_PAT, see CLAUDE.md §9) is read from the environment of the
*bot*, never handed to an agent: ops/harness/claude-settings.json denies agents
both `.env` and `git push`, and the push URL is built in memory here so the
credential is never written into any repository's .git/config.

Defence in depth: ops/harness/protect.sh independently blocks a push to
main/master/production/prod in every onboarded repo, so even a bug here cannot
land work on a protected branch.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

import state

API = "https://api.github.com"

#: The owner named exactly these two GitHub owners.
ORGS = ("Nexora-Tech-Team", "NexoraTechTeam")

#: Which of them is a real organisation. Nexora-Tech-Team is a personal account
#: that happens to be named like an org; NexoraTechTeam is the organisation.
#: Measured 2026-09-19: GITHUB_PAT can write to the personal repos but gets
#: 403 "Resource not accessible by personal access token" on the org's, while
#: GITHUB_ORGS_PAT is the reverse. A fine-grained PAT serves one owner, so the
#: split is structural, not a misconfiguration to be tidied away later.
ORG_OWNERS = ("NexoraTechTeam",)

#: The one branch a pull request may target.
PR_BASE = "dev"

#: Never a base, never a push target, never a merge destination.
PROTECTED = ("main", "master", "production", "prod", "staging", "release")

#: Every branch the harness creates starts here, so its work is identifiable
#: at a glance in the GitHub UI and can never be confused with a human branch.
BRANCH_PREFIX = "ah/"

APPROVALS = state.AGENTS / "approvals"

_SLUG_OK = re.compile(r"[^a-z0-9._-]+")
#: Minting is stricter than validation on purpose: a task id like "../../dev"
#: survives the validation charset (dots are legal in a branch name) but would
#: produce "..-..-dev", which validate_head then refuses. Nothing we mint may
#: ever be refused by our own gate, so minting drops dots entirely.
_MINT_OK = re.compile(r"[^a-z0-9-]+")


# --------------------------------------------------------------------------
# Pure validation. No network, no filesystem -- this is the rule surface.
# --------------------------------------------------------------------------

def validate_repo(full_name: str) -> tuple:
    """(ok, reason). Only repos in the owner's two organisations."""
    name = (full_name or "").strip().strip("/")
    if not name or name.count("/") != 1:
        return False, "repo harus berbentuk <org>/<repo>"
    org, repo = name.split("/")
    if org not in ORGS:
        return False, f"refused: {org} bukan organisasi yang diizinkan ({', '.join(ORGS)})"
    if not repo or _SLUG_OK.sub("", repo.lower()) != repo.lower():
        return False, f"refused: nama repo tidak valid: {repo}"
    return True, ""


def validate_base(branch: str) -> tuple:
    """(ok, reason). A PR may target dev. Nothing else, ever."""
    name = (branch or "").strip().lower()
    if not name:
        return False, f"base branch wajib: {PR_BASE}"
    if name in PROTECTED:
        return False, f"refused: {name} dikelola owner, PR tidak boleh menargetkannya"
    if name != PR_BASE:
        return False, f"refused: PR hanya boleh ke branch {PR_BASE}"
    return True, ""


def validate_head(branch: str) -> tuple:
    """(ok, reason). Push target must be a fresh ah/ branch, never a shared one."""
    name = (branch or "").strip()
    if not name:
        return False, "branch tujuan wajib diisi"
    if name.lower() in PROTECTED or name.lower() == PR_BASE:
        return False, f"refused: {name} adalah branch bersama, agent tidak boleh push ke sana"
    if not name.startswith(BRANCH_PREFIX):
        return False, f"refused: branch agent harus diawali {BRANCH_PREFIX}"
    tail = name[len(BRANCH_PREFIX):]
    if not tail or ".." in name or name.endswith("/") or " " in name:
        return False, f"refused: nama branch tidak valid: {name}"
    return True, ""


def branch_for(task_id: str, now: float | None = None) -> str:
    """Mint the branch name for a task. Deterministic shape, unique per minute."""
    slug = _MINT_OK.sub("-", (task_id or "task").strip().lower())
    slug = re.sub(r"-{2,}", "-", slug).strip("-") or "task"
    stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime(now if now is not None else time.time()))
    return f"{BRANCH_PREFIX}{slug}-{stamp}"


# --------------------------------------------------------------------------
# Approval records. Written by the Telegram button, read by merge().
# --------------------------------------------------------------------------

def _approval_path(repo: str, number: int) -> Path:
    return APPROVALS / f"{repo.replace('/', '__')}__{int(number)}.json"


def record_approval(repo: str, number: int, head_sha: str, chat_id, approvals_dir: Path | None = None) -> dict:
    """Persist the owner's tap. Bound to the head SHA the owner was shown."""
    ok, reason = validate_repo(repo)
    if not ok:
        raise ValueError(reason)
    directory = approvals_dir or APPROVALS
    directory.mkdir(parents=True, exist_ok=True)
    rec = {
        "repo": repo,
        "number": int(number),
        "head_sha": (head_sha or "").strip(),
        "approved_by": str(chat_id),
        "approved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    path = directory / _approval_path(repo, number).name
    path.write_text(json.dumps(rec, indent=2))
    return rec


def stage_approval(repo: str, number: int, head_sha: str, chat_id,
                   approvals_dir: Path | None = None) -> str:
    """Park a merge offer behind a short token and return it.

    Telegram caps callback_data at 64 bytes, and "Nexora-Tech-Team/
    CBQAGLOBAL-CRM-BACKEND-GOLANG" alone is 45 of them, so the button carries a
    token rather than the repo name. The token also means a button cannot be
    hand-crafted by someone who merely guesses a PR number: it has to exist on
    disk, and it records which chat was offered it.
    """
    ok, reason = validate_repo(repo)
    if not ok:
        raise ValueError(reason)
    directory = approvals_dir or APPROVALS
    directory.mkdir(parents=True, exist_ok=True)
    token_ = os.urandom(5).hex()
    (directory / f"pending-{token_}.json").write_text(json.dumps({
        "token": token_, "repo": repo, "number": int(number),
        "head_sha": (head_sha or "").strip(), "offered_to": str(chat_id),
        "offered_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }, indent=2))
    return token_


def resolve_pending(token_: str, approvals_dir: Path | None = None) -> dict | None:
    """Look up a staged offer. Unknown or malformed tokens resolve to None."""
    t = (token_ or "").strip()
    if not t or not re.fullmatch(r"[0-9a-f]{4,32}", t):
        return None
    directory = approvals_dir or APPROVALS
    try:
        return json.loads((directory / f"pending-{t}.json").read_text())
    except (OSError, ValueError):
        return None


def read_approval(repo: str, number: int, approvals_dir: Path | None = None) -> dict | None:
    directory = approvals_dir or APPROVALS
    path = directory / _approval_path(repo, number).name
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def approval_matches(rec: dict | None, repo: str, number: int, head_sha: str) -> tuple:
    """(ok, reason). An approval is for one PR at one commit -- no replay."""
    if not rec:
        return False, "belum ada approval dari Telegram untuk PR ini"
    if rec.get("repo") != repo or int(rec.get("number", -1)) != int(number):
        return False, "approval tidak cocok dengan PR ini"
    approved_sha = (rec.get("head_sha") or "").strip()
    current = (head_sha or "").strip()
    if approved_sha and current and approved_sha != current:
        return False, ("PR berubah setelah di-approve "
                       f"(disetujui {approved_sha[:7]}, sekarang {current[:7]}). "
                       "Minta approval ulang.")
    return True, ""


# --------------------------------------------------------------------------
# GitHub API. `caller` is injectable so the rules can be tested offline.
# --------------------------------------------------------------------------

def token(repo: str = "") -> str:
    """The credential for this repo's owner.

    A fine-grained PAT (`github_pat_...`) belongs to exactly ONE resource
    owner, and there are two here. Sending the wrong one is not a soft failure:
    it returns 403 "Resource not accessible by personal access token", which
    reads like a broken token rather than a misrouted one. Resolution order:

        1. GITHUB_PAT_<OWNER>   -- explicit per-owner override, if ever needed
        2. GITHUB_ORGS_PAT      -- organisation repos (NexoraTechTeam)
        3. GITHUB_PAT           -- personal-account repos, and the fallback

    A single classic token with `repo` scope in GITHUB_PAT also works on its
    own, because step 3 catches everything.
    """
    owner = repo.split("/")[0] if "/" in (repo or "") else ""
    if owner:
        key = "GITHUB_PAT_" + re.sub(r"[^A-Z0-9]", "_", owner.upper())
        specific = os.environ.get(key)
        if specific and specific.strip():
            return specific.strip()
        if owner in ORG_OWNERS:
            org_token = os.environ.get("GITHUB_ORGS_PAT")
            if org_token and org_token.strip():
                return org_token.strip()
    return (os.environ.get("GITHUB_PAT") or os.environ.get("GITHUB_TOKEN") or "").strip()


def _api(method: str, path: str, payload: dict | None = None, timeout: int = 30,
         repo: str = "") -> tuple:
    """(status, body). Never raises for an HTTP error status."""
    tok = token(repo)
    if not tok:
        return 0, {"message": "GITHUB_PAT tidak ada di environment bot"}
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(f"{API}{path}", data=data, method=method)
    req.add_header("Authorization", f"Bearer {tok}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    req.add_header("User-Agent", "nexora-agent-harness")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode(errors="replace")
            return resp.status, (json.loads(body) if body else {})
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        try:
            return e.code, json.loads(body)
        except ValueError:
            return e.code, {"message": body[:400]}
    except Exception as e:  # network down, DNS, timeout
        return 0, {"message": str(e)}


def push_branch(worktree: Path, repo: str, branch: str, caller=None) -> dict:
    """Push the worktree's HEAD to a fresh branch. Credential stays in memory."""
    ok, reason = validate_repo(repo)
    if not ok:
        return {"ok": False, "error": reason}
    ok, reason = validate_head(branch)
    if not ok:
        return {"ok": False, "error": reason}
    wt = Path(worktree)
    if not (wt / ".git").exists() and not wt.is_dir():
        return {"ok": False, "error": f"worktree tidak ada: {wt}"}
    tok = token(repo)
    if not tok:
        return {"ok": False, "error": "GITHUB_PAT tidak ada di environment bot"}
    url = f"https://x-access-token:{tok}@github.com/{repo}.git"
    run = caller or (lambda args: subprocess.run(
        args, capture_output=True, text=True, timeout=300))
    # --force-with-lease is deliberately absent: the branch is new, so a
    # non-fast-forward here means someone else owns that name and we stop.
    proc = run(["git", "-C", str(wt), "push", url, f"HEAD:refs/heads/{branch}"])
    out = ((getattr(proc, "stdout", "") or "") + (getattr(proc, "stderr", "") or ""))
    out = out.replace(tok, "***")
    if getattr(proc, "returncode", 1) != 0:
        return {"ok": False, "error": out.strip()[-500:] or "git push gagal"}
    return {"ok": True, "branch": branch, "output": out.strip()[-300:]}


def open_pr(repo: str, head: str, title: str, body: str = "", base: str = PR_BASE) -> dict:
    ok, reason = validate_repo(repo)
    if not ok:
        return {"ok": False, "error": reason}
    ok, reason = validate_base(base)
    if not ok:
        return {"ok": False, "error": reason}
    ok, reason = validate_head(head)
    if not ok:
        return {"ok": False, "error": reason}
    status, data = _api("POST", f"/repos/{repo}/pulls", {
        "title": (title or head)[:250],
        "head": head,
        "base": base,
        "body": body or "Dibuat oleh agent-harness. Merge hanya setelah approval owner di Telegram.",
        "maintainer_can_modify": True,
    }, repo=repo)
    if status != 201:
        return {"ok": False, "error": f"GitHub {status}: {data.get('message')}", "detail": data}
    return {"ok": True, "number": data.get("number"), "url": data.get("html_url"),
            "head_sha": ((data.get("head") or {}).get("sha") or "")}


def get_pr(repo: str, number: int) -> dict:
    ok, reason = validate_repo(repo)
    if not ok:
        return {"ok": False, "error": reason}
    status, data = _api("GET", f"/repos/{repo}/pulls/{int(number)}", repo=repo)
    if status != 200:
        return {"ok": False, "error": f"GitHub {status}: {data.get('message')}"}
    return {
        "ok": True,
        "number": data.get("number"),
        "title": data.get("title"),
        "url": data.get("html_url"),
        "base": ((data.get("base") or {}).get("ref") or ""),
        "head": ((data.get("head") or {}).get("ref") or ""),
        "head_sha": ((data.get("head") or {}).get("sha") or ""),
        "state": data.get("state"),
        "merged": bool(data.get("merged")),
        "mergeable": data.get("mergeable"),
        "changed_files": data.get("changed_files"),
        "additions": data.get("additions"),
        "deletions": data.get("deletions"),
    }


def list_prs(repo: str, limit: int = 10) -> dict:
    ok, reason = validate_repo(repo)
    if not ok:
        return {"ok": False, "error": reason}
    status, data = _api("GET", f"/repos/{repo}/pulls?state=open&base={PR_BASE}&per_page={int(limit)}", repo=repo)
    if status != 200:
        return {"ok": False, "error": f"GitHub {status}: {data.get('message')}"}
    return {"ok": True, "items": [
        {"number": p.get("number"), "title": p.get("title"),
         "head": ((p.get("head") or {}).get("ref") or ""), "url": p.get("html_url")}
        for p in (data if isinstance(data, list) else [])
    ]}


def merge(repo: str, number: int, approvals_dir: Path | None = None) -> dict:
    """Merge a PR into dev -- only with a matching Telegram approval on file."""
    info = get_pr(repo, number)
    if not info.get("ok"):
        return info
    ok, reason = validate_base(info.get("base"))
    if not ok:
        return {"ok": False, "error": f"{reason} (PR ini menargetkan {info.get('base')!r})"}
    if info.get("merged"):
        return {"ok": False, "error": "PR sudah ter-merge"}
    if info.get("state") != "open":
        return {"ok": False, "error": f"PR tidak terbuka (state={info.get('state')})"}
    rec = read_approval(repo, number, approvals_dir)
    ok, reason = approval_matches(rec, repo, number, info.get("head_sha"))
    if not ok:
        return {"ok": False, "error": reason}
    status, data = _api("PUT", f"/repos/{repo}/pulls/{int(number)}/merge", {
        "merge_method": "squash",
        "commit_title": f"{info.get('title')} (#{number})",
        "sha": info.get("head_sha"),
    }, repo=repo)
    if status != 200:
        return {"ok": False, "error": f"GitHub {status}: {data.get('message')}"}
    return {"ok": True, "sha": data.get("sha"), "message": data.get("message"),
            "approved_by": (rec or {}).get("approved_by")}
