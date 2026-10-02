"""Cross-run memory for scheduled triggers.

Every trigger fires in its own session with no history, so without this each run
re-derives the same state from scratch and nothing accumulates. A run leaves one
line behind; the next run is handed it before it starts.

Also answers the other half: was a trigger supposed to have run by now?
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
from pathlib import Path

WORKSPACE = Path(os.environ.get("AH_WORKSPACE", Path.home() / "AI-Workspace"))
MEMORY = WORKSPACE / "agents" / "memory" / "trigger-runs.json"

KEEP = 5
MEMO_CHARS = 400
GRACE_MINUTES = 120
STAMP = "%Y-%m-%d %H:%M"

# Python's weekday(): Monday is 0.
WEEKDAYS = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}

ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def _load() -> dict:
    try:
        return json.loads(MEMORY.read_text())
    except Exception:
        return {}


def _save(data: dict) -> None:
    MEMORY.parent.mkdir(parents=True, exist_ok=True)
    MEMORY.write_text(json.dumps(data, indent=2))


def extract_memo(text: str) -> str:
    """The agent is asked to end with `MEMO: ...`; fall back to its last line."""
    found = re.findall(r"^\s*MEMO:\s*(.+)$", text, re.M)
    memo = found[-1] if found else ""
    if not memo:
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        memo = lines[-1] if lines else "(tidak ada output)"
    return ANSI.sub("", memo).strip()[:MEMO_CHARS]


def record(tid: str, status: int, log_path: str | None = None,
           memo: str | None = None, now: dt.datetime | None = None) -> dict:
    if memo is None:
        text = ""
        if log_path:
            try:
                text = Path(log_path).read_text(errors="replace")
            except OSError:
                text = ""
        memo = extract_memo(text)
    entry = {
        "at": (now or dt.datetime.now()).strftime(STAMP),
        "status": int(status),
        "memo": memo,
        "log": Path(log_path).name if log_path else "",
    }
    data = _load()
    history = data.setdefault(tid, [])
    history.append(entry)
    del history[:-KEEP]
    _save(data)
    return entry


def runs(tid: str) -> list[dict]:
    return _load().get(tid, [])


def latest(tid: str) -> dict | None:
    history = runs(tid)
    return history[-1] if history else None


def recall(tid: str, limit: int = 3) -> str:
    """The block injected into the next run's prompt. Empty when there is no history."""
    history = runs(tid)[-limit:]
    if not history:
        return ""
    lines = ["PREVIOUS RUNS (terlama ke terbaru). Pakai ini; jangan turunkan ulang apa "
             "yang sudah diketahui. Laporkan apa yang BERUBAH sejak run terakhir."]
    for e in history:
        flag = "ok" if e["status"] == 0 else f"GAGAL exit {e['status']}"
        lines.append(f"- {e['at']} [{flag}] {e['memo']}")
    return "\n".join(lines)


def _parse_stamp(value: str) -> dt.datetime | None:
    try:
        return dt.datetime.strptime(value.strip(), STAMP)
    except Exception:
        return None


def expected_fire(schedule: str, now: dt.datetime) -> dt.datetime | None:
    """The most recent moment this schedule should have fired, or None when the
    schedule carries no clock time we can read."""
    text = (schedule or "").strip().lower()
    match = re.search(r"(\d{1,2}):(\d{2})", text)
    if not match:
        return None
    hour, minute = int(match.group(1)), int(match.group(2))
    if hour > 23 or minute > 59:
        return None

    weekday = next((num for name, num in WEEKDAYS.items() if name in text), None)
    at_time = {"hour": hour, "minute": minute, "second": 0, "microsecond": 0}

    if weekday is None:
        fire = now.replace(**at_time)
        return fire if fire <= now else fire - dt.timedelta(days=1)

    back = (now.weekday() - weekday) % 7
    fire = (now - dt.timedelta(days=back)).replace(**at_time)
    return fire if fire <= now else fire - dt.timedelta(days=7)


def overdue(schedule: str, last_run: str, now: dt.datetime | None = None,
            grace_minutes: int = GRACE_MINUTES) -> dt.datetime | None:
    """The fire time that was missed, or None when the schedule is on track.

    The grace period keeps a slow trigger from being reported as missed while it
    is still working.
    """
    now = now or dt.datetime.now()
    fire = expected_fire(schedule, now)
    if fire is None or now < fire + dt.timedelta(minutes=grace_minutes):
        return None
    last = _parse_stamp(last_run or "")
    if last and last >= fire:
        return None
    return fire


def _cli(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: trigmem.py {recall|record|show} <trigger-id> [...]", file=sys.stderr)
        return 2
    cmd, tid = argv[0], argv[1]
    if cmd == "recall":
        block = recall(tid)
        if block:
            print(block)
    elif cmd == "record":
        record(tid, int(argv[2]), argv[3] if len(argv) > 3 else None)
    elif cmd == "show":
        history = runs(tid)
        if not history:
            print(f"no recorded runs for trigger '{tid}'")
            return 0
        for e in history:
            flag = "ok     " if e["status"] == 0 else f"exit {e['status']:<3}"
            print(f"{e['at']}  {flag}  {e['memo']}")
    else:
        print(f"unknown command: {cmd}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
