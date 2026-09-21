#!/usr/bin/env python3
"""Widget feedback collector -- "tersimpan, tidak boleh hilang" (owner decision,
docs/ai-assistant-widget-rollout-plan.md §7).

Stdlib only, no dependencies, loopback-only. A separate service from
bin/lib/dash.py on purpose: dash.py is the control-plane that spawns agent
processes; this is passive browser ingest and must not share that surface
(same rollout plan, §Fase 1).

Durability model:
  * append-only NDJSON, one line per event, fsync()'d before the response
    is sent -- a crash right after the response means the line already
    survived a fsync, not that it is still only in an OS buffer.
  * one file per app per UTC calendar day: /var/lib/nexora-feedback/<app>/<date>.ndjson
  * duplicate eventId is skipped, not re-appended, and the dedup set is
    reloaded from the day's file at startup -- a restarted process (the
    outbox-retry drill in the rollout plan's Fase 1 gate) must not
    re-accept a duplicate just because its in-memory set was reset to empty.
  * received_at and remote_user are server-asserted. A client cannot set
    either (CLAUDE.md's "measure, do not estimate" / "do not trust a client
    timestamp" lesson applies here as much as it does to browser probes).
"""
from __future__ import annotations

import json
import os
import re
import sys
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

MAX_BODY_BYTES_DEFAULT = 64 * 1024
MAX_EVENTS_PER_BATCH = 50

APP_NAME_RE = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")
EVENT_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")

TOP_LEVEL_FIELDS = {"app", "events"}
EVENT_REQUIRED_FIELDS = {"eventId", "sessionId", "type"}
EVENT_ALLOWED_FIELDS = EVENT_REQUIRED_FIELDS | {"actor", "payload", "clientAt"}


class ValidationError(Exception):
    pass


class PayloadTooLarge(ValidationError):
    pass


def parse_and_validate(raw: bytes, max_body_bytes: int) -> tuple[str, list[dict]]:
    """Returns (app, events) or raises ValidationError/PayloadTooLarge.

    Fails closed: anything not explicitly recognised is rejected rather than
    passed through, since this endpoint is reachable straight from a browser.
    """
    if len(raw) > max_body_bytes:
        raise PayloadTooLarge(f"body exceeds {max_body_bytes} bytes")

    try:
        body = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationError(f"malformed JSON: {exc}") from exc

    if not isinstance(body, dict):
        raise ValidationError("body must be a JSON object")

    unknown = set(body.keys()) - TOP_LEVEL_FIELDS
    if unknown:
        raise ValidationError(f"unknown top-level field(s): {sorted(unknown)}")

    app = body.get("app")
    if not isinstance(app, str) or not APP_NAME_RE.match(app):
        raise ValidationError("app must be a short lowercase identifier")

    events = body.get("events")
    if not isinstance(events, list) or not events:
        raise ValidationError("events must be a non-empty array")
    if len(events) > MAX_EVENTS_PER_BATCH:
        raise ValidationError(f"batch exceeds {MAX_EVENTS_PER_BATCH} events")

    for ev in events:
        if not isinstance(ev, dict):
            raise ValidationError("each event must be a JSON object")
        missing = EVENT_REQUIRED_FIELDS - set(ev.keys())
        if missing:
            raise ValidationError(f"event missing field(s): {sorted(missing)}")
        unknown_event_fields = set(ev.keys()) - EVENT_ALLOWED_FIELDS
        if unknown_event_fields:
            raise ValidationError(f"event has unknown field(s): {sorted(unknown_event_fields)}")
        if not isinstance(ev["eventId"], str) or not EVENT_ID_RE.match(ev["eventId"]):
            raise ValidationError("eventId must be a short opaque identifier")
        if not isinstance(ev["sessionId"], str) or not ev["sessionId"]:
            raise ValidationError("sessionId must be a non-empty string")
        if not isinstance(ev["type"], str) or not ev["type"]:
            raise ValidationError("type must be a non-empty string")

    return app, events


class FeedbackStore:
    """Append-only NDJSON, one directory per app, one file per UTC day.

    Dedup is keyed on eventId and reloaded from disk on construction, so a
    process restart does not forget what it already durably wrote.
    """

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self._lock = threading.Lock()
        self._seen: dict[str, set[str]] = {}  # f"{app}:{date}" -> {eventId, ...}

    def _seen_key(self, app: str, date: str) -> str:
        return f"{app}:{date}"

    def _load_seen(self, app: str, date: str) -> set[str]:
        key = self._seen_key(app, date)
        if key in self._seen:
            return self._seen[key]
        ids: set[str] = set()
        path = self._path(app, date)
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line:
                    continue
                try:
                    ids.add(json.loads(line)["eventId"])
                except (json.JSONDecodeError, KeyError):
                    continue
        self._seen[key] = ids
        return ids

    def _path(self, app: str, date: str) -> Path:
        return self.base_dir / app / f"{date}.ndjson"

    def append(self, app: str, event: dict, *, remote_user: str | None,
               received_at: str, server_date: str) -> str:
        """Returns "accepted" or "duplicate". Never raises for a duplicate --
        a retried delivery is expected, not an error."""
        with self._lock:
            seen = self._load_seen(app, server_date)
            if event["eventId"] in seen:
                return "duplicate"

            path = self._path(app, server_date)
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o750)
            os.chmod(path.parent, 0o750)

            record = dict(event)
            record["app"] = app
            record["remote_user"] = remote_user
            record["received_at"] = received_at

            line = json.dumps(record, ensure_ascii=False) + "\n"
            fd = os.open(str(path), os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o640)
            try:
                os.write(fd, line.encode("utf-8"))
                os.fsync(fd)
            finally:
                os.close(fd)
            os.chmod(path, 0o640)

            seen.add(event["eventId"])
            return "accepted"


