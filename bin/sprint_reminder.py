#!/usr/bin/env python3
"""Scheduled Telegram reminder for daily-update / sprint-report reconciliation.

Prep+reminder only: it NEVER writes to NEXONE/Notion. It nudges the owner to have
the orchestrator session run the full flow (which needs Slack/Notion MCP + Playwright
that an unattended timer does not have). Stdlib only. Usage: sprint_reminder.py daily|weekly
"""
import os, sys, json, urllib.request, urllib.parse

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

kind = sys.argv[1] if len(sys.argv) > 1 else "daily"
tok = env("TELEGRAM_BOT_TOKEN")
chat = (env("TELEGRAM_ALLOWED_CHATS") or "").split(",")[0].strip()
if not tok or not chat:
    sys.exit("TELEGRAM_BOT_TOKEN / TELEGRAM_ALLOWED_CHATS missing")

if kind == "weekly":
    msg = ("⏰ <b>Sprint + Weekly Report</b> — Jumat 07:00 WIB\n"
           "Waktunya rekap sprint/mingguan. Minta saya (AI Assistant): "
           "<b>“proses sprint report”</b> — saya baca #daily-updates + #developments (2 minggu), "
           "rekonsiliasi Sprint di NEXONE via Playwright, buat report di Notion (Doc Hub), lalu lapor ke sini.\n"
           "Sprint 1 tidak diubah. <i>Prep+reminder: tidak menulis ke produksi tanpa konfirmasi Anda.</i>")
else:
    msg = ("⏰ <b>Daily Update</b> — 07:00 WIB\n"
           "Waktunya rekap harian. Minta saya (AI Assistant): <b>“proses daily update”</b> — "
           "saya baca #daily-updates + #developments, rekonsiliasi, dan lapor ke sini.\n"
           "<i>Prep+reminder: tidak menulis ke NEXONE/Notion tanpa konfirmasi Anda.</i>")

data = urllib.parse.urlencode({"chat_id": chat, "text": msg,
                               "parse_mode": "HTML", "disable_web_page_preview": "true"}).encode()
r = urllib.request.urlopen(urllib.request.Request(
    f"https://api.telegram.org/bot{tok}/sendMessage", data=data), timeout=30)
print("sent:", json.loads(r.read()).get("ok"), kind)
