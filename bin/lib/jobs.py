"""Background agent runs: spawn, track, stream, stop. Stdlib only."""
from __future__ import annotations

import json
import os
import signal
import shlex
import shutil
import subprocess
import time
import uuid
from pathlib import Path

import engine as engine_module
import state

JOBS_DIR = state.AGENTS / ".jobs"
MAX_KEEP = 60


# The reviewed allowlist the headless agent runs under. See
# ops/harness/README.md and ops/harness/tests/.
AGENT_SETTINGS = state.WORKSPACE / "ops" / "harness" / "claude-settings.json"


def _meta_path(jid: str) -> Path:
    return JOBS_DIR / f"{jid}.json"


def _log_path(jid: str) -> Path:
    return JOBS_DIR / f"{jid}.log"


def _rc_path(jid: str) -> Path:
    """Exit code sidecar, written by the shell wrapper when the engine exits.

    A file, not a memory of the process, because the parent that spawned the
    run (bot or dashboard) is restarted by the supervisor and must still be
    able to tell a crash from a success afterwards.
    """
    return JOBS_DIR / f"{jid}.rc"


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
    """Claude first, then whatever else is installed and still authorised.

    Installed is not the same as allowed to run: an org can disable Claude Code
    for the account whose credentials this process inherits, and then every
    claude run fails identically. `engine.pick` skips an engine that has
    already refused, so the harness moves to codex instead of retrying a wall.
    AH_ENGINE still overrides everything.
    """
    return engine_module.pick(role, is_installed=_installed)


def _installed(name: str) -> bool:
    """Resolve the way this process will actually launch it, not by PATH alone."""
    try:
        resolve_engine(name)
        return True
    except ValueError:
        return False


def _paused_reason() -> str:
    out = engine_module.unavailable()
    parts = []
    for name, entry in sorted(out.items()):
        if entry.get("kind") == engine_module.KIND_LIMITED and entry.get("until"):
            parts.append(f"{name} is out of quota until "
                         f"{time.strftime('%H:%M', time.localtime(entry['until']))}")
        else:
            parts.append(f"{name} is refused for this account")
    return ("the harness is paused: no engine can run right now (" +
            "; ".join(parts) + ")") if parts else "the harness is paused"


def _model_for(role: str) -> str:
    """With one vendor, reviewer independence comes from model and context.

    `review`/`qa` get their own model and are handed the diff, never the
    implementer's session — see AH_MODEL_REVIEW / AH_MODEL_IMPL in .env.
    """
    key = "AH_MODEL_REVIEW" if role in ("review", "qa") else "AH_MODEL_IMPL"
    return os.environ.get(key, "").strip()


# launchd hands a process a bare PATH (/usr/bin:/bin:/usr/sbin:/sbin), so the
# engines and the tools agents shell out to are invisible unless we rebuild it.
EXTRA_PATHS = [
    Path.home() / ".local" / "bin",
    Path("/opt/homebrew/bin"),
    Path("/opt/homebrew/sbin"),
    Path("/usr/local/bin"),
]


def agent_env() -> dict:
    env = dict(os.environ)
    parts = [str(p) for p in EXTRA_PATHS if p.is_dir()]
    for p in env.get("PATH", "").split(":"):
        if p and p not in parts:
            parts.append(p)
    env["PATH"] = ":".join(parts)
    env.setdefault("HOME", str(Path.home()))

    # Which Claude account the engine authenticates as is decided by
    # CLAUDE_CONFIG_DIR. An interactive session here points it at the work
    # account; launchd does not, so the engine fell back to the org-disabled
    # team account and every run was refused. Carry it explicitly. An operator
    # override (AH_CLAUDE_CONFIG_DIR) wins over whatever was inherited, but a
    # directory that does not exist is never forced — that would break the
    # engine instead of fixing it.
    want = os.environ.get("AH_CLAUDE_CONFIG_DIR", "").strip()
    if not want and "CLAUDE_CONFIG_DIR" not in env:
        default = Path.home() / ".claude-work"
        if default.is_dir():
            want = str(default)
    if want and Path(want).is_dir():
        env["CLAUDE_CONFIG_DIR"] = want
    return env


def resolve_engine(name: str) -> str:
    """Absolute path to an engine, searching beyond the inherited PATH."""
    found = shutil.which(name, path=agent_env()["PATH"])
    if found:
        return found
    for base in EXTRA_PATHS:
        cand = base / name
        if cand.is_file() and os.access(cand, os.X_OK):
            return str(cand)
    raise ValueError(
        f"engine '{name}' is not installed, or is not on this process's PATH. "
        f"Looked in: {', '.join(str(p) for p in EXTRA_PATHS)}"
    )


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


