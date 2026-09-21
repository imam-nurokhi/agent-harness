"""Event detection for Telegram notifications.

Principle: push only what changes a decision. Everything else is available on
request. Events from one poll are batched into a single message.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

import jobs
import state
import tgcore
import trigmem
from tgcore import code, esc

WATCH = tgcore.TG_DIR / "watch.json"
SUMMARY_CHARS = 260

# While the harness is paused, nothing can run at all — the owner asked to
# always be told, but a 25-second poll loop must not turn that into a nag.
# Re-announce at most this often until it recovers.
PAUSE_HEARTBEAT_SECONDS = 30 * 60


def load() -> dict:
    if WATCH.exists():
        try:
            return json.loads(WATCH.read_text())
        except Exception:
            pass
    return {"jobs": {}, "tasks": {}, "quiet": False, "primed": False}


def save(w: dict) -> None:
    tgcore.TG_DIR.mkdir(parents=True, exist_ok=True)
    WATCH.write_text(json.dumps(w, indent=2))


def _persona(role: str) -> str:
    a = next((x for x in state.agents() if x["role"] == role), None)
    return f"{a['glyph']} {a['name']}" if a else role


def _outcome(jid: str) -> str:
    """One meaningful line from a finished run, not the whole transcript."""
    r = jobs.tail(jid, 0)
    body = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", r.get("chunk", ""))
    m = re.search(r"^- Scope done:\s*(.+)$", body, re.M)
    if m:
        return m.group(1).strip()[:SUMMARY_CHARS]
    blocked = re.search(r"^- Not done / blocked:\s*(.+)$", body, re.M)
    if blocked and "none" not in blocked.group(1).lower():
        return "BLOKIR: " + blocked.group(1).strip()[:SUMMARY_CHARS]
    lines = [l.strip() for l in body.splitlines() if l.strip()]
    return (lines[-1][:SUMMARY_CHARS] if lines else "(tidak ada output)")


# A task in flight that nobody has touched for this long has stopped being
# "in progress" and started being a question. Matches weekly.STUCK_DAYS.
STUCK_DAYS = 3

# Once it is stuck it stays stuck, so say it once a day rather than on every
# 25-second poll.
STUCK_REPEAT = 86400.0


def _stuck_task_events(w: dict, now: float | None = None) -> list[str]:
    """Work in flight that has stopped moving.

    Everything else in this module reacts to *progress* -- a run finishing,
    criteria completing. Nothing reacted to the absence of it, so a task could
    stall on Monday and go unmentioned until the Friday report.

    Derived from the task file's mtime, so it costs no engine spend.
    """
    now = time.time() if now is None else now
    seen = w.setdefault("stuck", {})
    events: list[str] = []
    live = set()

    for t in state.tasks():
        if t["status"] not in ("active", "review"):
            continue
        idle = now - (t.get("mtime") or now)
        if idle < STUCK_DAYS * 86400.0:
            continue
        live.add(t["id"])
        last_said = seen.get(t["id"])
        if last_said is not None and now - last_said < STUCK_REPEAT:
            continue
        seen[t["id"]] = now
        days = int(idle // 86400)
        events.append(
            f"⏳ <b>{code(t['id'])} diam {days} hari</b>\n"
            f"{esc(t['title'])} · {esc(t['status'])} · "
            f"{t['criteria_done']}/{t['criteria_total']} kriteria\n"
            + code("/task " + t["id"]))

    # A task that moved again is forgotten, so a second stall alerts at once
    # instead of waiting out the old daily cooldown.
    for tid in [k for k in seen if k not in live]:
        seen.pop(tid)
    return events


def _trigger_events(w: dict) -> list[str]:
    """Scheduled work that failed, or never ran when it should have.

    Both are silent by nature: nobody is watching a 07:00 job at 07:00.
    """
    events: list[str] = []
    # A watch file written before triggers were tracked has no baseline. Record
    # one silently instead of announcing every historic failure at once.
    first_sight = "triggers" not in w
    seen = w.setdefault("triggers", {})

    for tr in state.triggers():
        tid = tr["id"]
        mark = seen.get(tid)
        if not isinstance(mark, dict):
            mark = {}
            seen[tid] = mark

        history = trigmem.runs(tid)
        last = history[-1] if history else None
        if last:
            key = f"{len(history)}|{last['at']}|{last['status']}"
            if mark.get("run") != key:
                mark["run"] = key
                if last["status"] != 0:
                    events.append(
                        f"🛑 <b>Trigger {code(tid)} gagal</b> — exit {last['status']}"
                        f" · {esc(tr['label'] or tid)}\n{esc(last['memo'])}\n"
                        + code(f"ah trigger memo {tid}"))

        if not tr.get("installed"):
            # A trigger the owner deliberately did not install (CLAUDE.md §7:
            # health, drift and sweep each spend engine quota) cannot run, so
            # it cannot be late. Announcing it weekly is noise nobody can act
            # on — and the reader learns to ignore the channel.
            mark.pop("overdue", None)
            continue

        missed = trigmem.overdue(tr["schedule"], tr["last_run"])
        if missed is None:
            mark.pop("overdue", None)
            continue
        key = missed.strftime(trigmem.STAMP)
        if mark.get("overdue") != key:
            mark["overdue"] = key
            events.append(
                f"⏰ <b>Trigger {code(tid)} terlambat</b> — jadwal "
                f"{esc(tr['schedule'])}, seharusnya jalan {esc(key)}.\n"
                f"Terakhir jalan: {esc(tr['last_run'] or 'belum pernah')}\n"
                + code(f"ah trigger run {tid}"))
    return [] if first_sight else events


def _engine_kind_label(engine, kind: str) -> str:
    if kind == getattr(engine, "KIND_REFUSED", "refused"):
        return "ditolak (butuh admin)"
    if kind == getattr(engine, "KIND_LIMITED", "limited"):
        return "limit pemakaian"
    return kind or "tidak tersedia"


def _engine_until(until) -> str:
    if not until:
        return "belum diketahui"
    return time.strftime("%H:%M", time.localtime(until))


def _engine_line(engine, name: str, info: dict) -> str:
    kind = info.get("kind", "")
    reason = str(info.get("reason", "")).strip()[:180]
    line = (f"⚠️ <b>{esc(name)} tidak tersedia</b> — {esc(_engine_kind_label(engine, kind))}\n"
            f"{esc(reason)}\nKembali: {esc(_engine_until(info.get('until')))}")
    if kind == getattr(engine, "KIND_REFUSED", "refused"):
        line += "\n" + code(f"ah engine clear {name}")
    return line


def _paused_message(engine, unavailable: dict) -> str:
    lines = ["⏸️ <b>Harness PAUSED</b> — tidak ada job yang bisa jalan sekarang."]
    for name, info in unavailable.items():
        kind = info.get("kind", "")
        lines.append(f"• {esc(name)}: {esc(_engine_kind_label(engine, kind))}, "
                     f"kembali {esc(_engine_until(info.get('until')))}")
        if kind == getattr(engine, "KIND_REFUSED", "refused"):
            lines.append("  " + code(f"ah engine clear {name}"))
    return "\n".join(lines)


def _engine_events(w: dict) -> list[str]:
    """Report unavailable/recovered engines, and a heartbeat while paused.

    Defensive by design: `engine` is being rewritten alongside this file, so
    any missing function or field must degrade to "no events", not an
    exception that would kill the whole poll loop.
    """
    try:
        import engine
        unavailable = engine.unavailable()
        is_paused = engine.paused()
    except Exception:
        return []

    events: list[str] = []
    # A watch file written before engine health was tracked has no baseline.
    # Record one silently instead of announcing history all at once.
    first_sight = "engines" not in w
    seen = w.setdefault("engines", {})

    for name, info in unavailable.items():
        kind = info.get("kind", "")
        key = f"{kind}|{info.get('until')}"
        prev = seen.get(name)
        seen[name] = key
        if first_sight or prev == key:
            continue
        events.append(_engine_line(engine, name, info))

    for name in [n for n in seen if n not in unavailable]:
        del seen[name]
        if not first_sight:
            events.append(f"✅ <b>{esc(name)} kembali tersedia</b>")

    pause_state = w.setdefault("paused", {"active": False, "last_announced": 0})
    now = time.time()
    if is_paused:
        entering = not pause_state.get("active")
        due = now - pause_state.get("last_announced", 0) >= PAUSE_HEARTBEAT_SECONDS
        pause_state["active"] = True
        if entering or due:
            pause_state["last_announced"] = now
            if not first_sight:
                events.append(_paused_message(engine, unavailable))
    elif pause_state.get("active"):
        pause_state["active"] = False
        pause_state["last_announced"] = 0
        if not first_sight:
            events.append("✅ <b>Harness kembali jalan</b> — ada engine yang tersedia lagi.")

    return events


def detect(w: dict) -> list[str]:
    """Return rendered event lines; mutates `w` with the new baseline."""
    events: list[str] = []

    # --- runs that just finished -------------------------------------------
    seen_jobs = w.setdefault("jobs", {})
    for j in jobs.listing(20):
        prev = seen_jobs.get(j["id"])
        seen_jobs[j["id"]] = j["status"]
        if prev is None or prev == j["status"] or j["status"] == "running":
            continue
        icon = "✅" if j["status"] == "done" else "🛑"
        line = (f"{icon} <b>{_persona(j['role'])}</b> selesai — {j['elapsed']}s"
                + (f" · {code(j['task'])}" if j.get("task") else ""))
        events.append(f"{line}\n{esc(_outcome(j['id']))}\n{code('/tail ' + j['id'])}")

    # --- tasks whose acceptance criteria just completed ---------------------
    seen_tasks = w.setdefault("tasks", {})
    for t in state.tasks():
        key = f"{t['criteria_done']}/{t['criteria_total']}:{t['status']}"
        prev = seen_tasks.get(t["id"])
        seen_tasks[t["id"]] = key
        if prev is None or prev == key:
            continue
        prev_done = int(prev.split("/")[0])
        if (t["criteria_total"] and t["criteria_done"] == t["criteria_total"]
                and prev_done < t["criteria_total"]):
            events.append(f"🎉 <b>{code(t['id'])} semua kriteria terpenuhi</b>\n"
                          f"{esc(t['title'])}\n{code('/task ' + t['id'])}")

    events += _stuck_task_events(w)
    events += _trigger_events(w)
    events += _engine_events(w)

    # Keep the baseline from growing without bound.
    if len(seen_jobs) > 120:
        w["jobs"] = dict(list(seen_jobs.items())[-80:])
    return events


def prime(w: dict) -> None:
    """First run: record current reality so nothing historic is announced."""
    if w.get("primed"):
        return
    w["jobs"] = {j["id"]: j["status"] for j in jobs.listing(20)}
    w["tasks"] = {t["id"]: f"{t['criteria_done']}/{t['criteria_total']}:{t['status']}"
                  for t in state.tasks()}
    w["triggers"] = {}
    _trigger_events(w)   # record the baseline, announce none of it
    _engine_events(w)    # same: baseline the engine/paused state, announce none
    w["primed"] = True
    save(w)


def digest() -> str:
    """On-demand summary — the antidote to streaming every change."""
    d = state.snapshot()
    s = d["summary"]
    running = [j for j in jobs.listing(20) if j["status"] == "running"]
    open_t = [t for t in d["tasks"] if t["status"] != "reported"]

    lines = [f"<b>Ringkasan</b> · {time.strftime('%H:%M')}", ""]
    lines.append(f"Task {s['tasks_total']} · terbuka {len(open_t)} · "
                 f"worktree {len(d['worktrees'])} · disk {d['health']['disk_free_gb']} GB")
    services = d.get("operations", {}).get("services", [])
    if services:
        lines += ["", "<b>Operations</b>"]
        lines += [f"• {esc(item['label'])}: {esc(item['status'])}" for item in services]
        lines.append("Dashboard: " + code("https://agents.nexoratech.co"))
    if running:
        lines += ["", "<b>Berjalan</b>"]
        lines += [f"• {_persona(j['role'])} {code(j['id'])} {j['elapsed']}s" for j in running]
    if open_t:
        lines += ["", "<b>Belum selesai</b>"]
        for t in open_t:
            lines.append(f"• {code(t['id'])} {esc(t['title'][:44])} — "
                         f"{t['criteria_done']}/{t['criteria_total']} AC")
    if not running and not open_t:
        lines += ["", "Semua task tertutup. Tidak ada run berjalan."]
    return "\n".join(lines)


def cmd_digest(_args: str) -> str:
    return digest()


def cmd_quiet(args: str) -> str:
    w = load()
    arg = args.strip().lower()
    if arg in ("on", "aktif"):
        w["quiet"] = True
    elif arg in ("off", "mati"):
        w["quiet"] = False
    else:
        return ("Format: " + code("/quiet on") + " atau " + code("/quiet off") +
                f"\nSaat ini: {'senyap' if w.get('quiet') else 'notifikasi aktif'}")
    save(w)
    return ("🔕 Notifikasi dimatikan. Pakai /digest untuk melihat status."
            if w["quiet"] else "🔔 Notifikasi dinyalakan kembali.")


HANDLERS = {"digest": cmd_digest, "quiet": cmd_quiet}
