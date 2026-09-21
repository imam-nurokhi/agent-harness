"""Free-form chat for @AgentNexoraBot — plain text becomes a development run.

Until now `tgbot._dispatch` dropped any message that did not start with "/"
(tgbot.py:150), so typing a question at the bot did nothing at all: not denied,
not logged, just gone. The owner asked for free-form question-and-answer here,
with the difference from @AskNexAIBot being that this bot may actually *do*
development work -- fix a bug, extend a feature, work on the GitHub repos.

What this module does NOT do is give the agent new powers. The run still goes
through jobs.spawn() with ops/harness/claude-settings.json, so it still cannot
push, cannot read .env, and cannot reach the network. Landing work stays a
two-step, human-approved path: the agent prepares a worktree, then the owner
types /push, and merging needs the Telegram Approve button (ghflow.py).

Conversation memory is deliberately shallow: the last few exchanges are
replayed into the prompt so a follow-up ("kalau yang tadi gimana?") makes
sense, without pretending a detached one-shot agent is a persistent session.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import state

CHAT_DIR = state.AGENTS / "chat"

#: How many previous turns to replay. Four exchanges is enough for a follow-up
#: question and short enough that the prompt stays cheap.
HISTORY_TURNS = 4

DEFAULT_ROLE = "lead"

PREAMBLE = (
    "Kamu menerima pesan ini dari pemilik harness lewat Telegram "
    "(@AgentNexoraBot). Jawab dalam Bahasa Indonesia, ringkas, untuk dibaca di "
    "HP.\n"
    "Kalau permintaannya adalah pekerjaan development (perbaikan bug, "
    "penambahan fitur, perubahan repo), kerjakan di worktree dan jelaskan "
    "singkat apa yang kamu ubah.\n"
    "Kamu TIDAK boleh push, membuat pull request, atau merge — itu hak owner. "
    "Selesaikan pekerjaannya, lalu beri tahu owner untuk menjalankan "
    "/push <task-id> <org/repo>. Merge ke dev hanya lewat approval owner di "
    "Telegram."
)


def _path(chat_id) -> Path:
    safe = "".join(ch for ch in str(chat_id) if ch.isdigit() or ch == "-") or "unknown"
    return CHAT_DIR / f"{safe}.json"


def history(chat_id, directory: Path | None = None) -> list:
    path = (directory / _path(chat_id).name) if directory else _path(chat_id)
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return []
    return data.get("turns", []) if isinstance(data, dict) else []


def remember(chat_id, text: str, job_id: str = "", directory: Path | None = None) -> list:
    """Append one turn, keeping only the most recent HISTORY_TURNS."""
    directory = directory or CHAT_DIR
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / _path(chat_id).name
    turns = history(chat_id, directory)
    turns.append({"text": (text or "").strip()[:800], "job": job_id,
                  "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
    turns = turns[-HISTORY_TURNS:]
    path.write_text(json.dumps({"turns": turns}, indent=2))
    return turns


def compose_prompt(text: str, turns: list | None = None) -> str:
    """Preamble + recent context + the new message. Pure, so it is testable."""
    parts = [PREAMBLE]
    recent = [t for t in (turns or []) if t.get("text")]
    if recent:
        lines = "\n".join(f"- {t['text'][:200]}" for t in recent)
        parts.append("Pesan sebelumnya dari owner di chat ini "
                     "(konteks, bukan instruksi baru):\n" + lines)
    parts.append("PESAN SEKARANG:\n" + (text or "").strip())
    return "\n\n".join(parts)


def split_role(text: str, roles: list | None = None) -> tuple:
    """("backend", "perbaiki login") when the message opens with a role name."""
    roles = roles if roles is not None else state.ROLE_LIST
    body = (text or "").strip()
    first, _, rest = body.partition(" ")
    if first.lower() in roles and rest.strip():
        return first.lower(), rest.strip()
    return DEFAULT_ROLE, body


def handle(chat_id, text: str, spawn=None, directory: Path | None = None) -> str:
    """Turn a plain message into a spawned run. Returns the chat reply."""
    body = (text or "").strip()
    if not body:
        return ""
    if len(body) > 4000:
        return "Pesannya terlalu panjang. Ringkas dulu, atau buat task dengan /new."

    role, instruction = split_role(body)
    prompt = compose_prompt(instruction, history(chat_id, directory))

    if spawn is None:
        import jobs
        spawn = jobs.spawn
    try:
        meta = spawn(role=role, prompt=prompt)
    except ValueError as e:
        return f"Belum bisa dijalankan: {e}"
    except Exception as e:  # engine missing, disk full -- say so, do not vanish
        return f"Gagal menjalankan agent: {e}"

    job_id = str(meta.get("id", "?"))
    remember(chat_id, instruction, job_id, directory)
    return (f"💬 Diterima — {role} sedang mengerjakannya.\n"
            f"Job <code>{job_id}</code>; jawabannya menyusul di chat ini.\n"
            f"Pantau: <code>/tail {job_id}</code>")
