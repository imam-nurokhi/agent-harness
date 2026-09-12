"""Collect live agent-harness state from the filesystem. No dependencies."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

WORKSPACE = Path(os.environ.get("AH_WORKSPACE", Path.home() / "AI-Workspace"))
AGENTS = WORKSPACE / "agents"
TASKS = AGENTS / "tasks"
REPORTS = AGENTS / "reports"
ROLES = AGENTS / "roles"
WORKTREES = WORKSPACE / "worktrees"
PROJECTS = WORKSPACE / "projects"

ROLE_LIST = ["lead", "frontend", "backend", "qa", "review", "devops", "docs"]


def _git(cwd: Path, *args: str) -> str:
    try:
        return subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True, text=True, timeout=10
        ).stdout.strip()
    except Exception:
        return ""


def _field(text: str, key: str) -> str:
    m = re.search(rf"^- \*\*{key}:\*\* *(.+)$", text, re.M)
    return m.group(1).strip().strip("`") if m else ""


def _task_status(task_id: str, has_wt: bool, has_report: bool, done: int, total: int) -> str:
    if has_report:
        return "reported"
    if has_wt and done and done == total:
        return "review"
    if has_wt:
        return "active"
    return "planned"


def tasks() -> list[dict]:
    out = []
    for f in sorted(TASKS.glob("*.md")):
        text = f.read_text(errors="replace")
        tid = f.stem
        title_m = re.search(r"^# Task: *(.+)$", text, re.M)

        # Acceptance criteria progress
        block = re.search(r"## Acceptance criteria\n(.*?)(?=\n## )", text, re.S)
        crit = re.findall(r"^- \[( |x|X)\] *(.+)$", block.group(1), re.M) if block else []
        done = sum(1 for c, _ in crit if c.lower() == "x")

        # Required checks progress
        cblock = re.search(r"## Required checks\n(.*?)(?=\n## |\Z)", text, re.S)
        checks = re.findall(r"^- \[( |x|X)\] *(.+)$", cblock.group(1), re.M) if cblock else []

        wt = WORKTREES / tid
        has_wt = wt.is_dir()
        report = REPORTS / f"{tid}.md"
        logs = sorted(REPORTS.glob(f"{tid}.*.log"))
        has_report = report.exists() or bool(logs)

        out.append({
            "id": tid,
            "title": title_m.group(1).strip() if title_m else tid,
            "role": _field(text, "Role"),
            "project": _field(text, "Project"),
            "klass": _field(text, "Class"),
            "base": _field(text, "Base branch"),
            "criteria": [{"done": c.lower() == "x", "text": t} for c, t in crit],
            "criteria_done": done,
            "criteria_total": len(crit),
            "checks": [{"done": c.lower() == "x", "text": t} for c, t in checks],
            "has_worktree": has_wt,
            "logs": [l.name for l in logs],
            "status": _task_status(tid, has_wt, has_report, done, len(crit)),
            "mtime": f.stat().st_mtime,
        })
    return out


def worktrees() -> list[dict]:
    out = []
    if not WORKTREES.is_dir():
        return out
    for d in sorted(p for p in WORKTREES.iterdir() if p.is_dir()):
        porcelain = _git(d, "status", "--porcelain")
        files = [l[3:] for l in porcelain.splitlines() if l.strip()]
        branch = _git(d, "branch", "--show-current")
        base = _git(d, "rev-parse", "--abbrev-ref", "HEAD@{upstream}") or "develop"
        ahead = _git(d, "rev-list", "--count", f"{base}..HEAD") if base else ""
        diffstat = _git(d, "diff", "--shortstat")
        last = _git(d, "log", "-1", "--format=%h %s|%ar")
        sha, _, when = last.partition("|")
        out.append({
            "task": d.name,
            "branch": branch or "?",
            "path": str(d),
            "dirty": len(files),
            "files": files[:25],
            "ahead": ahead,
            "diffstat": diffstat,
            "last_commit": sha,
            "last_when": when,
            "mtime": d.stat().st_mtime,
        })
    return out


def reports() -> list[dict]:
    out = []
    if not REPORTS.is_dir():
        return out
    for f in sorted(REPORTS.glob("*"), key=lambda p: -p.stat().st_mtime):
        if f.name.startswith(".") or f.is_dir():
            continue
        text = f.read_text(errors="replace")[-4000:]
        verdict = ""
        for pat in (r"\*\*(Approve[^*]*|Block)\*\*", r"^(Approve.*|Block.*)$"):
            m = re.search(pat, text, re.M)
            if m:
                verdict = m.group(1)[:40]
                break
        out.append({
            "name": f.name,
            "task": f.name.split(".")[0],
            "size": f.stat().st_size,
            "mtime": f.stat().st_mtime,
            "verdict": verdict,
            "tail": text[-1200:],
        })
    return out[:40]


def _describe_project(repo: Path, klass: str) -> dict:
    is_git = (repo / ".git").exists()
    dirty = 0
    if is_git:
        dirty = len([l for l in _git(repo, "status", "--porcelain").splitlines() if l.strip()])
    return {
        "name": repo.name,
        "klass": klass,
        "path": str(repo),
        "git": is_git,
        "branch": _git(repo, "branch", "--show-current") if is_git else "",
        "dirty": dirty,
        "has_agents_md": (repo / "AGENTS.md").exists(),
    }


def projects() -> list[dict]:
    """A project is either projects/<class>/<repo> or a repo sitting directly
    at projects/<name>. Never descend into .git or other dot directories."""
    out = []
    if not PROJECTS.is_dir():
        return out
    for entry in sorted(p for p in PROJECTS.iterdir()
                        if p.is_dir() and not p.name.startswith(".")):
        if (entry / ".git").exists():
            out.append(_describe_project(entry, entry.name))
            continue
        for repo in sorted(p for p in entry.iterdir()
                           if p.is_dir() and not p.name.startswith(".")):
            out.append(_describe_project(repo, entry.name))
    return out


def health() -> dict:
    engines = {}
    for b in ("codex", "claude", "git", "gh", "node"):
        engines[b] = shutil.which(b) or ""
    total, used, free = shutil.disk_usage(Path.home())
    return {
        "engines": engines,
        "codex_auth": (Path.home() / ".codex" / "auth.json").exists(),
        "claude_auth": (Path.home() / ".claude").is_dir(),
        "disk_free_gb": round(free / 1e9, 1),
        "disk_pct": round(used / total * 100),
        "workspace": str(WORKSPACE),
        "roles": [r for r in ROLE_LIST if (ROLES / f"{r}.md").exists()],
        "documents_guard": "Documents" in (WORKSPACE / "AGENTS.md").read_text(errors="replace")
        if (WORKSPACE / "AGENTS.md").exists() else False,
    }


def activity(limit: int = 25) -> list[dict]:
    events = []
    for base, kind in ((TASKS, "task"), (REPORTS, "report"), (WORKTREES, "worktree")):
        if not base.is_dir():
            continue
        for f in base.rglob("*"):
            if ".git" in f.parts or f.name.startswith("."):
                continue
            try:
                events.append({"kind": kind, "name": str(f.relative_to(WORKSPACE)),
                               "mtime": f.stat().st_mtime})
            except OSError:
                continue
    events.sort(key=lambda e: -e["mtime"])
    return events[:limit]


# ---------------------------------------------------------------- live agents

ROLE_PERSONA = {
    "lead":     {"name": "Raja",       "glyph": "\u265a", "piece": "King",   "title": "Lead",          "desk": 0},
    "qa":       {"name": "Ster",       "glyph": "\u265b", "piece": "Queen",  "title": "QA",            "desk": 1},
    "devops":   {"name": "Benteng",    "glyph": "\u265c", "piece": "Rook",   "title": "DevOps",        "desk": 2},
    "review":   {"name": "Kuda",       "glyph": "\u265e", "piece": "Knight", "title": "Code Review",   "desk": 3},
    "frontend": {"name": "Peluncur 1", "glyph": "\u265d", "piece": "Bishop", "title": "Frontend",      "desk": 4},
    "backend":  {"name": "Peluncur 2", "glyph": "\u265d", "piece": "Bishop", "title": "Backend",       "desk": 5},
    "docs":     {"name": "Pion",       "glyph": "\u265f", "piece": "Pawn",   "title": "Documentation", "desk": 6},
}


def _proc_cwd(pid: str) -> str:
    try:
        out = subprocess.run(["lsof", "-a", "-p", pid, "-d", "cwd", "-Fn"],
                             capture_output=True, text=True, timeout=5).stdout
    except Exception:
        return ""
    for line in out.splitlines():
        if line.startswith("n"):
            return line[1:]
    return ""


def _live_engine_procs() -> list[dict]:
    """Engine processes that are actually doing task work: a codex/claude whose
    cwd sits inside the workspace. Daemons and helpers are filtered out."""
    try:
        ps = subprocess.run(["ps", "-eo", "pid=,etime=,comm=,args="],
                            capture_output=True, text=True, timeout=8).stdout
    except Exception:
        return []

    procs = []
    for line in ps.splitlines():
        parts = line.split(None, 3)
        if len(parts) < 4:
            continue
        pid, etime, _comm, args = parts
        base = args.split()[0].rsplit("/", 1)[-1]
        if base not in ("codex", "claude"):
            continue
        # Background plumbing, not an agent doing work.
        if any(k in args for k in ("bg-pty-host", "bg-spare", "daemon run",
                                   "--bg-spare", "mcp", "ChatGPT")):
            continue
        cwd = _proc_cwd(pid)
        if not cwd or not cwd.startswith(str(WORKSPACE)):
            continue
        procs.append({"pid": pid, "etime": etime.strip(), "engine": base, "cwd": cwd})
    return procs


def agents() -> list[dict]:
    """The roster: one card per role, with whatever it is doing right now."""
    procs = _live_engine_procs()
    task_by_id = {t["id"]: t for t in tasks()}

    # Which task is each live process sitting in?
    busy: dict[str, dict] = {}
    for pr in procs:
        rel = Path(pr["cwd"])
        tid = None
        for parent in [rel, *rel.parents]:
            if parent.parent == WORKTREES:
                tid = parent.name
                break
        if tid and tid in task_by_id:
            role = task_by_id[tid].get("role") or "lead"
            busy.setdefault(role, {"task": tid, "title": task_by_id[tid]["title"],
                                   "engine": pr["engine"], "etime": pr["etime"],
                                   "pid": pr["pid"]})

    # A role with an assigned task but no live process is "assigned", not idle.
    assigned: dict[str, dict] = {}
    for t in task_by_id.values():
        role = t.get("role")
        if role and t["status"] in ("planned", "active", "review"):
            assigned.setdefault(role, t)

    out = []
    for role in sorted(ROLE_LIST, key=lambda r: ROLE_PERSONA.get(r, {}).get('desk', 99)):
        persona = ROLE_PERSONA.get(
            role, {"name": role, "glyph": "?", "piece": "", "title": role, "desk": 9})
        work = busy.get(role)
        at = assigned.get(role)
        if work:
            status, detail = "working", f"{work['task']} · {work['engine']} · {work['etime']}"
        elif at:
            status, detail = "assigned", f"{at['id']} · {at['status']}"
        else:
            status, detail = "idle", "no task"
        out.append({
            "role": role,
            "name": persona["name"],
            "glyph": persona["glyph"],
            "piece": persona["piece"],
            "title": persona["title"],
            "desk": persona["desk"],
            "status": status,
            "detail": detail,
            "task": (work or at or {}).get("task") or (at or {}).get("id") or "",
            "task_title": (work or {}).get("title") or (at or {}).get("title") or "",
            "engine": (work or {}).get("engine", ""),
            "has_contract": (ROLES / f"{role}.md").exists(),
        })
    return out


# ------------------------------------------------------------------ triggers

TRIGGERS = AGENTS / "triggers.json"


def triggers() -> list[dict]:
    if not TRIGGERS.exists():
        return []
    try:
        data = json.loads(TRIGGERS.read_text())
    except Exception:
        return []
    out = []
    for tr in data.get("triggers", []):
        out.append({
            "id": tr.get("id", "?"),
            "label": tr.get("label", ""),
            "schedule": tr.get("schedule", ""),
            "role": tr.get("role", ""),
            "prompt": tr.get("prompt", ""),
            "enabled": bool(tr.get("enabled", True)),
            "last_run": tr.get("last_run", ""),
            "installed": _launchd_installed(tr.get("id", "")),
        })
    return out


def _launchd_installed(tid: str) -> bool:
    if not tid:
        return False
    plist = Path.home() / "Library" / "LaunchAgents" / f"com.ah.trigger.{tid}.plist"
    return plist.exists()


def snapshot() -> dict:
    t = tasks()
    return {
        "generated": time.time(),
        "health": health(),
        "tasks": t,
        "worktrees": worktrees(),
        "reports": reports(),
        "projects": projects(),
        "activity": activity(),
        "agents": agents(),
        "triggers": triggers(),
        "summary": {
            "tasks_total": len(t),
            "by_status": {s: sum(1 for x in t if x["status"] == s)
                          for s in ("planned", "active", "review", "reported")},
        },
    }


if __name__ == "__main__":
    print(json.dumps(snapshot(), indent=2))