class RateLimiter:
    """Fixed-window limiter, per key (typically the client IP)."""

    def __init__(self, max_per_window: int, window_seconds: float):
        self.max_per_window = max_per_window
        self.window_seconds = window_seconds
        self._lock = threading.Lock()
        self._windows: dict[str, tuple[float, int]] = {}  # key -> (window_start, count)

    def allow(self, key: str, now: float | None = None) -> bool:
        now = time.time() if now is None else now
        with self._lock:
            start, count = self._windows.get(key, (now, 0))
            if now - start >= self.window_seconds:
                start, count = now, 0
            if count >= self.max_per_window:
                self._windows[key] = (start, count)
                return False
            self._windows[key] = (start, count + 1)
            return True


def make_handler(store: FeedbackStore, rate_limiter: RateLimiter, max_body_bytes: int):
    class Handler(BaseHTTPRequestHandler):
        server_version = "ah-feedback/1"

        def log_message(self, fmt, *args):  # quiet by default; systemd captures stdout
            pass

        def _send_json(self, status: int, payload: dict):
            body = json.dumps(payload).encode("utf-8")
            try:
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                # The client hung up before we finished replying. This is NORMAL
                # for the widget's outbox flush: fetch() and, on pagehide,
                # sendBeacon() close the socket the instant the batch is sent.
                # Every event was already persisted by store.append() before we
                # got here, so the 200 body is moot -- swallow the disconnect
                # quietly instead of letting socketserver log a traceback for
                # lossless, expected behaviour (journal noise, 2026-09-18 14:29Z).
                pass

        def do_GET(self):
            if self.path == "/healthz":
                self._send_json(200, {"ok": True})
            elif self.path == "/collect":
                self._send_json(405, {"error": "method not allowed"})
            else:
                self._send_json(404, {"error": "not found"})

        def do_POST(self):
            if self.path != "/collect":
                self._send_json(404, {"error": "not found"})
                return

            client_ip = self.headers.get("X-Real-IP", self.client_address[0])
            if not rate_limiter.allow(client_ip):
                self._send_json(429, {"error": "rate limit exceeded"})
                return

            declared_length = self.headers.get("Content-Length")
            try:
                length = int(declared_length) if declared_length is not None else 0
            except ValueError:
                self._send_json(400, {"error": "invalid Content-Length"})
                return
            if length > max_body_bytes:
                self._send_json(413, {"error": "payload too large"})
                return

            raw = self.rfile.read(length) if length else b""

            try:
                app, events = parse_and_validate(raw, max_body_bytes)
            except PayloadTooLarge as exc:
                self._send_json(413, {"error": str(exc)})
                return
            except ValidationError as exc:
                self._send_json(400, {"error": str(exc)})
                return

            remote_user = self.headers.get("X-Remote-User") or None
            received_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
            server_date = received_at[:10]

            accepted = 0
            duplicate = 0
            for ev in events:
                outcome = store.append(app, ev, remote_user=remote_user,
                                        received_at=received_at, server_date=server_date)
                if outcome == "accepted":
                    accepted += 1
                else:
                    duplicate += 1

            self._send_json(200, {"accepted": accepted, "duplicate": duplicate})

    return Handler


def make_server(address: tuple[str, int], data_dir: Path,
                 max_body_bytes: int = MAX_BODY_BYTES_DEFAULT,
                 rate_limit_per_minute: int = 60) -> ThreadingHTTPServer:
    store = FeedbackStore(data_dir)
    rate_limiter = RateLimiter(max_per_window=rate_limit_per_minute, window_seconds=60.0)
    handler = make_handler(store, rate_limiter, max_body_bytes)
    return ThreadingHTTPServer(address, handler)


def main(argv: list[str]) -> int:
    host = os.environ.get("AH_FEEDBACK_HOST", "127.0.0.1")
    port = int(os.environ.get("AH_FEEDBACK_PORT", "7788"))
    data_dir = Path(os.environ.get("AH_FEEDBACK_DATA_DIR", "/var/lib/nexora-feedback"))
    server = make_server((host, port), data_dir)
    print(f"ah-feedback listening on {host}:{port}, data_dir={data_dir}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
