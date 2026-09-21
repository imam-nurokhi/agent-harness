#!/usr/bin/env python3
"""Daily sprint report: read NEXONE through a real browser, send it to Telegram.

The owner asked for the Sprint 2/3 summary on a schedule — every weekday at
07:30 WIB. This is the unattended version of the report produced by hand on
2026-09-21.

**Why this is a local timer and not a cloud routine.** A cloud routine runs in
Anthropic's infrastructure with no access to this host: it has no NEXONE
credentials, no Telegram bot token, and no way to reach either without putting
secrets into a stored job config. It could read Slack (there is an MCP
connector) but would have nowhere to deliver the result. The data and the
delivery path both live here, so the schedule lives here too.

**What is in, and what is not.** NEXONE is read through Playwright, driving the
real login form, because the app keeps its token in sessionStorage and because
the owner asked for the live UI rather than a reverse-engineered API client.
Slack is deliberately absent: `SLACK_BOT_TOKEN` is not in `.env`, so an
unattended process cannot read a channel at all. Rather than pretend, the
message says so, and the moment that token exists this script grows a Slack
section (see `slack_note`).

Read-only by construction: no POST/PUT/PATCH/DELETE anywhere.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

WORKSPACE = Path(os.environ.get("AH_WORKSPACE", "/home/ahagent/AI-Workspace"))
ENV_FILE = WORKSPACE / ".env"
BASE = "https://nexone.nexoratech.co"

#: Resolved from the project member list rather than guessed from initials.
USERS = {7: "Imam", 22: "Diky", 15: "Rafif", 16: "Rafly", 9: "Harmanto"}

STATUS_ID = {
    "done": "Selesai", "development": "Dikerjakan", "review": "Review",
    "uat": "UAT", "todo": "Belum mulai", "backlog": "Backlog",
    "deploy_to_production": "Menuju produksi",
}


def env(name: str, path: Path | None = None) -> str:
    """Read one key from the workspace .env. The unit also loads it, but the
    script must work when run by hand, which is how it gets debugged."""
    if os.environ.get(name):
        return os.environ[name].strip()
    try:
        for line in (path or ENV_FILE).read_text(errors="replace").splitlines():
            line = line.strip()
            if line.startswith(f"{name}="):
                return line.split("=", 1)[1].strip().strip("'\"")
    except OSError:
        pass
    return ""


# --------------------------------------------------------------------------
# Formatting. Pure, so the message can be tested without a browser or network.
# --------------------------------------------------------------------------

def active_and_last_completed(sprints: list) -> tuple:
    """(active, last_completed). The two sprints a standup actually cares about.

    Picking by name ("Sprint 3") would break the day someone names one
    differently; picking by status and date does not.
    """
    def unwrap(row):
        return row.get("sprint", row)

    rows = [unwrap(r) for r in (sprints or [])]
    active = [s for s in rows if s.get("status") == "active"]
    done = [s for s in rows if s.get("status") == "completed"]
    active.sort(key=lambda s: s.get("start_date") or "")
    done.sort(key=lambda s: s.get("end_date") or "")
    return (active[-1] if active else None), (done[-1] if done else None)


def summary_of(row: dict) -> dict:
    return (row or {}).get("summary") or {}


def open_tasks(sprint: dict) -> list:
    """Every task not finished, newest blockers first by points."""
    out = []
    for link in (sprint or {}).get("tasks") or []:
        task = link.get("task") or {}
        if task.get("status") == "done":
            continue
        who = ", ".join(USERS.get(a.get("user_id"), f"user {a.get('user_id')}")
                        for a in task.get("assignees") or []) or "—"
        out.append({
            "title": task.get("title", "?"),
            "status": STATUS_ID.get(task.get("status"), task.get("status", "?")),
            "who": who,
            "points": task.get("total_points") or 0,
            "project": (link.get("project") or {}).get("name", "?"),
        })
    out.sort(key=lambda t: -t["points"])
    return out


def esc(text) -> str:
    return (str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def slack_note(has_slack_token: bool) -> str:
    if has_slack_token:
        return ""
    return ("\n<i>Bagian Slack belum termasuk: token bot Slack belum ada di "
            "<code>.env</code>, jadi proses terjadwal tidak bisa membaca kanal. "
            "Tambahkan <code>SLACK_BOT_TOKEN</code> untuk mengaktifkannya.</i>")


def build_message(sprints: list, has_slack_token: bool = False, limit: int = 6) -> str:
    active, completed = active_and_last_completed(sprints)
    if not active and not completed:
        return ("📋 <b>Laporan sprint</b>\n\nTidak ada sprint aktif maupun sprint "
                "selesai yang terbaca di NEXONE hari ini." + slack_note(has_slack_token))

    lines = ["📋 <b>Laporan Sprint — NEXONE</b>"]

    if active:
        s = summary_of(_row_for(sprints, active))
        done, total = s.get("done_tasks", 0), s.get("total_tasks", 0)
        dp, tp = s.get("done_points", 0), s.get("total_points", 0)
        lines.append(f"\n<b>{esc(active.get('name'))}</b> — berjalan "
                     f"({str(active.get('start_date', ''))[:10]} → "
                     f"{str(active.get('end_date', ''))[:10]})")
        lines.append(f"{done}/{total} tugas · {dp}/{tp} poin · "
                     f"<b>{s.get('progress', 0)}%</b>")
        if s.get("overdue_tasks"):
            lines.append(f"⚠️ {s['overdue_tasks']} tugas lewat tenggat")

        remaining = open_tasks(active)
        if remaining:
            lines.append(f"\n<b>Belum selesai ({len(remaining)}):</b>")
            for t in remaining[:limit]:
                lines.append(f"• [{esc(t['status'])}] {esc(t['title'])} — "
                             f"{esc(t['who'])} · {t['points']}p")
            if len(remaining) > limit:
                lines.append(f"…dan {len(remaining) - limit} lagi")

    if completed:
        s = summary_of(_row_for(sprints, completed))
        carried = open_tasks(completed)
        lines.append(f"\n<b>{esc(completed.get('name'))}</b> — selesai di "
                     f"{s.get('progress', 0)}% ({s.get('done_tasks', 0)}/"
                     f"{s.get('total_tasks', 0)} tugas)")
        if carried:
            projects = sorted({t["project"] for t in carried})
            where = projects[0] if len(projects) == 1 else f"{len(projects)} produk"
            lines.append(f"Sisa {len(carried)} tugas, semuanya di {esc(where)}")

    lines.append(f"\n{BASE}/internal-project/sprints")
    return "\n".join(lines) + slack_note(has_slack_token)


def _row_for(sprints: list, sprint: dict) -> dict:
    for row in sprints or []:
        if (row.get("sprint", row)).get("id") == sprint.get("id"):
            return row
    return {}


# --------------------------------------------------------------------------
# The parts that touch the world.
# --------------------------------------------------------------------------

def fetch_sprints() -> list:
    """Log in through the real form, then ask the app's own API from inside it."""
    from playwright.sync_api import sync_playwright

    email, password = env("NEXONE_EMAIL"), env("NEXONE_PASSWORD")
    if not email or not password:
        raise RuntimeError("NEXONE_EMAIL/NEXONE_PASSWORD tidak ada di .env")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        try:
            page.goto(f"{BASE}/login", wait_until="networkidle", timeout=60000)
            page.locator("input[type=email]:visible, input[name=email]:visible").first.fill(email)
            page.locator("input[type=password]:visible").first.fill(password)
            page.locator("button[type=submit]:visible").first.click()
            page.wait_for_load_state("networkidle", timeout=60000)
            page.wait_for_timeout(2500)

            token = ""
            for key in page.evaluate("() => Object.keys(sessionStorage)"):
                value = page.evaluate(
                    "k => sessionStorage.getItem(k)", key)
                if isinstance(value, str) and value.count(".") == 2 and len(value) > 40:
                    token = value
                    break
            if not token:
                raise RuntimeError("login NEXONE gagal: token tidak ditemukan")

            res = page.evaluate(
                """async ([p, t]) => {
                    const r = await fetch(p, {headers: {Authorization: 'Bearer ' + t,
                                                        Accept: 'application/json'}});
                    return {status: r.status, body: await r.text()};
                }""", ["/api/v1/internal-projects/sprints", token])
            if res["status"] != 200:
                raise RuntimeError(f"NEXONE menjawab {res['status']}")
            data = json.loads(res["body"])
            return data.get("data") if isinstance(data, dict) else data
        finally:
            browser.close()


