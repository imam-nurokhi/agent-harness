"""Telegram surface for the GitHub flow: push a branch, open a PR, approve a merge.

The owner's rule (2026-09-19) is that a merge into `dev` happens only when they
tap Approve in Telegram. That tap is the *only* path: ghflow.merge() refuses
without an approval file, and the file is written here and nowhere else.

Split of concerns:
  ghflow.py  -- the rules and the GitHub calls, tested offline
  tggh.py    -- how those rules look in a chat, and who is allowed to tap

Handlers return a string like every other command in tgcmd.HANDLERS. The merge
button is the one exception that needs more than text, so it sends its own
message with an inline keyboard.
"""
from __future__ import annotations

import json

import ghflow
import tgcore
from tgcore import code, esc

#: Callback payloads are "gh:a:<token>" / "gh:x:<token>" -- Telegram caps
#: callback_data at 64 bytes, so the repo and PR number live in the staged file.
CB_APPROVE = "gh:a:"
CB_CANCEL = "gh:x:"


def _repos_hint() -> str:
    return "Organisasi yang diizinkan: " + ", ".join(code(o) for o in ghflow.ORGS)


def cmd_push(args: str) -> str:
    """/push <task-id> <org/repo> [judul PR] — branch baru + PR ke dev.

    Not "push to dev" any more. The worktree's HEAD goes to a freshly minted
    ah/ branch, and a pull request against dev is opened in the same step,
    because a pushed branch nobody reviews is how work used to reach dev by
    accident.
    """
    import pushgate

    parts = args.strip().split(None, 2)
    if len(parts) < 2:
        return ("Format: " + code("/push <task-id> <org/repo> [judul]") +
                "\nContoh: " + code("/push task-005 NexoraTechTeam/academy perbaiki login") +
                "\n\nPR selalu menuju " + code(ghflow.PR_BASE) +
                ", dan merge butuh approval kamu lewat " + code("/merge") + ".")
    tid, repo = parts[0], parts[1]
    title = parts[2] if len(parts) > 2 else f"{tid}: perubahan dari agent-harness"

    ok, reason = ghflow.validate_repo(repo)
    if not ok:
        return "❌ " + esc(reason) + "\n" + _repos_hint()

    ok, info = pushgate.plan(tid)
    if not ok:
        return "❌ " + esc(info)

    res = pushgate.push(tid, repo=repo)
    if not res.get("ok"):
        return f"❌ Push {code(tid)} gagal:\n" + esc(res.get("error", ""))

    pr = ghflow.open_pr(repo, res["branch"], title,
                        body=(f"Task `{tid}` dikerjakan oleh agent-harness.\n\n"
                              f"Branch: `{res['branch']}`\n"
                              f"Merge ke `{ghflow.PR_BASE}` hanya setelah approval owner di Telegram."))
    if not pr.get("ok"):
        return (f"⚠️ Branch {code(res['branch'])} sudah ter-push ke {code(repo)}, "
                f"tapi PR gagal dibuat:\n" + esc(pr.get("error", "")) +
                "\nBuat PR manual atau ulangi dengan " + code("/pr"))

    return (f"✅ {code(tid)} → branch {code(res['branch'])}\n"
            f"📬 PR #{pr['number']} ke {code(ghflow.PR_BASE)}: {pr['url']}\n\n"
            f"Merge: " + code(f"/merge {repo} {pr['number']}"))


def cmd_pr(args: str) -> str:
    """/pr <org/repo> <branch> [judul] — buka PR untuk branch yang sudah ada."""
    parts = args.strip().split(None, 2)
    if len(parts) < 2:
        return ("Format: " + code("/pr <org/repo> <ah/branch> [judul]") +
                "\nUntuk push + PR sekaligus pakai " + code("/push") + ".")
    repo, head = parts[0], parts[1]
    title = parts[2] if len(parts) > 2 else head
    res = ghflow.open_pr(repo, head, title)
    if not res.get("ok"):
        return "❌ " + esc(res.get("error", ""))
    return (f"📬 PR #{res['number']} ke {code(ghflow.PR_BASE)}: {res['url']}\n"
            f"Merge: " + code(f"/merge {repo} {res['number']}"))


def cmd_prs(args: str) -> str:
    """/prs <org/repo> — PR terbuka yang menuju dev."""
    repo = args.strip().split()[0] if args.strip() else ""
    if not repo:
        return "Format: " + code("/prs <org/repo>") + "\n" + _repos_hint()
    res = ghflow.list_prs(repo)
    if not res.get("ok"):
        return "❌ " + esc(res.get("error", ""))
    items = res.get("items") or []
    if not items:
        return f"Tidak ada PR terbuka ke {code(ghflow.PR_BASE)} di {code(repo)}."
    lines = [f"<b>PR terbuka → {esc(ghflow.PR_BASE)}</b> ({esc(repo)})"]
    for p in items:
        lines.append(f"#{p['number']} — {esc(p['title'])}\n{p['url']}")
    lines.append("\nMerge: " + code(f"/merge {repo} <nomor>"))
    return "\n".join(lines)


