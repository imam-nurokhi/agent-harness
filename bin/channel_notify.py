#!/usr/bin/env python3
"""Tell the owner on Telegram when the channel bridge goes up or down.

The bridge is a Claude Code session in tmux (`ah-channel-telegram`). When it
stops -- because someone typed `/exit` in the pane, because it crashed, or
because the unit was stopped -- Telegram simply goes quiet: the plugin's MCP
server dies with the session and nothing is ever sent again. Silence is the
worst possible failure signal for a chat surface, so systemd calls this script
from ExecStartPost/ExecStopPost and the owner is told either way.

It deliberately does NOT use bin/lib/tgcore.py: that module speaks for
@AgentNexoraBot, whose token lives in the workspace .env. This notice belongs
to @AskNexAIBot, the channel's own bot, whose token lives only in
~/.claude/channels/telegram/.env (ops/channels/README.md explains why the two
tokens must never meet). Recipients come from the channel's own allowlist, so a
chat that was never paired is never messaged.

Never fails the unit: every error path still exits 0.
"""
from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

CHANNEL_DIR = Path.home() / ".claude" / "channels" / "telegram"
ENV_FILE = CHANNEL_DIR / ".env"
ACCESS_FILE = CHANNEL_DIR / "access.json"
TIMEOUT = 10

MESSAGES = {
    "up": "🟢 <b>AI Assistant online</b>\nSesi Claude Code tersambung lagi. Silakan lanjut bertanya.",
    "down": (
        "🔴 <b>AI Assistant terputus</b>\n"
        "Sesi berhenti (mis. perintah <code>/exit</code>, crash, atau restart).\n"
        "Unit <code>ah-channel-telegram</code> memakai <code>Restart=always</code>, "
        "jadi sesi baru biasanya online lagi dalam ~10 detik — tunggu notifikasi hijau."
    ),
}


def read_token(env_file: Path = ENV_FILE) -> str:
    """The channel bot's token, from the plugin's own .env. '' when absent."""
    try:
        text = env_file.read_text(errors="replace")
    except OSError:
        return ""
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition("=")
        if key.strip() == "TELEGRAM_BOT_TOKEN":
            return value.strip().strip("'\"")
    return ""


def read_recipients(access_file: Path = ACCESS_FILE) -> list:
    """Chats allowed to talk to the channel -- the only ones we may notify."""
    try:
        data = json.loads(access_file.read_text(errors="replace"))
    except (OSError, ValueError):
        return []
    if not isinstance(data, dict):
        return []
    out = []
    for chat in data.get("allowFrom") or []:
        chat = str(chat).strip()
        if chat and chat not in out:
            out.append(chat)
    return out


def send(token: str, chat_id: str, text: str) -> bool:
    payload = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": "true",
    }).encode()
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        with urllib.request.urlopen(url, data=payload, timeout=TIMEOUT) as resp:
            return resp.status == 200
    except Exception:
        return False


def main(argv: list) -> int:
    event = (argv[1] if len(argv) > 1 else "").strip().lower()
    if event not in MESSAGES:
        print(f"channel_notify: unknown event {event!r}; expected up|down")
        return 0
    token = read_token()
    if not token:
        print("channel_notify: no channel bot token; nothing sent")
        return 0
    recipients = read_recipients()
    if not recipients:
        print("channel_notify: allowlist empty; nothing sent")
        return 0
    for chat in recipients:
        ok = send(token, chat, MESSAGES[event])
        print(f"channel_notify: {event} -> {chat}: {'sent' if ok else 'FAILED'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
