#!/usr/bin/env python3
"""Is the AI Assistant actually able to hear Telegram — not merely "running"?

On 2026-09-21 the owner's messages at 03:23 and 17:49 WIB went unanswered while
every signal said the bridge was fine: the unit was `active (running)`, the tmux
session was up, the Claude Code session had been alive for 31 hours, and the
last notice in the chat was a green "AI Assistant online".

All of that was true and none of it was the question. Inbound messages reach the
session through the channel plugin's MCP server — a `bun` process — and that
process was gone. The session was awake and deaf. `Restart=always` never fired
because tmux, its main process, had not died.

So the health signal has to name the thing that actually carries messages:

    tmux alive  +  claude alive  +  plugin alive  =  can hear you
    tmux alive  +  claude alive  +  plugin GONE   =  looks online, is deaf

`--repair` restarts the unit when the bridge is deaf. Telegram keeps undelivered
updates for about 24 hours, so a restart inside that window still picks up the
messages that were missed rather than losing them.
"""
from __future__ import annotations

import argparse
import subprocess
import sys

UNIT = "ah-channel-telegram"

#: How a running bridge looks in `ps`. The plugin marker is the cache path the
#: channel plugin is started from; matching on "bun" alone would also match an
#: unrelated build.
CLAUDE_MARKER = "claude --channels"
PLUGIN_MARKER = "claude-plugins-official/telegram"

HEALTHY, DEAF, DOWN = "healthy", "deaf", "down"

MESSAGES = {
    DEAF: ("🟠 <b>AI Assistant tuli</b>\n"
           "Sesi hidup, tetapi jalur masuk pesan Telegram mati — pesan yang kamu "
           "kirim tidak akan pernah sampai. Bridge di-restart otomatis; "
           "tunggu notifikasi hijau, lalu kirim ulang pesan terakhirmu."),
    DOWN: ("🔴 <b>AI Assistant mati</b>\n"
           "Sesi tidak berjalan sama sekali. Bridge di-restart otomatis."),
}


def bridge_status(command_lines) -> str:
    """Classify the bridge from a list of running command lines. Pure."""
    lines = list(command_lines or ())
    has_session = any(CLAUDE_MARKER in line for line in lines)
    has_plugin = any(PLUGIN_MARKER in line for line in lines)
    if has_session and has_plugin:
        return HEALTHY
    if has_session:
        return DEAF
    return DOWN


def needs_restart(status: str) -> bool:
    """Only a bridge that cannot deliver messages is worth restarting."""
    return status in (DEAF, DOWN)


def running_commands(user: str = "ahagent") -> list:
    try:
        out = subprocess.run(["pgrep", "-u", user, "-a", "-f", "claude"],
                             capture_output=True, text=True, timeout=20).stdout
    except Exception:
        return []
    return [line for line in out.splitlines() if line.strip()]


def restart_unit() -> bool:
    try:
        proc = subprocess.run(
            ["systemctl", "--user", "restart", UNIT],
            capture_output=True, text=True, timeout=120)
        return proc.returncode == 0
    except Exception:
        return False


def main(argv: list) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repair", action="store_true",
                    help="restart the bridge when it cannot receive messages")
    ap.add_argument("--quiet", action="store_true", help="print nothing when healthy")
    args = ap.parse_args(argv[1:])

    status = bridge_status(running_commands())
    if status == HEALTHY:
        if not args.quiet:
            print("healthy")
        return 0

    print(f"{status}: bridge cannot receive Telegram messages")
    if not args.repair:
        return 1

    # Tell the owner before the restart: the green notice that follows is then
    # a recovery, not a mystery.
    try:
        import channel_notify
        token = channel_notify.read_token()
        for chat in channel_notify.read_recipients():
            if token:
                channel_notify.send(token, chat, MESSAGES[status])
    except Exception:
        pass

    ok = restart_unit()
    print("restart:", "ok" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.path.insert(0, str(__file__.rsplit("/", 1)[0]))
    raise SystemExit(main(sys.argv))