def spawn(role: str, prompt: str = "", task_id: str = "",
          project: str = "", engine: str = "", attempt: int = 1,
          parent: str = "", resumes: int = 0) -> dict:
    """Launch an agent detached, streaming into a log the UI can tail."""
    if role not in state.ROLE_LIST:
        raise ValueError(f"unknown role: {role}")

    # Every engine is refused or out of quota. Starting anyway would spend the
    # one thing that is scarce here — a retry — on a run that cannot begin. The
    # operator is told instead, and the harness waits.
    if not engine and engine_module.paused(is_installed=_installed):
        raise ValueError(_paused_reason())

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

    if project:
        target = (state.PROJECTS / project) if not Path(project).is_absolute() else Path(project)
        target = target.resolve()
        if not target.is_dir():
            raise ValueError(f"no such project: {project}")
        if str(target).startswith(str(Path.home() / "Documents")):
            raise ValueError("~/Documents is off-limits")
        cwd = target
    if not body:
        raise ValueError("nothing to do: give a prompt or a task id")

    jid = time.strftime("%H%M%S") + "-" + uuid.uuid4().hex[:4]
    engine = engine or _engine_for(role)
    full = _contract(role, cwd, body)

    engine_bin = resolve_engine(engine)

    model = _model_for(role)
    if engine == "codex":
        cmd = [engine_bin, "exec"]
        # Codex refuses to run outside a Git repo unless told otherwise. Ad-hoc
        # runs at the workspace root are legitimate, so allow it explicitly.
        if not (cwd / ".git").exists():
            cmd.append("--skip-git-repo-check")
        if model:
            cmd += ["--model", model]
        cmd.append(full)
    else:
        cmd = [engine_bin, "-p"]
        # An unattended run has nobody to answer a permission prompt, so the
        # policy must travel with the command. Without this the agent burns a
        # full run discovering it cannot execute anything and reports "blocked"
        # -- job 135157-520a spent 181s failing to run print('hello').
        # common.sh carries the same flag for `ah run`; this is the path the
        # dashboard and the Telegram /run and /ask commands take.
        if AGENT_SETTINGS.is_file():
            cmd += ["--settings", str(AGENT_SETTINGS)]
        if model:
            cmd += ["--model", model]
        cmd.append(full)

    log = _log_path(jid)
    rc = _rc_path(jid)
    rc.unlink(missing_ok=True)
    # Run the engine under a shell that records its exit code. Without this the
    # only signal is "the pid is gone", which cannot distinguish a clean finish
    # from a crash — and reads as success on a zombie that nobody reaped.
    wrapped = ["/bin/sh", "-c",
               f'{" ".join(shlex.quote(c) for c in cmd)}; '
               f'printf "%s" "$?" > {shlex.quote(str(rc))}']
    fh = open(log, "wb")
    try:
        proc = subprocess.Popen(
            wrapped, cwd=str(cwd), stdout=fh, stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL, start_new_session=True, env=agent_env(),
        )
    except FileNotFoundError:
        fh.close()
        raise ValueError(f"engine '{engine}' could not be executed at {engine_bin}")
    finally:
        # The child holds its own descriptor; the daemon must not keep one per
        # run or it leaks a file descriptor for every job it ever starts.
        fh.close()

    meta = {
        "id": jid, "role": role, "engine": engine, "model": model, "task": task_id,
        "cwd": str(cwd), "pid": proc.pid, "started": time.time(),
        "finished": None, "exit": None,
        "title": (task_id or body.strip().splitlines()[0][:70]),
        "prompt": body[:600],
        "attempt": attempt, "parent": parent, "project": project,
        "resumes": resumes,
    }
    # The retry needs the whole instruction, not the 600 characters the UI
    # shows. Kept beside the log so a restarted bot can still resume it.
    _body_path(jid).write_text(body)
    _write(jid, meta)
    _prune()
    return meta


def _body_path(jid: str) -> Path:
    return JOBS_DIR / f"{jid}.body"


# A quota comes back; waiting for it again is not a new attempt at the work.
# MAX_RESUMES only stops a job that has been waiting all day from queueing for
# ever if something about it is permanently unrunnable.
MAX_RESUMES = 5


def _stalled_by_limit(meta: dict) -> bool:
    """A job that stopped because a quota ran out, and is not finished with."""
    return (status(meta) == "failed"
            and meta.get("engine_fault") == engine_module.KIND_LIMITED
            and not meta.get("retried")
            and int(meta.get("resumes", 0)) < MAX_RESUMES)


def waiting() -> list[dict]:
    """Jobs held only by a quota, which will resume on their own."""
    out = []
    if not JOBS_DIR.is_dir():
        return out
    for mp in sorted(JOBS_DIR.glob("*.json"), key=lambda p: -p.stat().st_mtime)[:20]:
        meta = _read(mp.stem)
        if meta and _stalled_by_limit(meta):
            out.append(meta)
    return out


