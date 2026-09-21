#!/usr/bin/env python3
"""Scheduled Friday-morning weekly report: write it down, then send it.

Order matters. The file is written first so a Telegram outage costs a
notification, not the week's report -- there has to be something to point at in
the meeting either way.
"""
from __future__ import annotations

import datetime as dt
import re
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import jobs      # noqa: E402
import state     # noqa: E402
import tgcore    # noqa: E402
import weekly    # noqa: E402


def to_markdown(html_text: str) -> str:
    """Telegram HTML to plain Markdown for the file kept in agents/reports/."""
    text = html_text.replace("<code>", "`").replace("</code>", "`")
    text = re.sub(r"<b>(.*?)</b>", r"**\1**", text, flags=re.S)
    text = re.sub(r"<[^>]+>", "", text)
    for entity, char in (("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'), ("&amp;", "&")):
        text = text.replace(entity, char)
    return text


def main() -> int:
    now = time.time()
    html_report = weekly.report(state.snapshot(), jobs.listing(200), now=now)

    stamp = dt.datetime.fromtimestamp(now, dt.timezone.utc).strftime("%Y-%m-%d")
    path = state.REPORTS / f"weekly-{stamp}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    # Same day, same file: a re-run replaces the report rather than adding a
    # second one for the same week.
    path.write_text(to_markdown(html_report), encoding="utf-8")
    print(f"weekly report written: {path}")

    targets = tgcore.notification_targets(tgcore.load_config())
    if not targets:
        print("no paired Telegram chat; report not sent")
        return 0

    for chat in targets:
        try:
            result = tgcore.send(chat, html_report)
            print(f"sent to {chat}: {'ok' if result.get('ok') else result}")
        except Exception:
            # The report is already on disk; a failed send must not fail the run
            # or stop the remaining targets.
            traceback.print_exc()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
