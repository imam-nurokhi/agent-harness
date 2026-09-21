"""Read-only status for the isolated operations stack; no secrets or writes."""
from __future__ import annotations

import os
import shutil
import subprocess
import urllib.request


PUBLIC_BASE = "https://agents.nexoratech.co"


def _disk_status(percent_used: int) -> str:
    if percent_used >= 95:
        return "critical"
    if percent_used >= 85:
        return "warn"
    return "ok"


def _http_status(url: str) -> int | None:
    try:
        with urllib.request.urlopen(url, timeout=1.5) as response:
            return response.status
    except Exception:
        return None


def _service_active(name: str) -> bool:
    try:
        return subprocess.run(
            ["systemctl", "is-active", "--quiet", name],
            capture_output=True, timeout=2,
        ).returncode == 0
    except Exception:
        return False


def _slack_ready() -> bool:
    return bool(os.environ.get("SLACK_BOT_TOKEN")
                and os.environ.get("SLACK_DAILY_CHANNEL_ID"))


def _slack_href() -> str:
    """A link to the channel, never anything derived from the token."""
    channel = os.environ.get("SLACK_DAILY_CHANNEL_ID", "")
    return f"https://slack.com/app_redirect?channel={channel}" if channel else ""


def snapshot() -> dict:
    automation_status = _http_status("http://127.0.0.1:5678/automation/")
    backup_active = _service_active("nexora-operations-backup.timer")
    disk = shutil.disk_usage("/")
    disk_used = round((disk.used / disk.total) * 100)
    return {
        "services": [
            {
                "id": "automation", "label": "n8n automation",
                "status": "ok" if automation_status == 200 else "unavailable",
                "detail": "loopback verified" if automation_status == 200 else "not reachable from this host",
            },
            {
                "id": "backup", "label": "daily local backup",
                "status": "ok" if backup_active else "unavailable",
                "detail": "systemd timer active" if backup_active else "timer unavailable",
            },
            {
                "id": "disk", "label": "server capacity",
                "status": _disk_status(disk_used),
                "detail": f"{disk.free // (1024 ** 3)} GB free · {disk_used}% used",
            },
        ],
        "links": [
            {"label": "Automation", "href": f"{PUBLIC_BASE}/automation/", "status": "ready"},
            {"label": "GitHub NexoraTechTeam", "href": "https://github.com/NexoraTechTeam", "status": "ready"},
            {"label": "GitHub Nexora-Tech-Team", "href": "https://github.com/Nexora-Tech-Team", "status": "ready"},
            {"label": "NEXONE", "href": "", "status": "not-configured"},
            # Read by /daily. Derived, not hard-coded: the surface said
            # "not-configured" regardless, which would become a lie the moment
            # a token was added.
            {"label": "Slack #daily-updates", "href": _slack_href(),
             "status": "ready" if _slack_ready() else "not-configured"},
        ],
    }
