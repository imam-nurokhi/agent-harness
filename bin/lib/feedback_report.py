#!/usr/bin/env python3
"""ah feedback — summarize what the widget feedback collector has recorded.

Reads NDJSON straight off disk (/var/lib/nexora-feedback/<app>/*.ndjson by
default) — no server call, no dependency on ah-feedback being up. Pure
functions over parsed lines, same shape as ops/nginx/validate_vhost.py and
ops/n8n/validate_env.py: a summarize() that takes data in, a thin CLI that
finds the files and prints it.

CLARIFICATION_NEEDED counts are the point: docs/ai-assistant-widget-rollout-
plan.md Fase 1 calls this out explicitly as "daftar lubang KB" (the knowledge
base's gap list) -- the report exists to surface it, not just count questions.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

DEFAULT_DATA_DIR = Path("/var/lib/nexora-feedback")


def load_ndjson(path: Path) -> list[dict]:
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue  # a corrupt line must not sink the whole report
    return records


def reviewer_key(record: dict) -> str:
    reviewer = (record.get("payload") or {}).get("reviewer")
    if reviewer and reviewer.get("email"):
        return reviewer["email"]
    if record.get("remote_user"):
        return f"basic-auth:{record['remote_user']}"
    return "unknown"


def summarize(records: list[dict]) -> dict:
    """Returns {app: {reviewers: {key: {...}}, gate: {...} | None}}."""
    by_app: dict[str, dict] = {}

    for rec in records:
        app = rec.get("app", "unknown")
        app_summary = by_app.setdefault(
            app, {"reviewers": {}, "latest_signoff": None, "gap_questions": {}})
        reviewers = app_summary["reviewers"]
        rkey = reviewer_key(rec)
        r = reviewers.setdefault(rkey, {
            "questions": 0,
            "clarification_needed": [],
            "findings_recorded": 0,
            "findings_open_at_last_seen": None,
            "last_seen": None,
        })

        rtype = rec.get("type")
        payload = rec.get("payload") or {}

        if rtype == "question.asked":
            r["questions"] += 1
        elif rtype == "answer.given" and payload.get("classification") == "CLARIFICATION_NEEDED":
            r["clarification_needed"].append(rec.get("received_at"))
            # The reviewer's actual words are the gap list. Counted per
            # (question, screen) so a question that keeps failing on one screen
            # rises to the top of the KB backlog. Rows written before
            # 2026-09-19 carry no question text -- they stay countable but
            # unlistable, which is exactly why the text is captured now.
            q = (payload.get("question") or "").strip()
            if q:
                key = (q, payload.get("screen") or payload.get("route") or "—")
                app_summary["gap_questions"][key] = app_summary["gap_questions"].get(key, 0) + 1
        elif rtype == "finding.recorded":
            r["findings_recorded"] += 1
        elif rtype == "baseline.signoff":
            app_summary["latest_signoff"] = {
                "status": payload.get("status"),
                "by": rkey,
                "at": rec.get("received_at"),
            }

        seen = rec.get("received_at")
        if seen and (r["last_seen"] is None or seen > r["last_seen"]):
            r["last_seen"] = seen

    return by_app


def render(summary: dict) -> str:
    if not summary:
        return "no feedback recorded yet"
    lines = []
    for app in sorted(summary):
        data = summary[app]
        lines.append(f"== {app}")
        for rkey in sorted(data["reviewers"]):
            r = data["reviewers"][rkey]
            gap = len(r["clarification_needed"])
            lines.append(
                f"  {rkey}: {r['questions']} question(s), "
                f"{gap} CLARIFICATION_NEEDED (KB gap), "
                f"{r['findings_recorded']} finding(s) recorded, "
                f"last seen {r['last_seen'] or '—'}"
            )
        signoff = data["latest_signoff"]
        if signoff:
            lines.append(f"  latest sign-off: {signoff['status']} by {signoff['by']} @ {signoff['at']}")

        gaps = data.get("gap_questions") or {}
        total_gap = sum(len(r["clarification_needed"]) for r in data["reviewers"].values())
        if gaps:
            lines.append("  KB gap list — questions the assistant could NOT answer:")
            for (q, screen), n in sorted(gaps.items(), key=lambda kv: (-kv[1], kv[0][0]))[:15]:
                lines.append(f"    {n}x [{screen}] {q}")
        elif total_gap:
            lines.append(
                f"  KB gap list: {total_gap} unanswered question(s) recorded without text "
                "(question text is captured only from 2026-09-19 onward)"
            )
    return "\n".join(lines)


def collect_records(data_dir: Path, app: str | None, since_days: int | None) -> list[dict]:
    cutoff = None
    if since_days is not None:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=since_days)).strftime("%Y-%m-%d")

    apps = [app] if app else sorted(p.name for p in data_dir.iterdir() if p.is_dir()) if data_dir.exists() else []
    records: list[dict] = []
    for a in apps:
        app_dir = data_dir / a
        if not app_dir.is_dir():
            continue
        for path in sorted(app_dir.glob("*.ndjson")):
            date = path.stem
            if cutoff and date < cutoff:
                continue
            records.extend(load_ndjson(path))
    return records


def main(argv: list[str]) -> int:
    app = None
    since_days = None
    data_dir = DEFAULT_DATA_DIR
    args = list(argv[1:])
    while args:
        a = args.pop(0)
        if a == "--since":
            since_days = int(args.pop(0))
        elif a == "--data-dir":
            data_dir = Path(args.pop(0))
        elif not a.startswith("-"):
            app = a
        else:
            print(f"usage: feedback_report.py [app] [--since DAYS] [--data-dir DIR]", file=sys.stderr)
            return 2

    records = collect_records(data_dir, app, since_days)
    print(render(summarize(records)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
