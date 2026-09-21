"""Telegram transport, config, and pairing for the agent harness. Stdlib only."""
from __future__ import annotations

import json
import random
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import state

TG_DIR = state.AGENTS / ".telegram"
CONFIG = TG_DIR / "config.json"
ENV = state.WORKSPACE / ".env"

API = "https://api.telegram.org/bot{token}/{method}"
ROLE_LEVELS = ("viewer", "operator", "owner")


# ------------------------------------------------------------------ config

def load_env() -> dict:
    out = {}
    if ENV.exists():
        for line in ENV.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                out[k.strip()] = v.strip()
    return out


def token() -> str:
    t = load_env().get("TELEGRAM_BOT_TOKEN", "")
    if not t:
        raise SystemExit("TELEGRAM_BOT_TOKEN missing from ~/AI-Workspace/.env")
    return t


def load_config() -> dict:
    if CONFIG.exists():
        try:
            return json.loads(CONFIG.read_text())
        except Exception:
            pass
    return {"allowed": [], "pair_code": None, "offset": 0, "seen_jobs": []}


def save_config(cfg: dict) -> None:
    TG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps(cfg, indent=2))
    CONFIG.chmod(0o600)


def allowed_from_env() -> list[int]:
    raw = load_env().get("TELEGRAM_ALLOWED_CHATS", "")
    out = []
    for part in raw.split(","):
        part = part.strip()
        if part.lstrip("-").isdigit():
            out.append(int(part))
    return out


def new_pair_code(cfg: dict) -> str:
    code = f"{random.randint(0, 999999):06d}"
    cfg["pair_code"] = code
    save_config(cfg)
    return code


def is_allowed(cfg: dict, chat_id: int) -> bool:
    return chat_id in set(cfg.get("allowed", [])) | set(allowed_from_env())


def role_for(cfg: dict, chat_id: int) -> str | None:
    """Resolve a paired chat's role, preserving legacy paired-chat ownership."""
    if not is_allowed(cfg, chat_id):
        return None
    role = cfg.get("roles", {}).get(str(chat_id))
    if role in ROLE_LEVELS:
        return role
    return "owner"


def has_level(cfg: dict, chat_id: int, minimum: str) -> bool:
    if minimum not in ROLE_LEVELS:
        raise ValueError(f"unknown Telegram role: {minimum}")
    role = role_for(cfg, chat_id)
    return role is not None and ROLE_LEVELS.index(role) >= ROLE_LEVELS.index(minimum)


def owner_chat_ids(cfg: dict) -> set[int]:
    chats = set(cfg.get("allowed", [])) | set(allowed_from_env())
    return {chat_id for chat_id in chats if role_for(cfg, chat_id) == "owner"}


def grant_role(cfg: dict, chat_id: int, role: str) -> None:
    """Persist a role change without permitting removal of the final owner."""
    if role not in ROLE_LEVELS:
        raise ValueError("role harus viewer, operator, atau owner")
    if not is_allowed(cfg, chat_id):
        raise ValueError("chat belum ter-pair")
    was_owner = role_for(cfg, chat_id) == "owner"
    if was_owner and role != "owner" and len(owner_chat_ids(cfg)) <= 1:
        raise ValueError("owner terakhir tidak boleh diturunkan")
    roles = dict(cfg.get("roles", {}))
    roles[str(chat_id)] = role
    cfg["roles"] = roles


def notification_targets(cfg: dict, minimum: str = "operator") -> list[int]:
    return sorted(chat_id for chat_id in
                  (set(cfg.get("allowed", [])) | set(allowed_from_env()))
                  if has_level(cfg, chat_id, minimum))


# ------------------------------------------------------------------- API

def call(method: str, params: dict | None = None, timeout: int = 40) -> dict:
    url = API.format(token=token(), method=method)
    data = urllib.parse.urlencode(params or {}).encode()
    req = urllib.request.Request(url, data=data)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read())
        except Exception:
            return {"ok": False, "description": str(e)}
    except Exception as e:
        return {"ok": False, "description": str(e)}


TG_LIMIT = 3800  # Telegram caps a message at 4096 chars; leave room for markup.


