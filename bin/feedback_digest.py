#!/usr/bin/env python3
"""Scheduled Telegram digest of widget feedback collected in the last 7 days.

Read-only: summarizes bin/lib/feedback_report.py's output and sends it to
Telegram. Never writes to NEXONE/Notion/NDJSON — same "prep+reminder only"
shape as bin/sprint_reminder.py. Stdlib only.
Usage: feedback_digest.py
"""
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
import feedback_report  # noqa: E402


def env(key):
    v = os.environ.get(key)
    if v:
        return v
    # fallback: read the real .env directly (state.WORKSPACE bug means tgcore can't)
    try:
        for line in open("/home/ahagent/AI-Workspace/.env"):
            line = line.strip()
            if line and not line.startswith("#") and line.split("=", 1)[0].strip() == key:
                return line.split("=", 1)[1].strip()
    except OSError:
        pass
    return ""


def build_message(summary: dict) -> str:
    if not summary:
        return ("📋 <b>Widget feedback — 7 hari terakhir</b>\n"
                "Belum ada aktivitas reviewer minggu ini.")
    lines = ["📋 <b>Widget feedback — 7 hari terakhir</b>"]
    for app in sorted(summary):
        data = summary[app]
        lines.append(f"\n<b>{app}</b>")
        gaps_total = 0
        questions_total = 0
        findings_total = 0
        for r in data["reviewers"].values():
            gaps_total += len(r["clarification_needed"])
            questions_total += r["questions"]
            findings_total += r["findings_recorded"]
        lines.append(
            f"  {len(data['reviewers'])} reviewer, {questions_total} pertanyaan, "
            f"{gaps_total} CLARIFICATION_NEEDED (lubang KB), {findings_total} finding")
        signoff = data["latest_signoff"]
        if signoff:
            lines.append(f"  sign-off terakhir: {signoff['status']} oleh {signoff['by']}")
    return "\n".join(lines)


def main() -> int:
    tok = env("TELEGRAM_BOT_TOKEN")
    chat = (env("TELEGRAM_ALLOWED_CHATS") or "").split(",")[0].strip()
    if not tok or not chat:
        print("TELEGRAM_BOT_TOKEN / TELEGRAM_ALLOWED_CHATS missing", file=sys.stderr)
        return 1

    records = feedback_report.collect_records(feedback_report.DEFAULT_DATA_DIR, None, since_days=7)
    summary = feedback_report.summarize(records)
    msg = build_message(summary)

    data = urllib.parse.urlencode({"chat_id": chat, "text": msg,
                                    "parse_mode": "HTML", "disable_web_page_preview": "true"}).encode()
    r = urllib.request.urlopen(urllib.request.Request(
        f"https://api.telegram.org/bot{tok}/sendMessage", data=data), timeout=30)
    print("sent:", json.loads(r.read()).get("ok"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