def retry_if_engine_failed(jid: str) -> dict | None:
    """Hand the same work to another engine, if the engine was the problem.

    Two different things are bounded here, and conflating them is what would
    leave work abandoned overnight:

      attempt  rotation between engines *now*. Capped at MAX_ATTEMPTS because
               each one spends a real quota within the same minute.
      resumes  coming back after a quota has refilled. That is not another go
               at the work, it is the first go finally getting to start, so it
               begins the attempt budget again.

    Only a refusal or a limit is retried at all. An ordinary failure is the
    agent's own, and running it elsewhere would spend a second quota to
    reproduce the same bug.
    """
    meta = refresh(jid)
    if not meta or status(meta) != "failed" or meta.get("retried"):
        return None
    kind = meta.get("engine_fault") or engine_module.classify(_log_head(jid))
    if kind is None:
        return None
    if engine_module.paused(is_installed=_installed):
        return None

    attempt, resumes = int(meta.get("attempt", 1)), int(meta.get("resumes", 0))

    # Did the quota that stopped this job refill? Then this is not another go
    # at the work — it is the first go finally getting to start, so the
    # rotation budget begins again. Rotating between engines inside one minute
    # and coming back an hour later are different things and must not share a
    # counter, or a job stalled overnight would be abandoned by morning.
    was = meta.get("engine", "")
    resumed = (kind == engine_module.KIND_LIMITED
               and was not in engine_module.unavailable())
    if resumed:
        if resumes >= MAX_RESUMES:
            return None
        attempt, resumes = 0, resumes + 1
    elif attempt >= engine_module.MAX_ATTEMPTS:
        return None

    body = ""
    try:
        body = _body_path(jid).read_text()
    except Exception:
        body = meta.get("prompt", "")
    if not body.strip():
        return None

    meta["retried"] = True
    _write(jid, meta)
    return spawn(role=meta.get("role", "lead"), prompt=body,
                 task_id=meta.get("task", ""), project=meta.get("project", ""),
                 attempt=attempt + 1, parent=jid, resumes=resumes)


def tick() -> list[dict]:
    """Advance any job the engine, not the agent, caused to fail.

    Called from the surfaces that poll anyway (the dashboard's state read and
    the bot's loop), because a detached job has nobody else to reconsider it.
    Idempotent per job: `retried` is written before the replacement starts.
    """
    started = []
    if not JOBS_DIR.is_dir():
        return started
    for mp in sorted(JOBS_DIR.glob("*.json"), key=lambda p: -p.stat().st_mtime)[:20]:
        try:
            nxt = retry_if_engine_failed(mp.stem)
        except Exception:
            nxt = None
        if nxt:
            started.append(nxt)
    return started


def _prune() -> None:
    metas = sorted(JOBS_DIR.glob("*.json"), key=lambda p: -p.stat().st_mtime)
    for old in metas[MAX_KEEP:]:
        old.unlink(missing_ok=True)
        _log_path(old.stem).unlink(missing_ok=True)
        _rc_path(old.stem).unlink(missing_ok=True)
        _body_path(old.stem).unlink(missing_ok=True)


def _reap(pid: int) -> None:
    """Clear our own zombie so the pid stops looking alive to os.kill(pid, 0)."""
    try:
        os.waitpid(pid, os.WNOHANG)
    except (ChildProcessError, OSError, TypeError):
        pass


def refresh(jid: str) -> dict | None:
    """Reconcile a job's recorded state with what the engine actually did."""
    meta = _read(jid)
    if not meta:
        return None
    if meta.get("finished") is not None:
        return meta

    pid = meta.get("pid", -1)
    _reap(pid)
    rc = _rc_path(jid)
    code = None
    if rc.exists():
        try:
            code = int(rc.read_text().strip() or -1)
        except ValueError:
            code = -1
    elif _alive(pid):
        return meta
    else:
        # The wrapper died without recording anything — killed, OOM, or the
        # machine went down mid-run. That is a failure, not a success.
        code = -1

    meta["finished"] = (_log_path(jid).stat().st_mtime
                        if _log_path(jid).exists() else time.time())
    head = _log_head(jid)
    kind = engine_module.classify(head)
    meta["code"] = code
    # An engine that refuses or runs out of quota can still exit 0. Such a run
    # produced nothing, and must never reach the board or Telegram as a tick.
    meta["exit"] = "done" if (code == 0 and kind is None) else "failed"
    if kind:
        meta["engine_fault"] = kind
    _write(jid, meta)

    # The run just proved something about the engine. A refusal ("your org has
    # disabled Claude Code") gets it skipped next time; a success clears an
    # earlier note, so access restored by an admin is picked up on its own.
    engine_module.note_result(meta.get("engine", ""), code == 0, head)
    return meta


def _log_head(jid: str, limit: int = 2000) -> str:
    """The opening of a job's log.

    Deliberately the head and not the tail. A refused engine says so
    immediately and stops; an agent that merely *discusses* authentication does
    it deep inside a long transcript. Reading the end would confuse the two and
    quietly move every later run to another vendor.
    """
    try:
        with open(_log_path(jid), "rb") as fh:
            return fh.read(limit).decode("utf-8", "replace")
    except Exception:
        return ""


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
