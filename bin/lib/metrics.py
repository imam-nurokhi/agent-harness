"""Monitoring for the harness: Prometheus now, Grafana when a token exists.

The whole observability stack already runs on this host — Grafana 13.2 on
:3000, Prometheus on :9090, Loki on :3100, behind monitoring.nexoratech.co —
and the harness had no idea. `docs/nexora-cbqa-cloud-operations-plan.md` item
#5 still lists uptime and SSL as "not covered at all"; they have in fact been
scraped all along, by 17 blackbox probes nobody was reading.

Two deliberate choices:

**Prometheus, not Grafana, is the data source.** Prometheus needs no
credential, answers structured queries, and holds the same series every
dashboard draws from. Grafana's API needs a service-account token, and asking
for one before the feature works would have blocked the whole thing on an
email. Grafana is used for what only Grafana knows — dashboards and its own
alert rules — and every function that needs it degrades to "not configured"
rather than failing.

**Reading only.** No rule is written, no silence created, no dashboard edited.
The monitoring stack belongs to a vhost this workspace shares (CLAUDE.md §1);
the harness is a reader there, never an author.
"""
from __future__ import annotations

import json
import re
import os
import urllib.error
import urllib.parse
import urllib.request

PROM = os.environ.get("PROM_URL", "http://127.0.0.1:9090")
GRAFANA = os.environ.get("GRAFANA_URL", "http://127.0.0.1:3000")
GRAFANA_PUBLIC = "https://monitoring.nexoratech.co"

TIMEOUT = 12

#: Thresholds. Chosen to be quiet: a monitor that cries every day is a monitor
#: nobody reads, and this workspace has already paid for that lesson twice
#: (hourly auto-resume alerts, weekly alerts for an uninstalled trigger).
SSL_WARN_DAYS = 21
DISK_WARN_PCT = 85.0
MEM_WARN_PCT = 90.0


class Unavailable(Exception):
    """The source could not be reached. Never silently treated as 'healthy'."""


def _get(url: str, token: str = "") -> dict:
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read().decode(errors="replace") or "{}")
    except urllib.error.HTTPError as e:
        raise Unavailable(f"HTTP {e.code}") from e
    except Exception as e:
        raise Unavailable(str(e)) from e


def query(expr: str, base: str = "") -> list:
    """Instant query -> [(labels, float)]. Raises Unavailable, never lies."""
    url = f"{base or PROM}/api/v1/query?" + urllib.parse.urlencode({"query": expr})
    data = _get(url)
    if data.get("status") != "success":
        raise Unavailable(data.get("error") or "prometheus menolak query")
    out = []
    for row in data.get("data", {}).get("result", []):
        try:
            out.append((row.get("metric", {}), float(row["value"][1])))
        except (KeyError, ValueError, TypeError):
            continue
    return out


# --------------------------------------------------------------------------
# Pure shaping. Tested without a network.
# --------------------------------------------------------------------------

def probe_summary(rows: list) -> dict:
    """Uptime across blackbox probes."""
    total = len(rows)
    down = sorted(m.get("instance", "?") for m, v in rows if v < 1)
    return {"total": total, "up": total - len(down), "down": down}


def ssl_summary(rows: list, warn_days: int = SSL_WARN_DAYS) -> dict:
    """Certificates, soonest expiry first."""
    items = sorted(({"host": m.get("instance", "?"), "days": int(v)} for m, v in rows),
                   key=lambda x: x["days"])
    return {"items": items, "soonest": items[0] if items else None,
            "expiring": [i for i in items if i["days"] <= warn_days]}


#: Instance labels in this Prometheus are prose, not hostnames:
#: "Server Production audit-q.cbqaglobal.co.id (148.230.96.117)" and
#: "Server Development OneAlpha". Matching the literal "Server Production"
#: left the Development ones untouched — visible the first time the real data
#: was rendered — so the environment word is matched as a class.
_ENV_PREFIX = re.compile(r"^server\s+\w+\s+", re.IGNORECASE)


def _short_host(label: str) -> str:
    text = _ENV_PREFIX.sub("", (label or "?").strip())
    return (text.split(" (")[0] or text).strip() or "?"


def worst(rows: list, warn_pct: float) -> dict:
    """Highest utilisation, plus everything over the threshold."""
    items = sorted(({"host": _short_host(m.get("instance", "")), "pct": round(v, 1)}
                    for m, v in rows), key=lambda x: -x["pct"])
    return {"items": items, "top": items[0] if items else None,
            "over": [i for i in items if i["pct"] >= warn_pct]}


def targets_summary(rows: list) -> dict:
    """`up` across every scrape target."""
    total = len(rows)
    down = sorted(f"{m.get('job', '?')}/{_short_host(m.get('instance', ''))}"
                  for m, v in rows if v < 1)
    return {"total": total, "up": total - len(down), "down": down}


