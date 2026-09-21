"""Push an agent's work to a remote — to a fresh branch, never to a shared one.

**The rule changed on 2026-09-19.** It used to be "nothing lands anywhere but
dev or staging, and only after an approval from Telegram", and this module
pushed a worktree's HEAD straight onto dev. The owner replaced it:

    commit+push dilakukan ke branch baru dan hanya bisa dibuatkan PR untuk
    merge ke branch dev saja, merge PR hanya bisa dilakukan jika saya approved
    by telegrambot

So dev is no longer a push target at all. Work reaches dev only as a pull
request that the owner merges by tapping Approve in Telegram. This module now
does one thing: validate and push to a freshly minted `ah/...` branch. The
branch naming, the PR, and the approval gate live in ghflow.py, which is the
single place those rules are expressed and tested.

Defence in depth is unchanged: ops/harness/protect.sh independently blocks a
push to main/master/production/prod in every onboarded repo, so even a bug here
cannot land work on a protected branch.
"""
import subprocess

import ghflow
import state

#: Kept for readers who remember the old contract: there are no shared push
#: targets any more. dev is reached through a pull request, nothing else.
ALLOWED_TARGETS = ()
FORBIDDEN = ghflow.PROTECTED + (ghflow.PR_BASE,)


def validate_target(name: str) -> tuple:
    """(ok, reason). Only a fresh ah/ branch passes; shared branches never do.

    Delegates to ghflow so the harness has exactly one definition of "a branch
    an agent may write to", rather than two that can drift apart.
    """
    return ghflow.validate_head(name)


def _safe_id(task_id: str):
    tid = (task_id or "").strip()
    if not tid or "/" in tid or "\\" in tid or ".." in tid:
        return None
    return tid


def plan(task_id: str, target: str = "") -> tuple:
    """Validate a push without doing it: (ok, info-or-reason).

    `target` is optional now. Left empty, the branch is minted from the task id
    -- which is the normal path, because a human choosing the branch name was
    how work used to end up on dev.
    """
    tid = _safe_id(task_id)
    if not tid:
        return False, "invalid task id"
    branch = (target or "").strip() or ghflow.branch_for(tid)
    ok, reason = validate_target(branch)
    if not ok:
        return False, reason
    wt = state.WORKTREES / tid
    if not wt.is_dir():
        return False, f"no worktree for {tid}"
    if dirty(wt):
        # A push sends HEAD. Uncommitted work is simply not in HEAD, so pushing
        # a dirty worktree produces a branch and a PR that silently omit the
        # change the owner just reviewed with /diff. Refuse instead.
        return False, (f"worktree {tid} masih ada perubahan yang belum di-commit. "
                       "Minta agent commit dulu, baru /push.")
    return True, {"task": tid, "target": branch, "branch": branch, "worktree": wt}


def dirty(worktree) -> bool:
    """True when the worktree has changes that a push would leave behind."""
    try:
        res = subprocess.run(["git", "-C", str(worktree), "status", "--porcelain"],
                             capture_output=True, text=True, timeout=30)
    except Exception:
        return False
    return bool(res.stdout.strip())


def push(task_id: str, target: str = "", repo: str = "") -> dict:
    """Push the worktree's HEAD to a new branch on the repo.

    No pull --rebase any more: the branch is new, so there is nothing to rebase
    onto, and a non-fast-forward means the name is taken -- which must fail
    loudly rather than be reconciled.
    """
    ok, info = plan(task_id, target)
    if not ok:
        return {"ok": False, "error": info}
    if not repo:
        return {"ok": False, "error": "repo tujuan wajib: <org>/<repo>"}
    res = ghflow.push_branch(info["worktree"], repo, info["branch"])
    if not res.get("ok"):
        return res
    return {"ok": True, "task": info["task"], "branch": info["branch"],
            "repo": repo, "detail": res.get("output", "")}
