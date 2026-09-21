"""The hourly sweep that carries stalled task work forward on its own.

`resume.pick` is the judgement — which task is safe to resume. This is the hand
that acts on it, and it is deliberately timid:

  - it starts nothing while any engine is out, because resuming into a paused
    harness only burns the quota that is already scarce;
  - it starts nothing while a run is already live, because one agent at a time
    is what keeps unattended work directed instead of a swarm;
  - it starts exactly one task, through the same job path the dashboard uses;
  - it says what it did, on Telegram, so a sweep is never silent work.

Run by hand with `python3 resumerun.py`, or on a timer installed by the
scheduler. It is safe to run as often as you like: a busy or paused harness is
a no-op.
"""
import json
import sys
import time

import engine
import jobs
import resume
import state

#: Where the last announced failure per task is remembered. A sweep runs every
#: hour; a failure that cannot fix itself would otherwise be re-announced every
#: hour too, which is what happened on 2026-09-21 — nine identical alerts
#: overnight, each one indistinguishable from the last. Alerts that repeat
#: without new information train the reader to ignore them, so the second
#: identical failure is silent and only a *change* speaks again.
_FAILURES = state.AGENTS / ".resume-failures.json"


def _load_failures() -> dict:
    try:
        data = json.loads(_FAILURES.read_text())
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_failures(data: dict) -> None:
    try:
        _FAILURES.parent.mkdir(parents=True, exist_ok=True)
        _FAILURES.write_text(json.dumps(data, indent=2, sort_keys=True))
    except OSError:
        # Losing the memo costs a duplicate alert, never a missed one.
        pass


def should_announce(task_id: str, error: str) -> bool:
    """True the first time this exact failure is seen for this task."""
    failures = _load_failures()
    if failures.get(task_id) == error:
        return False
    failures[task_id] = error
    _save_failures(failures)
    return True


def clear_failure(task_id: str) -> None:
    """Forget a task's last failure, so a later relapse is announced again."""
    failures = _load_failures()
    if failures.pop(task_id, None) is not None:
        _save_failures(failures)

# A short instruction prepended to the task's own file, so a resumed run knows
# it is picking up started work and must account for what is already there
# rather than starting from a blank slate.
_RESUME_NOTE = (
    "This task was started earlier and left unfinished. You are resuming it, "
    "not starting fresh. Read the worktree's current diff and the task's "
    "Progress and Report sections first, state what is already done, then "
    "continue only what remains. Do not redo finished work. Commit nothing and "
    "push nothing without explicit human approval, exactly as the common role "
    "contract requires."
)


def _live_task_ids() -> set:
    """Task ids the harness itself is currently running, and a busy marker.

    The signal is jobs the harness started (jobs.listing), not every claude or
    codex process on the machine. Scraping ps counted the operator's own
    interactive session — a claude whose cwd is the workspace — and a stale
    engine from days ago as live work, which pinned the sweep at "busy" forever.
    A job the harness launched and can see finish is the only thing that means
    the harness is busy.
    """
    ids = set()
    for job in jobs.listing(20):
        if job.get("status") == "running":
            ids.add("__busy__")
            if job.get("task"):
                ids.add(job["task"])
    return ids


def _spawn(task: dict) -> dict:
    """Start a resume run for one task. Replaced in tests."""
    body = ""
    try:
        body = (state.TASKS / f"{task['id']}.md").read_text(errors="replace")
    except Exception:
        body = ""
    prompt = f"{_RESUME_NOTE}\n\n{body}"
    # No project= here: jobs.spawn derives the working directory from the task's
    # worktree via task_id. The task's Project field is display text
    # ("Name (`~/path`)"), not a path, and passing it made jobs.spawn raise.
    return jobs.spawn(role=task.get("role", "lead"), prompt=prompt,
                      task_id=task["id"])


def _notify(text: str) -> None:
    """Tell Telegram. Replaced in tests; degrades quietly if the bot is absent."""
    try:
        import tgcore
        cfg = tgcore.load_config()
        for chat in tgcore.notification_targets(cfg):
            tgcore.send(chat, text)
    except Exception:
        pass


def sweep(live_task_ids=None) -> dict:
    """One pass: resume at most one stalled task, or explain why it did not."""
    if engine.paused(is_installed=jobs._installed):
        free = engine.next_free_at()
        when = (time.strftime("%H:%M", time.localtime(free)) if free
                else "belum diketahui")
        _notify("⏸️ <b>Auto-resume paused</b> — semua engine "
                f"sedang tidak tersedia. Coba lagi otomatis; perkiraan pulih: {when}.")
        return {"action": "paused", "when": when}

    live = _live_task_ids() if live_task_ids is None else set(live_task_ids)
    if live:
        # Something is already running. Leave it be — this is not a swarm.
        return {"action": "busy"}

    task = resume.pick(live_task_ids=live)
    if task is None:
        blocked = resume.unconfigured()
        if blocked:
            # Nothing to resume *because* the board is waiting on the owner.
            # Announced once per distinct reason, same rule as a failure.
            lines = [f"• <code>{b['id']}</code> — {b['reason']}" for b in blocked]
            digest = "\n".join(lines)
            if should_announce("__unconfigured__", digest):
                _notify("🟡 <b>Task belum bisa dijalankan</b> — menunggu "
                        f"kelengkapan dari kamu:\n{digest}")
            return {"action": "unconfigured", "tasks": [b["id"] for b in blocked]}
        clear_failure("__unconfigured__")
        return {"action": "idle"}

    try:
        meta = _spawn(task)
    except Exception as exc:
        # A resume that cannot start must say so, not die in a log nobody reads
        # — but say it once. Repeating an unfixable failure hourly is how nine
        # identical alerts arrived overnight on 2026-09-21.
        if should_announce(task["id"], str(exc)):
            _notify("⚠️ <b>Auto-resume gagal</b> — "
                    f"<code>{task['id']}</code> tidak bisa dimulai: {exc}")
        return {"action": "error", "task": task["id"], "error": str(exc)}
    clear_failure(task["id"])
    _notify(f"▶️ <b>Auto-resume</b> — melanjutkan "
            f"<code>{task['id']}</code> ({task.get('role', '?')}): "
            f"{task.get('title', '')}".rstrip())
    return {"action": "started", "task": task["id"],
            "job": (meta or {}).get("id")}


if __name__ == "__main__":
    result = sweep()
    print(result.get("action", "?"), result.get("task", ""))
    sys.exit(0)