def verdict(probes: dict, ssl: dict, disk: dict, mem: dict, targets: dict) -> str:
    """One word the owner can act on, before reading any detail."""
    if probes.get("down") or targets.get("down"):
        return "turun"
    if ssl.get("expiring") or disk.get("over") or mem.get("over"):
        return "perhatian"
    return "sehat"


ICON = {"sehat": "🟢", "perhatian": "🟡", "turun": "🔴"}


def render(summary: dict) -> str:
    """The Telegram message. Short by design: this is read on a phone."""
    if summary.get("error"):
        return ("🔌 <b>Monitoring tidak terbaca</b>\n"
                f"Prometheus di {PROM} tidak menjawab: {summary['error']}\n"
                "Ini bukan berarti layanan sehat — statusnya tidak diketahui.")

    p, s, d, m, t = (summary[k] for k in ("probes", "ssl", "disk", "mem", "targets"))
    v = summary["verdict"]
    lines = [f"{ICON.get(v, '•')} <b>Monitoring — {v}</b>"]

    lines.append(f"\n<b>Situs</b>: {p['up']}/{p['total']} up")
    for host in p["down"][:5]:
        lines.append(f"  🔴 {host}")

    if s["soonest"]:
        lines.append(f"<b>SSL terdekat</b>: {s['soonest']['host']} — {s['soonest']['days']} hari")
    for item in s["expiring"][:5]:
        lines.append(f"  ⚠️ {item['host']} tinggal {item['days']} hari")

    if d["top"]:
        lines.append(f"<b>Disk tertinggi</b>: {d['top']['host']} {d['top']['pct']}%")
    for item in d["over"][:5]:
        lines.append(f"  ⚠️ {item['host']} disk {item['pct']}%")

    if m["top"]:
        lines.append(f"<b>RAM tertinggi</b>: {m['top']['host']} {m['top']['pct']}%")
    for item in m["over"][:5]:
        lines.append(f"  ⚠️ {item['host']} RAM {item['pct']}%")

    lines.append(f"<b>Target scrape</b>: {t['up']}/{t['total']} up")
    for name in t["down"][:5]:
        lines.append(f"  🔴 {name}")

    grafana = summary.get("grafana")
    if grafana and grafana.get("configured"):
        lines.append(f"\n<b>Grafana</b>: {grafana['dashboards']} dashboard, "
                     f"{grafana['alerting']} alert aktif")
    else:
        lines.append("\n<i>Grafana belum tersambung — tambahkan GRAFANA_TOKEN ke .env "
                     "untuk daftar dashboard dan alert.</i>")
    lines.append(GRAFANA_PUBLIC + "/dashboards")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Collection.
# --------------------------------------------------------------------------

QUERIES = {
    "probes": "probe_success",
    "ssl": "(probe_ssl_earliest_cert_expiry - time())/86400",
    "disk": ('max by (instance) (100 - (node_filesystem_avail_bytes'
             '{fstype!~"tmpfs|overlay|squashfs"} / node_filesystem_size_bytes * 100))'),
    "mem": ("100 * (1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)"),
    "targets": "up",
}


def collect(token: str = "") -> dict:
    try:
        raw = {key: query(expr) for key, expr in QUERIES.items()}
    except Unavailable as exc:
        return {"error": str(exc)}
    out = {
        "probes": probe_summary(raw["probes"]),
        "ssl": ssl_summary(raw["ssl"]),
        "disk": worst(raw["disk"], DISK_WARN_PCT),
        "mem": worst(raw["mem"], MEM_WARN_PCT),
        "targets": targets_summary(raw["targets"]),
        "grafana": grafana_overview(token),
    }
    out["verdict"] = verdict(out["probes"], out["ssl"], out["disk"],
                             out["mem"], out["targets"])
    return out


def grafana_overview(token: str = "") -> dict:
    """Dashboards and firing alerts. Degrades to 'not configured' without a token."""
    token = token or os.environ.get("GRAFANA_TOKEN", "").strip()
    if not token:
        return {"configured": False}
    try:
        dashboards = _get(f"{GRAFANA}/api/search?type=dash-db&limit=100", token)
        alerts = _get(f"{GRAFANA}/api/alertmanager/grafana/api/v2/alerts", token)
    except Unavailable as exc:
        return {"configured": True, "error": str(exc), "dashboards": 0, "alerting": 0}
    firing = [a for a in alerts if (a.get("status") or {}).get("state") == "active"] \
        if isinstance(alerts, list) else []
    return {
        "configured": True,
        "dashboards": len(dashboards) if isinstance(dashboards, list) else 0,
        "alerting": len(firing),
        "titles": [d.get("title") for d in (dashboards or [])][:10]
                  if isinstance(dashboards, list) else [],
    }
