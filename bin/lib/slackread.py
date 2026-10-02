#!/usr/bin/env python3
"""Read #daily-updates and render it, without an agent and without an engine.

A lead agent asked to summarise this channel stopped correctly: there was no
Slack credential, and ops/harness/claude-settings.json denies curl and wget. The
answer is not to loosen that allowlist. This module makes the read a plain
harness capability -- it runs inside the bot process like /weekly, so no
permission gate applies and no engine spend is incurred.

It **groups and attributes**; it does not paraphrase. That is a deliberate
limit: a deterministic report cannot invent an update nobody wrote, and the
reader can see exactly who said what. If a genuine narrative summary is ever
wanted, that is an agent's job on top of this data, not a change here.
"""
from __future__ import annotations

import datetime as dt
import html
import json
import re
import urllib.error
import urllib.request

API = "https://slack.com/api"
TZ = dt.timezone(dt.timedelta(hours=7))          # WIB, the team's timezone
MAX_CHARS = 3600                                  # Telegram rejects over 4096
MAX_LINE = 200

# Slackbot joins, huddles and channel-join notices are not updates.
SKIP_SUBTYPES = {"huddle_thread", "channel_join", "channel_leave", "bot_message"}
SKIP_USERS = {"USLACKBOT"}


class NotConfigured(RuntimeError):
    """Raised instead of guessing at a workspace or a token."""


# ---------------------------------------------------------------- time window

def day_label(epoch: float) -> str:
    return dt.datetime.fromtimestamp(epoch, TZ).strftime("%Y-%m-%d")


