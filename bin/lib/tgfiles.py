"""Sending an agent's work to Telegram as a file — diff, report, or full log.

`/tail` truncates and a chat message caps at 4096 characters, so a real diff or
report cannot be read from a phone. Telegram accepts documents; this sends them.

The guard is the reason this is its own module. The same pipe that hands you a
diff could hand out `.env` or a private key, so every path is checked before a
byte leaves the box: it must resolve inside the workspace (symlinks followed),
must not be a secret-bearing file, and must be within Telegram's size limit.
The checks are pure functions so they can be tested without a network.
"""
import mimetypes
import re
import urllib.request
from pathlib import Path

import state

# Telegram accepts documents up to 50 MB, but the harness caps lower: a file
# this big is almost never something you want on a phone, and it bounds abuse.
MAX_BYTES = 20 * 1024 * 1024

# Never send these, whatever directory they sit in. Matched on the whole name
# so `.env.production` and `id_rsa.key` are caught, not just `.env`.
_SECRET = re.compile(
    r"(^|/)\.env(\.|$)"
    r"|\.pem$|\.key$|\.p12$|\.pfx$|\.keystore$|\.jks$"
    r"|(^|/)id_(rsa|ed25519|ecdsa)($|\.)"
    r"|(^|/)\.git-credentials$"
    r"|(^|/)credentials\.json$",
    re.IGNORECASE)


def check_sendable(path) -> tuple:
    """(ok, reason). The one gate every artifact passes before it is sent."""
    p = Path(path)
    try:
        real = p.resolve()
    except Exception:
        return False, "cannot resolve the path"

    ws = state.WORKSPACE.resolve()
    if real != ws and ws not in real.parents:
        return False, "refused: the file is outside the workspace"
    if _SECRET.search(real.as_posix()):
        return False, "refused: that looks like a secret file and will not be sent"
    if not real.is_file():
        return False, "no such file"
    size = real.stat().st_size
    if size > MAX_BYTES:
        mb = size / (1024 * 1024)
        return False, f"refused: {mb:.0f} MB is over the 20 MB limit"
    return True, ""


def _safe_id(task_or_job: str) -> str | None:
    """A task/job id is a bare token; anything with a path separator is a lie."""
    tid = (task_or_job or "").strip()
    if not tid or "/" in tid or "\\" in tid or ".." in tid:
        return None
    return tid


def report_path(task_id: str):
    """The report to send for a task: the report file, else its newest transcript."""
    tid = _safe_id(task_id)
    if not tid:
        return None
    report = state.REPORTS / f"{tid}.md"
    if report.is_file():
        return report
    logs = sorted(state.REPORTS.glob(f"{tid}.*.log"),
                  key=lambda p: -p.stat().st_mtime)
    return logs[0] if logs else None


def diff_path(task_id: str):
    """Write the worktree diff to a temp file under reports/, or None if clean/absent."""
    tid = _safe_id(task_id)
    if not tid:
        return None, "invalid task id"
    wt = state.WORKTREES / tid
    if not wt.is_dir():
        return None, f"no worktree for {tid}"
    import subprocess
    try:
        out = subprocess.run(["git", "-C", str(wt), "diff"],
                             capture_output=True, text=True, timeout=30).stdout
    except Exception as exc:
        return None, f"git diff failed: {exc}"
    if not out.strip():
        return None, f"{tid} has no uncommitted changes"
    dest = state.REPORTS / f".diff-{tid}.patch"
    dest.write_text(out)
    return dest, ""


def job_log_path(job_id: str):
    tid = _safe_id(job_id)
    if not tid:
        return None
    log = state.AGENTS / ".jobs" / f"{tid}.log"
    return log if log.is_file() else None


def send_document(chat_id: int, path, caption: str = "") -> dict:
    """POST a file to Telegram as multipart/form-data, hand-encoded (stdlib only)."""
    import tgcore
    ok, reason = check_sendable(path)
    if not ok:
        return {"ok": False, "description": reason}

    real = Path(path).resolve()
    ctype = mimetypes.guess_type(real.name)[0] or "application/octet-stream"
    boundary = "----ahHarness" + real.name.replace(" ", "_")[:24]
    body = bytearray()

    def field(name, value):
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        body.extend(f"{value}\r\n".encode())

    field("chat_id", str(chat_id))
    if caption:
        field("caption", caption[:1024])
    body.extend(f"--{boundary}\r\n".encode())
    body.extend((f'Content-Disposition: form-data; name="document"; '
                 f'filename="{real.name}"\r\n').encode())
    body.extend(f"Content-Type: {ctype}\r\n\r\n".encode())
    body.extend(real.read_bytes())
    body.extend(f"\r\n--{boundary}--\r\n".encode())

    url = tgcore.API.format(token=tgcore.token(), method="sendDocument")
    req = urllib.request.Request(url, data=bytes(body))
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    try:
        import json
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except Exception as exc:
        return {"ok": False, "description": str(exc)}
