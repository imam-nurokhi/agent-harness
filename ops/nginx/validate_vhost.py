#!/usr/bin/env python3
"""Fail closed before nginx accepts the agents.nexoratech.co vhost.

Pure functions over the text of two files, mirroring ops/n8n/validate_env.py:
no I/O, no nginx invocation, just a list of problems that must be empty before
anything is copied onto the shared VPS.

Two rules here were each responsible for an outage:

* the sustained rate -- a browser opening the n8n editor fires dozens of asset
  requests at once and the dashboard polls /api/state every few seconds, so a
  zone that refills at 1r/s starves however large `burst` is; and
* the /automation/ trailing slash -- n8n 2.x serves its bundles from the server
  root, so a proxy_pass that keeps the prefix hands every asset back as
  index.html and the editor renders blank.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path


# MEASURED, not estimated. One cold load of the n8n editor through this vhost
# logged 797 requests (2026-09-17, chromium headless, empty cache, 794x200).
# An earlier guess of "40+ chunks" under-sized the limits by more than an order
# of magnitude and left the editor blank behind 429/503 even after the prefix
# fix, so this number is pinned here and in the tests.
EDITOR_COLD_LOAD_REQUESTS = 797

# The reservoir must absorb one whole cold load, or a hard refresh dies midway.
MIN_BURST = EDITOR_COLD_LOAD_REQUESTS

# And the refill must carry a full cold load every 20s, so back-to-back reloads
# recover instead of compounding.
MIN_SUSTAINED_RPS = EDITOR_COLD_LOAD_REQUESTS / 20

# On nginx 1.24 with HTTP/2, limit_conn counts each *stream* as a connection,
# not each TCP connection. A browser opens as many concurrent streams as
# http2_max_concurrent_streams allows, so limit_conn must sit above that ceiling
# or an ordinary page load answers 503. Measured: limit_conn 10 gave 629x503 and
# limit_conn 64 still gave 407x503 in one editor load.
#
# Both numbers are therefore pinned together: the stream ceiling is declared
# explicitly rather than left to nginx's default, and limit_conn keeps 2x
# headroom over it. limit_req does the rate work; limit_conn only stops one IP
# holding the worker pool.
H2_MAX_CONCURRENT_STREAMS = 128
MIN_CONN_LIMIT = 2 * H2_MAX_CONCURRENT_STREAMS

RATE_TOO_LOW = (
    f"limit_req_zone sustained rate is below {MIN_SUSTAINED_RPS:.1f}r/s; "
    "burst alone cannot carry a browser page load"
)
BURST_TOO_LOW = (
    f"limit_req burst is below {MIN_BURST}, one cold load of the n8n editor; "
    "a hard refresh will be cut off part-way and the editor renders blank"
)
CONN_LIMIT_TOO_LOW = (
    f"limit_conn allows fewer than {MIN_CONN_LIMIT} per IP; under HTTP/2 each "
    "stream counts as a connection, so an ordinary page load answers 503"
)
NO_H2_STREAM_CEILING = (
    f"vhost does not pin http2_max_concurrent_streams to "
    f"{H2_MAX_CONCURRENT_STREAMS}; limit_conn cannot be reasoned about without it"
)
NO_RATE_ZONE = "no limit_req_zone with a parseable rate= was found"
NO_RATE_LIMIT = "vhost does not apply limit_req"
NO_WEBSOCKET = "vhost does not forward Upgrade/Connection; the n8n editor push channel will fail"
NO_AUTH = "vhost does not require auth_basic"
NO_CONN_LIMIT = "vhost does not apply limit_conn"
NO_AUTOMATION_UPSTREAM = "vhost does not proxy /automation/ to 127.0.0.1:5678"
AUTOMATION_PREFIX_NOT_STRIPPED = (
    "proxy_pass for /automation/ must end in '/': n8n 2.x serves its bundles "
    "from the server root, so keeping the prefix resolves every asset to the "
    "SPA catch-all (index.html) and blanks the editor"
)
NO_AUTOMATION_REDIRECT = (
    "no 'location = /automation' redirect; the bare URL does not match "
    "'^~ /automation/' and falls through to the dashboard upstream"
)
MISSING_HEADER = "vhost no longer sets the %s response header"

REQUIRED_HEADERS = (
    "X-Content-Type-Options",
    "X-Frame-Options",
    "Referrer-Policy",
    "Strict-Transport-Security",
    "Content-Security-Policy",
)

_RATE_UNITS = {"s": 1.0, "m": 60.0}


def strip_comments(text: str) -> str:
    """Directives behind a '#' are not in force; treat them as absent."""
    return "\n".join(line.split("#", 1)[0] for line in text.splitlines())


def sustained_rate_per_second(zone_text: str) -> float:
    """The refill rate of the limit_req zone, in requests per second.

    Returns 0.0 when no zone declares a rate, so callers fail closed.
    """
    match = re.search(r"limit_req_zone[^;]*\brate=(\d+)r/([sm])", strip_comments(zone_text))
    if not match:
        return 0.0
    return int(match.group(1)) / _RATE_UNITS[match.group(2)]


def validate(zone_text: str, vhost_text: str) -> list[str]:
    problems: list[str] = []
    zone = strip_comments(zone_text)
    vhost = strip_comments(vhost_text)

    rate = sustained_rate_per_second(zone)
    if rate <= 0.0:
        problems.append(NO_RATE_ZONE)
    elif rate < MIN_SUSTAINED_RPS:
        problems.append(RATE_TOO_LOW)

    burst = re.search(r"^\s*limit_req\s+zone=\S+\s+burst=(\d+)", vhost, re.M)
    if not burst:
        problems.append(NO_RATE_LIMIT)
    elif int(burst.group(1)) < MIN_BURST:
        problems.append(BURST_TOO_LOW)

    conn = re.search(r"^\s*limit_conn\s+\w+\s+(\d+)", vhost, re.M)
    if not conn:
        problems.append(NO_CONN_LIMIT)
    elif int(conn.group(1)) < MIN_CONN_LIMIT:
        problems.append(CONN_LIMIT_TOO_LOW)
    if not re.search(r"^\s*auth_basic\s+\S", vhost, re.M):
        problems.append(NO_AUTH)

    if not re.search(r"proxy_set_header\s+Upgrade\s+\$http_upgrade", vhost):
        problems.append(NO_WEBSOCKET)
    elif not re.search(r"proxy_set_header\s+Connection\s+", vhost):
        problems.append(NO_WEBSOCKET)

    automation = re.search(r"proxy_pass\s+(http://127\.0\.0\.1:5678\S*);", vhost)
    if not automation:
        problems.append(NO_AUTOMATION_UPSTREAM)
    elif not automation.group(1).endswith("5678/"):
        problems.append(AUTOMATION_PREFIX_NOT_STRIPPED)

    if not re.search(r"location\s*=\s*/automation\s", vhost):
        problems.append(NO_AUTOMATION_REDIRECT)

    if not re.search(rf"^\s*http2_max_concurrent_streams\s+{H2_MAX_CONCURRENT_STREAMS}\s*;",
                     vhost, re.M):
        problems.append(NO_H2_STREAM_CEILING)

    for header in REQUIRED_HEADERS:
        if header not in vhost:
            problems.append(MISSING_HEADER % header)

    return problems


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: validate_vhost.py <zone.conf> <vhost.conf>", file=sys.stderr)
        return 2
    problems = validate(Path(argv[1]).read_text(encoding="utf-8"),
                        Path(argv[2]).read_text(encoding="utf-8"))
    for problem in problems:
        print(f"FAIL: {problem}")
    if problems:
        return 1
    print("OK: nginx artefacts satisfy the agents.nexoratech.co contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