def send_telegram(text: str) -> bool:
    token, chat = env("TELEGRAM_BOT_TOKEN"), env("TELEGRAM_ALLOWED_CHATS").split(",")[0].strip()
    if not token or not chat:
        print("telegram: token atau chat id tidak ada", file=sys.stderr)
        return False
    payload = urllib.parse.urlencode({
        "chat_id": chat, "text": text[:4000], "parse_mode": "HTML",
        "disable_web_page_preview": "true"}).encode()
    try:
        with urllib.request.urlopen(
                f"https://api.telegram.org/bot{token}/sendMessage",
                data=payload, timeout=30) as resp:
            return resp.status == 200
    except Exception as exc:
        print(f"telegram gagal: {exc}", file=sys.stderr)
        return False


def main(argv: list) -> int:
    dry = "--dry-run" in argv
    try:
        sprints = fetch_sprints()
    except Exception as exc:
        # A scheduled report that fails silently is the failure mode this whole
        # workspace keeps relearning. Tell the owner, then exit non-zero.
        message = f"⚠️ <b>Laporan sprint gagal</b>\nNEXONE tidak bisa dibaca: {esc(exc)}"
        print(message, file=sys.stderr)
        if not dry:
            send_telegram(message)
        return 1

    text = build_message(sprints, has_slack_token=bool(env("SLACK_BOT_TOKEN")))
    if dry:
        print(text)
        return 0
    return 0 if send_telegram(text) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