def send(chat_id: int, text: str, preview: bool = False) -> dict:
    """Send, splitting on line boundaries so long reports are not truncated."""
    chunks, cur = [], ""
    for line in text.split("\n"):
        while len(line) > TG_LIMIT:            # a single absurdly long line
            chunks.append(line[:TG_LIMIT])
            line = line[TG_LIMIT:]
        if len(cur) + len(line) + 1 > TG_LIMIT:
            chunks.append(cur)
            cur = line
        else:
            cur = f"{cur}\n{line}" if cur else line
    if cur:
        chunks.append(cur)

    res = {"ok": True}
    for c in chunks or [""]:
        res = call("sendMessage", {
            "chat_id": chat_id,
            "text": c,
            "parse_mode": "HTML",
            "disable_web_page_preview": "false" if preview else "true",
        })
        if not res.get("ok"):
            # Fall back to plain text if the HTML failed to parse.
            res = call("sendMessage", {"chat_id": chat_id, "text": c})
    return res


def get_updates(offset: int, timeout: int = 25) -> list[dict]:
    r = call("getUpdates", {"offset": offset, "timeout": timeout},
             timeout=timeout + 12)
    return r.get("result", []) if r.get("ok") else []


def esc(s: object) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def code(s: object) -> str:
    return f"<code>{esc(s)}</code>"


def set_commands() -> dict:
    cmds = [
        ("status", "Ringkasan harness"),
        ("agents", "Roster agent (bidak catur)"),
        ("tasks", "Daftar task"),
        ("task", "Detail task: /task task-001"),
        ("run", "Jalankan: /run backend task-001"),
        ("ask", "Instruksi bebas: /ask lead cek status"),
        ("jobs", "Run terakhir"),
        ("tail", "Output run: /tail <job-id>"),
        ("stop", "Hentikan run: /stop <job-id>"),
        ("triggers", "Trigger terjadwal"),
        ("trigger", "Jalankan trigger: /trigger standup"),
        ("doctor", "Cek kesehatan harness"),
        ("help", "Semua perintah"),
    ]


def set_commands_full() -> dict:
    """Full command menu including task management and noise control."""
    cmds = _full_command_list()
    return call("setMyCommands", {
        "commands": json.dumps([{"command": c, "description": d} for c, d in cmds])
    })


def _full_command_list() -> list:
    """The one list the Telegram slash-menu is built from."""
    return [
        ("kanban", "Papan kanban"),
        ("status", "Ringkasan harness"),
        ("ops", "Status n8n, backup, server"),
        ("monitor", "Uptime, SSL, disk, target Prometheus"),
        ("digest", "Ringkasan sesuai permintaan"),
        ("brief", "Daily brief data tersedia"),
        ("reporting", "Report: director|management|dev"),
        ("weekly", "Weekly report untuk meeting manajemen"),
        ("daily", "Update tim dari Slack #daily-updates"),
        ("sources", "Status sumber data/integrasi"),
        ("reminders", "Cakupan reminder aktif"),
        ("support", "Status support intake"),
        ("deploy", "Aturan deploy production"),
        ("grant", "Owner: ubah role chat"),
        ("agents", "Roster agent (bidak catur)"),
        ("tasks", "Daftar task"),
        ("task", "Detail task: /task task-001"),
        ("new", "Buat task baru: /new <judul>"),
        ("assign", "Tetapkan role: /assign task-005 backend"),
        ("ac", "Tambah kriteria: /ac task-005 <kriteria>"),
        ("tick", "Centang kriteria: /tick task-005 2"),
        ("wt", "Buat worktree: /wt task-005 projects/sandbox"),
        ("note", "Catatan: /note task-005 <teks>"),
        ("close", "Cek kesiapan tutup: /close task-005"),
        ("run", "Jalankan: /run backend task-001"),
        ("ask", "Instruksi bebas: /ask lead <teks>"),
        ("jobs", "Run terakhir"),
        ("tail", "Output run: /tail <job-id>"),
        ("stop", "Hentikan run: /stop <job-id>"),
        ("triggers", "Trigger terjadwal"),
        ("trigger", "Jalankan trigger: /trigger standup"),
        ("quiet", "Notifikasi: /quiet on|off"),
        ("diff", "Kirim diff worktree: /diff task-005"),
        ("report", "Kirim report/transkrip: /report task-005"),
        ("log", "Kirim log penuh: /log <job-id>"),
        ("push", "Push ke branch baru + PR ke dev: /push task-005 <org/repo>"),
        ("pr", "Buka PR ke dev: /pr <org/repo> <ah/branch>"),
        ("prs", "PR terbuka ke dev: /prs <org/repo>"),
        ("merge", "Minta approval merge: /merge <org/repo> <nomor>"),
        ("engine", "Engine yang dipakai + yang limit/ditolak"),
        ("resume", "Lanjutkan task mandek sekarang"),
        ("doctor", "Cek kesehatan harness"),
        ("help", "Semua perintah"),
    ]
