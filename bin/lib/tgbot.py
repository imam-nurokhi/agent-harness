"""Telegram control daemon for the agent harness.

Long-polls Telegram, authorises by chat id, dispatches commands, and pushes a
notification when a run finishes. Only paired chats may control anything.
"""
from __future__ import annotations

import re
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import jobs      # noqa: E402
import state     # noqa: E402
import tgcmd     # noqa: E402
import tgcore    # noqa: E402
import tgtask    # noqa: E402
import tgwatch   # noqa: E402
from tgcore import code, esc  # noqa: E402

POLL = 25
NOTIFY_TAIL = 1400
COMMAND_LEVELS = {
    # Aggregated read-only status is safe for a paired viewer.
    "help": "viewer", "start": "viewer", "status": "viewer", "agents": "viewer",
    "jobs": "viewer", "brief": "viewer", "reporting": "viewer", "ops": "viewer",
    "sources": "viewer", "reminders": "viewer", "support": "viewer", "deploy": "viewer",
    "monitor": "viewer",
    # Detailed task and execution data is restricted to an operator.
    "kanban": "operator", "board": "operator", "tasks": "operator", "task": "operator",
    "tail": "operator", "diff": "operator", "report": "operator", "log": "operator",
    "digest": "operator", "triggers": "operator", "engine": "operator",
    "weekly": "operator", "daily": "operator",
    # Harness changes, execution, diagnostics, and access management require owner.
    "new": "owner", "assign": "owner", "ac": "owner", "tick": "owner", "wt": "owner",
    "note": "owner", "close": "owner", "run": "owner", "ask": "owner", "stop": "owner",
    "trigger": "owner", "quiet": "owner", "push": "owner", "doctor": "owner", "resume": "owner",
    "grant": "owner",
    # GitHub writes. Owner-only twice over: the command needs owner, and the
    # merge button re-checks the tapper's role in tggh.handle_callback.
    "pr": "owner", "prs": "owner", "merge": "owner",
}


# /help tells the reader to check their role with /status, so both must say it.
ROLE_BANNER_COMMANDS = ("status", "help", "start")

def _role_banner(cfg: dict, chat_id: int) -> str:
    """One line naming this chat's role, and what it still cannot reach.

    /help groups commands by role, so a reader needs to know which group is
    theirs. Handlers never see the chat id -- they take only the argument
    string -- so this is appended at dispatch, the same way _engine_banner() is.
    The ordering comes from tgcore.ROLE_LEVELS rather than a second copy here.
    """
    role = tgcore.role_for(cfg, chat_id)
    if role is None:
        return ""
    line = f"\n\nRole chat ini: <b>{esc(role)}</b>."
    higher = tgcore.ROLE_LEVELS[tgcore.ROLE_LEVELS.index(role) + 1:]
    if higher:
        line += (" Perintah di bagian "
                 + " dan ".join(f"<b>{esc(h)}</b>" for h in higher)
                 + " memerlukan akses lebih tinggi.")
    return line


def _engine_banner() -> str:
    """A line per engine this account has been refused, with the exact fix.

    Appended to /status and /doctor so the operator learns about a disabled
    engine from the chat they already read, not only from a red job card.
    """
    refused = state.engines().get("refused") or {}
    if not refused:
        return ""
    lines = ["", "⚠️ <b>Engine issues</b>"]
    for name, info in refused.items():
        reason = (info.get("reason") or "").strip()[:160]
        lines.append(f"{code(name)} — {esc(reason)}")
        lines.append(f"    fix: {code('ah engine clear ' + name)}")
    return "\n".join(lines)


def _announce_pairing(cfg: dict) -> str:
    codeval = cfg.get("pair_code") or tgcore.new_pair_code(cfg)
    print("\n  Telegram bot: @KaraImamiBot")
    print("  No chat is paired yet. From your phone, message the bot:")
    print(f"\n      /pair {codeval}\n")
    print("  Only a paired chat can control the harness.\n")
    return codeval


def _handle_pair(cfg: dict, chat_id: int, args: str, username: str) -> str:
    given = args.strip().split()[0] if args.strip() else ""
    want = cfg.get("pair_code")
    if not want:
        return "Pairing sedang tidak dibuka."
    if given != want:
        return "Kode pairing salah."
    allowed = set(cfg.get("allowed", []))
    role = "owner" if not tgcore.owner_chat_ids(cfg) else "viewer"
    allowed.add(chat_id)
    cfg["allowed"] = sorted(allowed)
    roles = dict(cfg.get("roles", {}))
    roles[str(chat_id)] = role
    cfg["roles"] = roles
    cfg["pair_code"] = None          # single use
    tgcore.save_config(cfg)
    print(f"  paired: chat_id={chat_id} ({username})")
    return (f"✅ Terhubung sebagai <b>{role}</b>.\n\n" + tgcmd.cmd_help(""))


def _handle_grant(cfg: dict, actor_chat_id: int, args: str) -> str:
    """Owner-only role mutation for an already paired chat."""
    parts = args.split()
    if len(parts) != 2 or not parts[0].lstrip("-").isdigit():
        return "Format: " + code("/grant <chat-id> <viewer|operator|owner>")
    target_chat_id = int(parts[0])
    try:
        tgcore.grant_role(cfg, target_chat_id, parts[1].lower())
    except ValueError as exc:
        return "❌ " + esc(str(exc))
    tgcore.save_config(cfg)
    return f"✅ {code(target_chat_id)} sekarang memiliki role <b>{esc(parts[1].lower())}</b>."