def week_window(now: float) -> tuple[float, float]:
    """Monday 00:00 to `now`, in the team's timezone.

    Monday, not "seven days back", so the report lines up with the working week
    people actually talk about.
    """
    here = dt.datetime.fromtimestamp(now, TZ)
    monday = (here - dt.timedelta(days=here.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0)
    return monday.timestamp(), now


# ------------------------------------------------------------------- fetching

def _call(token: str, method: str, params: dict) -> dict:
    query = urllib.parse.urlencode(params)
    req = urllib.request.Request(f"{API}/{method}?{query}")
    # In the header, never the URL: a query string ends up in proxy and access
    # logs, and this token can read the channel.
    req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as r:
        body = json.loads(r.read())
    if not body.get("ok"):
        raise RuntimeError(f"slack {method} failed: {body.get('error', 'unknown')}")
    return body


def fetch_week(token: str, channel: str, now: float) -> tuple[list[dict], dict]:
    """Messages posted since Monday, plus a user-id to display-name map."""
    missing = [name for name, value in
               (("SLACK_BOT_TOKEN", token), ("SLACK_DAILY_CHANNEL_ID", channel))
               if not value]
    if missing:
        raise NotConfigured(
            "Slack is not configured: set " + " and ".join(missing) +
            " in the workspace .env. The bot token needs channels:history and "
            "channels:read, and the bot must be invited to the channel.")

    oldest, latest = week_window(now)
    body = _call(token, "conversations.history", {
        "channel": channel, "oldest": f"{oldest:.6f}",
        "latest": f"{latest:.6f}", "limit": "200"})
    messages = body.get("messages", [])

    # users:read is a separate scope. Without it the report still works, it just
    # shows ids -- losing a post because a name is unavailable would be worse.
    names: dict[str, str] = {}
    for uid in {m.get("user") for m in messages if m.get("user")}:
        try:
            info = _call(token, "users.info", {"user": uid})
            profile = info["user"].get("profile", {})
            names[uid] = (profile.get("display_name")
                          or profile.get("real_name") or uid)
        except Exception:
            names[uid] = uid
    return messages, names


# ------------------------------------------------------------------ rendering

def _esc(text: object) -> str:
    return html.escape(str(text), quote=False)


def clean(text: str, names: dict[str, str] | None = None) -> str:
    """Slack markup into something readable in Telegram."""
    names = names or {}
    # <@U123|Diky> or <@U123>
    text = re.sub(r"<@(\w+)\|([^>]+)>", lambda m: "@" + m.group(2), text)
    text = re.sub(r"<@(\w+)>", lambda m: "@" + names.get(m.group(1), m.group(1)), text)
    # <https://x|label> or <https://x>
    text = re.sub(r"<(https?://[^|>]+)\|([^>]+)>", lambda m: m.group(2), text)
    text = re.sub(r"<(https?://[^>]+)>", lambda m: m.group(1), text)
    text = text.replace("<!channel>", "@channel").replace("<!here>", "@here")
    return text.strip()


def by_day(messages: list[dict], names: dict[str, str] | None = None) -> list[dict]:
    """Real posts, oldest day first, each with who wrote it."""
    names = names or {}
    days: dict[str, list[dict]] = {}
    for m in sorted(messages, key=lambda m: float(m["ts"])):
        if m.get("subtype") in SKIP_SUBTYPES or m.get("user") in SKIP_USERS:
            continue
        body = clean(m.get("text", ""), names)
        if not body:
            continue
        uid = m.get("user", "?")
        days.setdefault(day_label(float(m["ts"])), []).append({
            "author": names.get(uid, uid),
            "user": uid,
            "ts": float(m["ts"]),
            "text": body,
        })
    return [{"date": d, "entries": days[d]} for d in sorted(days)]


def collect(messages: list[dict], names: dict[str, str], now: float,
            expected: set[str] | None = None) -> dict:
    oldest, latest = week_window(now)
    days = by_day(messages, names)
    seen_days = {d["date"] for d in days}

    cursor = dt.datetime.fromtimestamp(oldest, TZ)
    end = dt.datetime.fromtimestamp(latest, TZ)
    silent = []
    while cursor.date() <= end.date():
        label = cursor.strftime("%Y-%m-%d")
        if label not in seen_days:
            silent.append(label)
        cursor += dt.timedelta(days=1)

    posted = {e["user"] for d in days for e in d["entries"]}
    missing = sorted(names.get(u, u) for u in (expected or set()) - posted)

    return {
        "period": f"{day_label(oldest)} … {day_label(latest)}",
        "days": days,
        "silent_days": silent,
        "missing": missing,
        "total": sum(len(d["entries"]) for d in days),
        "people": sorted({e["author"] for d in days for e in d["entries"]}),
    }


def render(data: dict) -> str:
    lines = [
        "📋 <b>#daily-updates</b>",
        f"{data['period']} · {data['total']} pesan · {len(data['people'])} orang",
        "",
    ]
    for day in data["days"]:
        weekday = dt.datetime.strptime(day["date"], "%Y-%m-%d").strftime("%a")
        lines.append(f"<b>{weekday} {day['date']}</b>")
        for e in day["entries"]:
            first, *rest = e["text"].splitlines()
            lines.append(f"• <b>{_esc(e['author'])}</b>: {_esc(first)[:MAX_LINE]}")
            for extra in rest[:6]:
                if extra.strip():
                    lines.append(f"   {_esc(extra.strip())[:MAX_LINE]}")
        lines.append("")

    if data["silent_days"]:
        lines.append("<b>Hari tanpa update</b>")
        lines.append(", ".join(data["silent_days"]) + " — tidak ada pesan")
        lines.append("")
    if data["missing"]:
        lines.append("<b>Belum melapor</b>")
        lines.append(", ".join(_esc(n) for n in data["missing"]))
        lines.append("")

    lines.append("<i>Dikelompokkan apa adanya dari Slack — tidak diparafrase.</i>")

    out = "\n".join(lines)
    if len(out) > MAX_CHARS:
        out = out[:MAX_CHARS].rsplit("\n", 1)[0] + "\n\n… dipotong agar muat di Telegram."
    return out


def report(messages: list[dict], names: dict[str, str], now: float,
           expected: set[str] | None = None) -> str:
    return render(collect(messages, names, now, expected))