def cmd_merge(args: str, chat_id: int | None = None) -> str:
    """/merge <org/repo> <nomor> — tampilkan PR lalu minta approval lewat tombol.

    This never merges. It stages an offer and shows the buttons; the merge
    happens in handle_callback, only when the owner taps Approve.
    """
    parts = args.strip().split()
    if len(parts) < 2:
        return ("Format: " + code("/merge <org/repo> <nomor-PR>") +
                "\nLihat daftar: " + code("/prs <org/repo>"))
    repo, raw = parts[0], parts[1].lstrip("#")
    if not raw.isdigit():
        return "❌ Nomor PR harus angka."
    info = ghflow.get_pr(repo, int(raw))
    if not info.get("ok"):
        return "❌ " + esc(info.get("error", ""))

    ok, reason = ghflow.validate_base(info.get("base"))
    if not ok:
        return (f"❌ PR #{info['number']} menargetkan {code(info.get('base'))}. " +
                esc(reason))
    if info.get("merged"):
        return f"PR #{info['number']} sudah ter-merge."
    if info.get("state") != "open":
        return f"PR #{info['number']} tidak terbuka (state={esc(info.get('state'))})."

    token = ghflow.stage_approval(repo, info["number"], info["head_sha"], chat_id)
    text = (f"<b>Minta approval merge</b>\n"
            f"{esc(repo)} PR #{info['number']}\n"
            f"{esc(info.get('title') or '')}\n\n"
            f"{code(info.get('head'))} → {code(info.get('base'))}\n"
            f"{info.get('changed_files') or 0} berkas, "
            f"+{info.get('additions') or 0}/-{info.get('deletions') or 0}\n"
            f"commit {code((info.get('head_sha') or '')[:7])}\n"
            f"{info.get('url')}\n\n"
            f"Merge hanya berjalan kalau kamu tekan Approve.")
    keyboard = {"inline_keyboard": [[
        {"text": "✅ Approve & merge", "callback_data": CB_APPROVE + token},
        {"text": "✖️ Batal", "callback_data": CB_CANCEL + token},
    ]]}
    res = tgcore.call("sendMessage", {
        "chat_id": chat_id, "text": text, "parse_mode": "HTML",
        "disable_web_page_preview": "true",
        "reply_markup": json.dumps(keyboard),
    })
    if not res.get("ok"):
        # No buttons reached the chat, so there is no approval path. Say so
        # rather than leaving a staged token nobody can act on.
        return text + "\n\n⚠️ Tombol gagal dikirim: " + esc(res.get("description", ""))
    return ""


def handle_callback(cfg: dict, cq: dict) -> None:
    """Answer an inline-button tap. The only place a merge is ever called."""
    data = (cq.get("data") or "").strip()
    cq_id = cq.get("id")
    msg = cq.get("message") or {}
    chat_id = (msg.get("chat") or {}).get("id")
    tapper = (cq.get("from") or {}).get("id")

    def answer(text: str, alert: bool = False) -> None:
        tgcore.call("answerCallbackQuery", {
            "callback_query_id": cq_id, "text": text[:190],
            "show_alert": "true" if alert else "false",
        })

    if not data.startswith((CB_APPROVE, CB_CANCEL)):
        answer("Tombol tidak dikenal.")
        return

    # A button is a command, so it needs the same role check the command has.
    if not tgcore.is_allowed(cfg, tapper) or not tgcore.has_level(cfg, tapper, "owner"):
        answer("Hanya owner yang boleh menyetujui merge.", alert=True)
        return

    token = data.split(":", 2)[2] if data.count(":") >= 2 else ""
    pending = ghflow.resolve_pending(token)
    if not pending:
        answer("Permintaan approval ini sudah kedaluwarsa.", alert=True)
        return

    repo, number = pending["repo"], int(pending["number"])

    if data.startswith(CB_CANCEL):
        answer("Dibatalkan.")
        tgcore.send(chat_id, f"✖️ Merge {code(repo)} PR #{number} dibatalkan.")
        return

    answer("Memproses merge…")
    ghflow.record_approval(repo, number, pending.get("head_sha", ""), tapper)
    res = ghflow.merge(repo, number)
    if not res.get("ok"):
        tgcore.send(chat_id, f"❌ Merge {code(repo)} PR #{number} gagal:\n" +
                    esc(res.get("error", "")))
        return
    tgcore.send(chat_id, (f"✅ PR #{number} ter-merge ke {code(ghflow.PR_BASE)} "
                          f"({code(repo)})\ncommit {code((res.get('sha') or '')[:7])}"))


HANDLERS = {"pr": cmd_pr, "prs": cmd_prs}