def _notify(cfg: dict) -> None:
    """One batched message per poll, and only for events that matter."""
    targets = tgcore.notification_targets(cfg)
    if not targets:
        return
    w = tgwatch.load()
    tgwatch.prime(w)
    events = tgwatch.detect(w)
    tgwatch.save(w)
    if not events or w.get("quiet"):
        return
    body = "\n\n".join(events[:6])
    if len(events) > 6:
        body += f"\n\n… dan {len(events) - 6} peristiwa lain. /digest"
    for chat in targets:
        tgcore.send(chat, body)


def _dispatch(cfg: dict, msg: dict) -> None:
    chat = msg.get("chat") or {}
    chat_id = chat.get("id")
    text = (msg.get("text") or "").strip()
    username = chat.get("username") or chat.get("first_name") or "?"
    if not chat_id:
        return

    # Plain text used to be dropped here, which made the bot look broken to
    # anyone who typed a question instead of a command. It is now a development
    # request: same permissions, same approval gates, just no slash.
    if not text.startswith("/"):
        if not tgcore.is_allowed(cfg, chat_id):
            return
        if not tgcore.has_level(cfg, chat_id, "owner"):
            tgcore.send(chat_id, "⛔ Tanya-jawab bebas memerlukan role <b>owner</b>.")
            return
        import tgchat
        reply = tgchat.handle(chat_id, text)
        if reply:
            tgcore.send(chat_id, reply)
        return

    raw, _, args = text.partition(" ")
    cmd = raw.lstrip("/").split("@")[0].lower()

    if cmd == "pair":
        tgcore.send(chat_id, _handle_pair(cfg, chat_id, args, username))
        return

    if not tgcore.is_allowed(cfg, chat_id):
        tgcore.send(chat_id,
                    "⛔ Chat ini belum terhubung ke harness.\n"
                    "Jalankan <code>ah bot pair</code> di Mac untuk mendapat kode, "
                    "lalu kirim <code>/pair &lt;kode&gt;</code>.")
        print(f"  denied: chat_id={chat_id} ({username}) cmd=/{cmd}")
        return

    required = COMMAND_LEVELS.get(cmd, "owner")
    if not tgcore.has_level(cfg, chat_id, required):
        print(f"  denied-role: chat_id={chat_id} ({username}) cmd=/{cmd} required={required}")
        tgcore.send(chat_id, f"⛔ {code('/' + cmd)} memerlukan role <b>{required}</b>.")
        return

    if cmd == "grant":
        tgcore.send(chat_id, _handle_grant(cfg, chat_id, args))
        return

    # /merge needs to know which chat to put the Approve button in, so it takes
    # chat_id where every other handler takes only its arguments.
    if cmd == "merge":
        import tggh
        result = tggh.cmd_merge(args, chat_id)
        if result:
            tgcore.send(chat_id, result)
        return

    handler = (tgcmd.HANDLERS.get(cmd) or tgtask.HANDLERS.get(cmd)
               or tgwatch.HANDLERS.get(cmd))
    if not handler:
        tgcore.send(chat_id, f"Perintah tidak dikenal: {code('/' + cmd)}\nCoba /help")
        return

    try:
        result = handler(args)
        # A handler may ask to send a file instead of text: ("__DOC__", path,
        # caption). The guard against leaking secrets lives in tgfiles, not here.
        if isinstance(result, tuple) and result and result[0] == "__DOC__":
            import tgfiles
            _, path, caption = result
            res = tgfiles.send_document(chat_id, path, caption)
            if not res.get("ok"):
                tgcore.send(chat_id, esc(res.get("description", "gagal mengirim berkas")))
            return
        if cmd in ("status", "doctor"):
            result += _engine_banner()
        if cmd in ROLE_BANNER_COMMANDS:
            result += _role_banner(cfg, chat_id)
        tgcore.send(chat_id, result)
    except Exception:
        traceback.print_exc()
        tgcore.send(chat_id, f"Terjadi error menjalankan {code('/' + cmd)}.")


def main() -> None:
    cfg = tgcore.load_config()
    me = tgcore.call("getMe", timeout=15)
    if not me.get("ok"):
        raise SystemExit(f"Telegram rejected the token: {me.get('description')}")
    uname = me["result"]["username"]

    tgcore.set_commands_full()
    tgwatch.prime(tgwatch.load())

    if not cfg.get("allowed") and not tgcore.allowed_from_env():
        _announce_pairing(cfg)
    else:
        print(f"\n  Telegram bot @{uname} live. "
              f"Paired chats: {cfg.get('allowed') or tgcore.allowed_from_env()}\n")

    offset = cfg.get("offset", 0)
    while True:
        try:
            updates = tgcore.get_updates(offset, POLL)
            for u in updates:
                offset = max(offset, u["update_id"] + 1)
                msg = u.get("message") or u.get("edited_message")
                if msg:
                    cfg = tgcore.load_config()
                    _dispatch(cfg, msg)
                cq = u.get("callback_query")
                if cq:
                    # The merge Approve/Deny buttons. Role is re-checked inside,
                    # because a button can be tapped by anyone the message
                    # reaches, not only by whoever ran /merge.
                    import tggh
                    tggh.handle_callback(tgcore.load_config(), cq)
            if updates:
                cfg = tgcore.load_config()
                cfg["offset"] = offset
                tgcore.save_config(cfg)

            _notify(tgcore.load_config())
        except KeyboardInterrupt:
            print("\n  bot stopped\n")
            return
        except Exception:
            traceback.print_exc()
            time.sleep(5)


if __name__ == "__main__":
    main()
