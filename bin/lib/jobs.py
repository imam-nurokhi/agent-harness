"""Background agent runs: spawn, track, stream, stop. Stdlib only."""
from __future__ import annotations

import json
import os
import signal
import subprocess
import time
import uuid
from pathlib import Path

import state

JOBS_DIR = state.AGENTS / ".jobs"
MAX_KEEP = 60


def _meta_path(jid: str) -> Path:
    return JOBS_DIR / f"{jid}.json"


def _log_path(jid: str) -> Path:
    return JOBS_DIR / f"{jid}.log"


def _write(jid: str, meta: dict) -> None:
    _meta_path(jid).write_text(json.dumps(meta, indent=2))


def _read(jid: str) -> dict | None:
    try:
        return json.loads(_meta_path(jid).read_text())
    except Exception:
        return None


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError, TypeError):
        return False


def _engine_for(role: str) -> str:
    return "claude" if role in ("review", "qa") else "codex"


def _contract(role: str, cwd: Path, body: str) -> str:
    """The same contract the CLI builds, so UI runs are not a weaker path."""
    parts = [
        f"You are the {role.upper()} agent in a multi-agent harness. "
        "Your contract follows. Read it fully before you touch anything.",
        f"\nWorking directory: {cwd}\n"
        "Never operate outside it. ~/Documents is off-limits at all times.",
        "\n===== WORKSPACE RULES =====\n" + _safe_read(state.WORKSPACE / "AGENTS.md"),
        "\n===== COMMON ROLE PREAMBLE =====\n" + _safe_read(state.ROLES / "_common.md"),
        f"\n===== ROLE: {role} =====\n" + _safe_read(state.ROLES / f"{role}.md"),
        "\n===== TASK =====\n" + body,
        "\n===== BEGIN =====\n"
        "Restate the objective in two sentences, state any ASSUMPTION you must make, "
        "then proceed. Finish with the Report block from the common preamble.",
    ]
    return "\n".join(parts)


def _safe_read(p: Path) -> str:
    try:
        return p.read_text(errors="replace")
    except Exception:
        return f"(missing: {p})"


def spawn(role: str, prompt: str = "", task_id: str = "") -> dict:
    """Launch an agent detached, streaming into a log the UI can tail."""
    if role not in state.ROLE_LIST:
        raise ValueError(f"unknown role: {role}")

    JOBS_DIR.mkdir(parents=True, exist_ok=True)

    body = prompt.strip()
    cwd = state.WORKSPACE
    if task_id:
        tf = state.TASKS / f"{task_id}.md"
        if not tf.exists():
            raise ValueError(f"no such task: {task_id}")
        body = _safe_read(tf) + (f"\n\nEXTRA INSTRUCTION FROM THE HUMAN:\n{body}" if body else "")
        wt = state.WORKTREES / task_id
        if wt.is_dir():
            cwd = wt
    if not body:
        raise ValueError("nothing to do: give a prompt or a task id")

    jid = time.strftime("%H%M%S") + "-" + uuid.uuid4().hex[:4]
    engine = _engine_for(role)
    full = _contract(role, cwd, body)

    if engine == "codex":
        cmd = ["codex", "exec"]
        # Codex refuses to run outside a Git repo unless told otherwise. Ad-hoc
        # runs at the workspace root are legitimate, so allow it explicitly.
        if not (cwd / ".git").exists():
            cmd.append("--skip-git-repo-check")
        cmd.append(full)
    else:
        cmd = [engine, "-p", full]

    log = _log_path(jid)
    fh = open(log, "wb")
    try:
        proc = subprocess.Popen(
            cmd, cwd=str(cwd), stdout=fh, stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL, start_new_session=True,
        )
    except FileNotFoundError:
        fh.close()
        raise ValueError(f"engine '{engine}' is not installed")

    meta = {
        "id": jid, "role": role, "engine": engine, "task": task_id,
        "cwd": str(cwd), "pid": proc.pid, "started": time.time(),
        "finished": None, "exit": None,
        "title": (task_id or body.strip().splitlines()[0][:70]),
        "prompt": body[:600],
    }
    _write(jid, meta)
    _prune()
    return meta


def _prune() -> None:
    metas = sorted(JOBS_DIR.glob("*.json"), key=lambda p: -p.stat().st_mtime)
    for old in metas[MAX_KEEP:]:
        old.unlink(missing_ok=True)
        _log_path(old.stem).unlink(missing_ok=True)


def refresh(jid: str) -> dict | None:
    """Reconcile a job's recorded state with the actual process."""
    meta = _read(jid)
    if not meta:
        return None
    if meta.get("finished") is None and not _alive(meta.get("pid", -1)):
        meta["finished"] = _log_path(jid).stat().st_mtime if _log_path(jid).exists() else time.time()
        meta["exit"] = "done"
        _write(jid, meta)
    return meta


def status(meta: dict) -> str:
    if meta.get("finished") is None:
        return "running"
    return meta.get("exit") or "done"


def listing(limit: int = 24) -> list[dict]:
    if not JOBS_DIR.is_dir():
        return []
    out = []
    for mp in sorted(JOBS_DIR.glob("*.json"), key=lambda p: -p.stat().st_mtime)[:limit]:
        meta = refresh(mp.stem)
        if not meta:
            continue
        log = _log_path(meta["id"])
        meta = dict(meta)
        meta["status"] = status(meta)
        meta["bytes"] = log.stat().st_size if log.exists() else 0
        meta["elapsed"] = int((meta.get("finished") or time.time()) - meta["started"])
        out.append(meta)
    return out


def tail(jid: str, offset: int = 0, cap: int = 200_000) -> dict:
    """Bytes since `offset`, so the UI can stream without re-sending history."""
    meta = refresh(jid)
    if not meta:
        return {"error": "no such job"}
    log = _log_path(jid)
    if not log.exists():
        return {"id": jid, "offset": 0, "chunk": "", "status": status(meta), "eof": True}

    size = log.stat().st_size
    if offset > size:          # log was rotated or truncated
        offset = 0
    with open(log, "rb") as fh:
        fh.seek(offset)
        raw = fh.read(cap)
    return {
        "id": jid,
        "offset": offset + len(raw),
        "size": size,
        "chunk": raw.decode("utf-8", errors="replace"),
        "status": status(meta),
        "role": meta["role"],
        "engine": meta["engine"],
        "task": meta.get("task", ""),
        "title": meta.get("title", ""),
        "elapsed": int((meta.get("finished") or time.time()) - meta["started"]),
        "eof": status(meta) != "running",
    }


def stop(jid: str) -> dict:
    meta = _read(jid)
    if not meta:
        return {"error": "no such job"}
    pid = meta.get("pid")
    if pid and _alive(pid):
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        except Exception:
            try:
                os.kill(pid, signal.SIGTERM)
            except Exception:
                pass
    meta["finished"] = time.time()
    meta["exit"] = "stopped"
    _write(jid, meta)
    return {"ok": True, "id": jid}
