"""Pick the one stalled task an unattended sweep should carry forward.

The harness can now run for hours without anyone watching, and the owner wants
work that stopped half-finished to continue on its own. The judgement of WHICH
task is the whole safety story, so it lives here, alone, behind tests — not
tangled into the scheduler that calls it.

A task is eligible only when it was genuinely started and genuinely not
finished, and when picking it up cannot step on anybody:

  - it has a worktree (planning roles excepted) and unmet acceptance criteria
    and no report yet — the definition of started-but-stalled;
  - its file does not say do-not-run;
  - no one holds a claim on it and no run is live against it;
  - its project is not on hold.

Exactly one task comes back per sweep, and the same one each sweep until it
moves, so an unattended harness finishes one thing before starting the next
instead of scattering half-runs across the board.
"""
import re

import state

# A task file may forbid its own automation. This is how task-038 (a security
# finding logged for the owner to decide on) stays untouched no matter what.
_DO_NOT_RUN = re.compile(
    r"jangan dijalankan|do not run|do-not-run|hands off|menunggu keputusan owner",
    re.IGNORECASE)

# Planning roles read and report; they do not need an isolated worktree, so a
# started-but-stalled planning task is one that simply has unmet criteria.
_NO_WORKTREE_ROLES = ("lead", "docs")


def _forbids_running(task: dict) -> bool:
    try:
        text = (state.TASKS / f"{task['id']}.md").read_text(errors="replace")
    except Exception:
        # If the file cannot even be read, the safe reading is hands-off.
        return True
    return bool(_DO_NOT_RUN.search(text))


def unstartable_reason(task: dict) -> str:
    """Why this task could never be spawned, or "" when it could be.

    Checked before the sweep commits to a task, because `jobs.spawn` raising
    "unknown role" is not a transient failure: an hour later the file says the
    same thing, so the same alert fires again. Nine of them arrived on
    2026-09-21 before anyone looked.
    """
    role = (task.get("role") or "").strip().lower()
    if not role:
        return ("role belum diisi — lengkapi dengan "
                f"/assign {task.get('id', '<task>')} <role>")
    if role not in state.ROLE_LIST:
        return (f"role {role!r} tidak dikenal — pilih salah satu dari: "
                + ", ".join(state.ROLE_LIST))
    return ""


def _is_stalled(task: dict) -> bool:
    """Started, and not finished. Not a fresh idea, not a completed one."""
    if task.get("status") == "reported":
        return False
    total = task.get("criteria_total", 0)
    done = task.get("criteria_done", 0)
    if total and done >= total:
        # Every criterion ticked — done enough to await review, not to rework.
        return False
    if unstartable_reason(task):
        # Not stalled work — unconfigured work. Offering it to the sweep only
        # produces an alert nobody can act on from a phone. See unconfigured().
        return False
    role = (task.get("role") or "").strip().lower()
    if role not in _NO_WORKTREE_ROLES and not task.get("has_worktree"):
        return False
    return True


def unconfigured(is_held=None):
    """Tasks that look started but can never run, each with its reason.

    Skipping them silently would trade a loud bug for a quiet one: nothing
    happens and nobody knows why. This is what `/status` and the sweep report
    read so the owner can see the board is waiting on *them*.
    """
    held = is_held or (lambda t: state.is_held(t.get("klass", ""),
                                               _project_name(t)))
    out = []
    for task in state.tasks():
        if task.get("status") == "reported" or task.get("claim"):
            continue
        if not task.get("has_worktree"):
            continue
        reason = unstartable_reason(task)
        if not reason or held(task):
            continue
        out.append({"id": task["id"], "title": task.get("title", ""),
                    "reason": reason})
    out.sort(key=lambda t: t["id"])
    return out


def candidates(live_task_ids=None, is_held=None):
    """Every task a sweep could safely resume, in a stable, directed order.

    `is_held` is injected so the scope rules (which project classes are paused)
    are enforced by the caller that owns them, and can be tested in isolation.
    """
    live = set(live_task_ids or ())
    held = is_held or (lambda t: state.is_held(t.get("klass", ""),
                                               _project_name(t)))
    out = []
    for task in state.tasks():
        if task["id"] in live:
            continue
        if task.get("claim"):
            continue
        if not _is_stalled(task):
            continue
        if _forbids_running(task):
            continue
        if held(task):
            continue
        out.append(task)
    # Lowest task id first: deterministic, and it keeps the sweep on the oldest
    # unfinished work rather than whatever was touched most recently.
    out.sort(key=lambda t: t["id"])
    return out


def pick(live_task_ids=None, is_held=None):
    """The single task to resume now, or None when the board has nothing to do."""
    found = candidates(live_task_ids, is_held)
    return found[0] if found else None


def _project_name(task: dict) -> str:
    proj = (task.get("project") or "").strip()
    # The project field is often "NAME (`~/path`)"; the hold check wants a name.
    return proj.split()[0] if proj else ""


if __name__ == "__main__":
    import json
    import sys
    chosen = pick()
    if chosen is None:
        sys.exit(1)
    print(json.dumps({"id": chosen["id"], "role": chosen["role"],
                      "title": chosen.get("title", "")}))
