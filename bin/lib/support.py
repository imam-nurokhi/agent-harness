"""Private, internal support intake records; never a public customer endpoint."""
from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import state


SUPPORT_DIR = state.AGENTS / "support"
INTAKE = SUPPORT_DIR / "intake.json"
SEVERITIES = {"low": 72, "normal": 24, "high": 8, "urgent": 4}
STATUSES = {"new", "triage", "assigned", "waiting_customer", "resolved", "closed"}
SECRET_PATTERN = re.compile(
    r"(?:api[_-]?key|access[_-]?token|password|secret)\s*[:=]|"
    r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    re.IGNORECASE,
)


def _now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def _timestamp(value: datetime | None = None) -> str:
    return (value or _now()).isoformat().replace("+00:00", "Z")


def _clean(value: object, field: str, limit: int) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} is required")
    text = value.strip()
    if not text:
        raise ValueError(f"{field} is required")
    if len(text) > limit:
        raise ValueError(f"{field} is too long")
    if SECRET_PATTERN.search(text):
        raise ValueError("support intake must not contain secret material")
    return text


def _load() -> list[dict]:
    if not INTAKE.exists():
        return []
    try:
        data = json.loads(INTAKE.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"support intake cannot be read: {exc}") from exc
    if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
        raise ValueError("support intake has invalid format")
    return data


def _save(items: list[dict]) -> None:
    SUPPORT_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    SUPPORT_DIR.chmod(0o700)
    descriptor, temporary_name = tempfile.mkstemp(prefix="intake-", suffix=".json", dir=SUPPORT_DIR)
    try:
        with os.fdopen(descriptor, "w") as handle:
            json.dump(items, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.chmod(temporary_name, 0o600)
        Path(temporary_name).replace(INTAKE)
        INTAKE.chmod(0o600)
    finally:
        Path(temporary_name).unlink(missing_ok=True)


def _next_id(items: list[dict]) -> str:
    highest = 0
    for item in items:
        match = re.fullmatch(r"sup-(\d+)", str(item.get("id", "")))
        if match:
            highest = max(highest, int(match.group(1)))
    return f"sup-{highest + 1:04d}"


def list_requests() -> list[dict]:
    return sorted(_load(), key=lambda item: item.get("created_at", ""), reverse=True)


def create(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("support payload must be an object")
    severity = str(payload.get("severity", "")).lower()
    if severity not in SEVERITIES:
        raise ValueError("severity must be low, normal, high, or urgent")
    subject = _clean(payload.get("subject"), "subject", 140)
    requester_ref = _clean(payload.get("requester_ref"), "requester reference", 120)
    summary = _clean(payload.get("summary"), "summary", 2000)
    items = _load()
    created_at = _now()
    request = {
        "id": _next_id(items),
        "subject": subject,
        "requester_ref": requester_ref,
        "summary": summary,
        "severity": severity,
        "status": "new",
        "assignee": "",
        "created_at": _timestamp(created_at),
        "updated_at": _timestamp(created_at),
        "sla_due_at": _timestamp(created_at + timedelta(hours=SEVERITIES[severity])),
        "history": [{"at": _timestamp(created_at), "event": "created"}],
    }
    items.append(request)
    _save(items)
    return request


def update(request_id: str, status: str, assignee: str | None = None) -> dict:
    if status not in STATUSES:
        raise ValueError("invalid support status")
    if not re.fullmatch(r"sup-\d+", request_id or ""):
        raise ValueError("invalid support id")
    items = _load()
    request = next((item for item in items if item.get("id") == request_id), None)
    if request is None:
        raise ValueError("support request not found")
    next_assignee = request.get("assignee", "")
    if assignee is not None:
        next_assignee = _clean(assignee, "assignee", 120)
    if status == "assigned" and not next_assignee:
        raise ValueError("assigned support request needs an assignee")
    request["status"] = status
    request["assignee"] = next_assignee
    request["updated_at"] = _timestamp()
    request.setdefault("history", []).append({
        "at": request["updated_at"],
        "event": f"status:{status}" + (f" assignee:{next_assignee}" if assignee else ""),
    })
    _save(items)
    return request
