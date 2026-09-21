"""Deterministic weekly report for the Friday management meeting.

The plan asks for "report deterministik ... dari data yang sudah disetujui", so
this is computed from harness state rather than written by an agent: it costs no
engine spend, it cannot claim a task shipped when it did not, and the same input
always renders the same text. Anything it cannot derive, it says it cannot
derive.

collect() is pure data and render() is pure presentation, so the numbers can be
tested without parsing Telegram markup.
"""
from __future__ import annotations

import datetime as dt
import html

WINDOW_DAYS = 7

# An active task nobody has touched for this long has stopped being "in
# progress" and started being a question for the meeting.
STUCK_DAYS = 3

IN_FLIGHT = ("active", "review")
DAY = 86400.0

# Telegram rejects a message over 4096 characters, and a management summary
# nobody scrolls is not a summary. Sections list this many and then count.
MAX_ITEMS = 8

# "Completed this week" is derived from file mtime. After a bulk copy, restore
# or rsync every mtime is recent, and the window would swallow the entire
# backlog. When almost every reported task lands in one week, the evidence is
# an artefact rather than a delivery record -- and the report says so.
SUSPECT_RATIO = 0.9
SUSPECT_MIN = 5


def _esc(text: object) -> str:
    return html.escape(str(text), quote=False)


def _stamp(epoch: float) -> str:
    # UTC, matching the server clock the schedules are expressed against, so a
    # date in the report can be checked directly against the harness logs.
    return dt.datetime.fromtimestamp(epoch, dt.timezone.utc).strftime("%Y-%m-%d")


def collect(snapshot: dict, job_list: list[dict], now: float,
            days: int = WINDOW_DAYS) -> dict:
    """Everything the report states, derived and nothing more."""
    since = now - days * DAY
    tasks = snapshot.get("tasks") or []

    shipped = [t for t in tasks
               if t.get("status") == "reported" and (t.get("mtime") or 0) >= since]
    in_flight = [t for t in tasks if t.get("status") in IN_FLIGHT]
    queued = [t for t in tasks if t.get("status") == "planned"]

    # Only work that is supposed to be moving can be stuck. A planned task
    # sitting still is a backlog item, not a problem.
    stuck = [t for t in in_flight
             if (now - (t.get("mtime") or now)) >= STUCK_DAYS * DAY]

    recent = [j for j in job_list if (j.get("started") or 0) >= since]
    failed_runs = [j for j in recent if j.get("status") == "failed"]

    attention = [s for s in (snapshot.get("operations") or {}).get("services") or []
                 if s.get("status") not in {"ok", "ready"}]

    all_reported = [t for t in tasks if t.get("status") == "reported"]
    mtime_suspect = (len(all_reported) >= SUSPECT_MIN
                     and len(shipped) >= SUSPECT_RATIO * len(all_reported))

    refused = (snapshot.get("engines") or {}).get("refused") or {}
    engine_risks = [{"engine": name, "reason": (info or {}).get("reason", "")}
                    for name, info in sorted(refused.items())]

    return {
        "period": f"{_stamp(since)} … {_stamp(now)}",
        "generated": _stamp(now),
        "shipped": shipped,
        "in_flight": in_flight,
        "queued": queued,
        "stuck": stuck,
        "reported_total": len(all_reported),
        "mtime_suspect": mtime_suspect,
        "runs_done": sum(1 for j in recent if j.get("status") == "done"),
        "runs_total": len(recent),
        "failed_runs": failed_runs,
        "attention": attention,
        "engine_risks": engine_risks,
    }


def _task_line(t: dict) -> str:
    bits = [f"<code>{_esc(t.get('id'))}</code>", _esc(t.get("title") or t.get("id"))]
    if t.get("criteria_total"):
        bits.append(f"({t.get('criteria_done', 0)}/{t['criteria_total']} kriteria)")
    role = t.get("role")
    if role:
        bits.append(f"· {_esc(role)}")
    return "• " + " ".join(bits)


def _section(title: str, items: list, line, empty: str) -> list[str]:
    out = [f"<b>{title}</b>"]
    if not items:
        out.append(empty)
    else:
        out += [line(i) for i in items[:MAX_ITEMS]]
        if len(items) > MAX_ITEMS:
            out.append(f"… dan {len(items) - MAX_ITEMS} lainnya")
    out.append("")
    return out


def render(data: dict) -> str:
    lines = [
        "<b>Weekly report — manajemen</b>",
        f"Periode {data['period']} · dihasilkan {data['generated']}",
        "Angka di bawah diturunkan dari state harness, bukan estimasi.",
        "",
    ]

    lines += _section(
        f"✅ Selesai minggu ini ({len(data['shipped'])})",
        data["shipped"], _task_line, "Tidak ada task yang selesai dalam periode ini.")

    if data["mtime_suspect"]:
        lines.append(
            f"⚠️ {data['shipped'] and len(data['shipped'])} dari "
            f"{data['reported_total']} task reported jatuh di periode ini. "
            "Tanggal selesai diturunkan dari <code>mtime</code> berkas, jadi "
            "angka itu kemungkinan artefak penyalinan workspace, bukan catatan "
            "delivery. Jangan dipakai di meeting tanpa dicek.")
        lines.append("")

    lines += _section(
        f"🔨 Sedang berjalan ({len(data['in_flight'])})",
        data["in_flight"], _task_line, "Tidak ada task yang sedang berjalan.")

    lines += _section(
        f"⚠️ Mandek ≥{STUCK_DAYS} hari ({len(data['stuck'])})",
        data["stuck"], _task_line, "Tidak ada task yang mandek.")

    lines += _section(
        f"📋 Antrian ({len(data['queued'])})",
        data["queued"], _task_line, "Antrian kosong.")

    lines.append("<b>🔧 Operasi</b>")
    lines.append(f"Run minggu ini: {data['runs_total']} "
                 f"({data['runs_done']} selesai, {len(data['failed_runs'])} gagal)")
    if data["failed_runs"]:
        for j in data["failed_runs"]:
            task_ref = f" · <code>{_esc(j['task'])}</code>" if j.get("task") else ""
            lines.append(f"• gagal <code>{_esc(j.get('id'))}</code>{task_ref}")
    if data["attention"]:
        for s in data["attention"]:
            detail = f" — {_esc(s['detail'])}" if s.get("detail") else ""
            lines.append(f"• {_esc(s.get('label') or s.get('id'))}: "
                         f"{_esc(s.get('status'))}{detail}")
    if data["engine_risks"]:
        for e in data["engine_risks"]:
            lines.append(f"• engine <code>{_esc(e['engine'])}</code> ditolak — "
                         f"{_esc(e['reason'])}")
    if not (data["failed_runs"] or data["attention"] or data["engine_risks"]):
        lines.append("Tidak ada layanan atau engine yang perlu perhatian.")

    lines += ["", "Detail per task: <code>/task &lt;id&gt;</code>. "
                  "Papan lengkap: <code>/kanban</code>."]
    return "\n".join(lines)


def report(snapshot: dict, job_list: list[dict], now: float,
           days: int = WINDOW_DAYS) -> str:
    return render(collect(snapshot, job_list, now, days))
