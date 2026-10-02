"""Feedback collector: "tersimpan, tidak boleh hilang" must hold under retry,
duplicate delivery, and an oversized/malformed client -- not just the happy path.

docs/ai-assistant-widget-rollout-plan.md Fase 1 is explicit: append-only NDJSON,
fsync per line, daily rotation, duplicate `eventId` rejected, oversized body
rejected, unknown fields rejected, `remote_user` and `received_at` are
server-asserted facts the client cannot forge. These tests exercise the pure
logic (validation, storage, rate limiting) directly, plus one end-to-end round
trip through the real HTTP server, mirroring how ops/nginx/validate_vhost.py
and ops/n8n/validate_env.py are tested here: no I/O surprises, a list of
problems, and the artefact itself asserted last.
"""
from __future__ import annotations

import http.client
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import collector  # noqa: E402


def event(event_id="ev-1", session_id="sess-1", **overrides):
    base = {
        "eventId": event_id,
        "sessionId": session_id,
        "type": "question.asked",
        "actor": "Joan Marsh",
        "payload": {"classification": "ANSWERED_FROM_SOURCE", "route": "readiness"},
        "clientAt": "2026-09-18T05:00:00.000Z",
    }
    base.update(overrides)
    return base


def batch(app="accreditation", events=None, **overrides):
    body = {"app": app, "events": events if events is not None else [event()]}
    body.update(overrides)
    return body


class ParseAndValidateTests(unittest.TestCase):
    def test_accepts_a_well_formed_batch(self):
        app, events = collector.parse_and_validate(json.dumps(batch()).encode(), max_body_bytes=65536)
        self.assertEqual(app, "accreditation")
        self.assertEqual(len(events), 1)

    def test_rejects_body_over_the_size_limit(self):
        oversized = json.dumps(batch(events=[event(payload={"pad": "x" * 100})])).encode()
        with self.assertRaises(collector.PayloadTooLarge):
            collector.parse_and_validate(oversized, max_body_bytes=10)

    def test_rejects_unknown_top_level_field(self):
        payload = batch()
        payload["sql"] = "drop table findings"
        with self.assertRaises(collector.ValidationError):
            collector.parse_and_validate(json.dumps(payload).encode(), max_body_bytes=65536)

    def test_rejects_unknown_app_name(self):
        with self.assertRaises(collector.ValidationError):
            collector.parse_and_validate(
                json.dumps(batch(app="../../etc")).encode(), max_body_bytes=65536)

    def test_rejects_empty_events_array(self):
        with self.assertRaises(collector.ValidationError):
            collector.parse_and_validate(json.dumps(batch(events=[])).encode(), max_body_bytes=65536)

    def test_rejects_event_missing_a_required_field(self):
        broken = event()
        del broken["eventId"]
        with self.assertRaises(collector.ValidationError):
            collector.parse_and_validate(json.dumps(batch(events=[broken])).encode(), max_body_bytes=65536)

    def test_rejects_event_carrying_a_client_supplied_received_at(self):
        # received_at is a server-asserted fact -- CLAUDE.md's own lesson about
        # not trusting client timestamps applies here as much as it does to
        # NDJSON durability.
        tampered = event(receivedAt="2020-01-01T00:00:00Z")
        with self.assertRaises(collector.ValidationError):
            collector.parse_and_validate(json.dumps(batch(events=[tampered])).encode(), max_body_bytes=65536)

    def test_caps_events_per_batch(self):
        many = [event(event_id=f"ev-{i}") for i in range(collector.MAX_EVENTS_PER_BATCH + 1)]
        with self.assertRaises(collector.ValidationError):
            collector.parse_and_validate(json.dumps(batch(events=many)).encode(), max_body_bytes=10_000_000)

    def test_rejects_malformed_json(self):
        with self.assertRaises(collector.ValidationError):
            collector.parse_and_validate(b"{not json", max_body_bytes=65536)


class FeedbackStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = collector.FeedbackStore(Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def _lines(self, app, date):
        path = Path(self.tmp.name) / app / f"{date}.ndjson"
        return [json.loads(line) for line in path.read_text().splitlines() if line]

    def test_append_writes_one_ndjson_line_with_server_fields(self):
        outcome = self.store.append(
            "accreditation", event(), remote_user="imam", received_at="2026-09-18T05:00:01Z",
            server_date="2026-09-18")
        self.assertEqual(outcome, "accepted")
        [line] = self._lines("accreditation", "2026-09-18")
        self.assertEqual(line["eventId"], "ev-1")
        self.assertEqual(line["remote_user"], "imam")
        self.assertEqual(line["received_at"], "2026-09-18T05:00:01Z")
        self.assertEqual(line["app"], "accreditation")

    def test_duplicate_event_id_is_skipped_not_re_appended(self):
        self.store.append("accreditation", event(), remote_user="imam",
                           received_at="2026-09-18T05:00:01Z", server_date="2026-09-18")
        outcome = self.store.append("accreditation", event(), remote_user="imam",
                                     received_at="2026-09-18T05:00:05Z", server_date="2026-09-18")
        self.assertEqual(outcome, "duplicate")
        self.assertEqual(len(self._lines("accreditation", "2026-09-18")), 1)

    def test_duplicate_check_survives_a_process_restart(self):
        # The outbox retry drill (Fase 1 gate) restarts the collector process;
        # dedup must be reloaded from disk, not rely on an in-memory set that
        # a restart would silently reset to empty.
        self.store.append("accreditation", event(), remote_user="imam",
                           received_at="2026-09-18T05:00:01Z", server_date="2026-09-18")
        fresh = collector.FeedbackStore(Path(self.tmp.name))
        outcome = fresh.append("accreditation", event(), remote_user="imam",
                                received_at="2026-09-18T05:00:09Z", server_date="2026-09-18")
        self.assertEqual(outcome, "duplicate")

    def test_different_apps_do_not_share_a_dedup_namespace(self):
        self.store.append("accreditation", event(), remote_user="imam",
                           received_at="2026-09-18T05:00:01Z", server_date="2026-09-18")
        outcome = self.store.append("academy", event(), remote_user="imam",
                                     received_at="2026-09-18T05:00:01Z", server_date="2026-09-18")
        self.assertEqual(outcome, "accepted")

    def test_rotates_by_server_date_not_client_date(self):
        self.store.append("accreditation", event(event_id="a"), remote_user="imam",
                           received_at="2026-09-18T23:59:59Z", server_date="2026-09-18")
        self.store.append("accreditation", event(event_id="b"), remote_user="imam",
                           received_at="2026-09-19T00:00:01Z", server_date="2026-09-19")
        self.assertEqual(len(self._lines("accreditation", "2026-09-18")), 1)
        self.assertEqual(len(self._lines("accreditation", "2026-09-19")), 1)

    def test_file_permissions_are_group_readable_only(self):
        self.store.append("accreditation", event(), remote_user="imam",
                           received_at="2026-09-18T05:00:01Z", server_date="2026-09-18")
        path = Path(self.tmp.name) / "accreditation" / "2026-09-18.ndjson"
        mode = path.stat().st_mode & 0o777
        self.assertEqual(mode, 0o640)

    def test_fsync_is_called_per_line(self):
        calls = []
        real_fsync = collector.os.fsync
        collector.os.fsync = lambda fd: calls.append(fd) or real_fsync(fd)
        try:
            self.store.append("accreditation", event(), remote_user="imam",
                               received_at="2026-09-18T05:00:01Z", server_date="2026-09-18")
        finally:
            collector.os.fsync = real_fsync
        self.assertEqual(len(calls), 1)


class RateLimiterTests(unittest.TestCase):
    def test_allows_up_to_the_limit_then_blocks(self):
        limiter = collector.RateLimiter(max_per_window=3, window_seconds=60)
        clock = [1000.0]
        allow = lambda: limiter.allow("1.2.3.4", now=clock[0])
        self.assertTrue(allow())
        self.assertTrue(allow())
        self.assertTrue(allow())
        self.assertFalse(allow())

    def test_window_resets_after_it_elapses(self):
        limiter = collector.RateLimiter(max_per_window=1, window_seconds=60)
        self.assertTrue(limiter.allow("1.2.3.4", now=1000.0))
        self.assertFalse(limiter.allow("1.2.3.4", now=1010.0))
        self.assertTrue(limiter.allow("1.2.3.4", now=1061.0))

    def test_keys_are_independent(self):
        limiter = collector.RateLimiter(max_per_window=1, window_seconds=60)
        self.assertTrue(limiter.allow("1.2.3.4", now=1000.0))
        self.assertTrue(limiter.allow("5.6.7.8", now=1000.0))


class SendJsonResilienceTests(unittest.TestCase):
    """A durability service must not spew tracebacks when the CLIENT hangs up.

    Root cause (journal, 2026-09-18 14:29Z): the widget flushes its outbox with
    fetch() and, on pagehide, sendBeacon(); both routinely close the socket the
    instant the batch is sent. store.append() has already persisted every event
    by then, so the events are safe -- but the follow-up self.wfile.write() of
    the 200 body hits a socket the client already closed, raising BrokenPipeError
    /ConnectionResetError. Unhandled, socketserver logs a full traceback for what
    is normal, lossless client behaviour. _send_json must swallow exactly those
    two and stay quiet (the response is moot -- the client is gone)."""

    def _bare_handler(self, wfile):
        # Build a Handler class, then an instance WITHOUT running __init__ (which
        # would try to service a real socket). _send_json only needs wfile plus
        # the response/header writers, which we stub to no-ops.
        with tempfile.TemporaryDirectory() as tmp:
            Handler = collector.make_handler(
                collector.FeedbackStore(Path(tmp)),
                collector.RateLimiter(max_per_window=60, window_seconds=60.0),
                65536,
            )
        h = Handler.__new__(Handler)
        h.wfile = wfile
        h.send_response = lambda *a, **k: None
        h.send_header = lambda *a, **k: None
        h.end_headers = lambda *a, **k: None
        return h

    def test_send_json_swallows_broken_pipe(self):
        class BrokenWFile:
            def write(self, _b):
                raise BrokenPipeError(32, "Broken pipe")
        # Must return normally -- a client that hung up is not an error.
        self._bare_handler(BrokenWFile())._send_json(200, {"accepted": 1})

    def test_send_json_swallows_connection_reset(self):
        class ResetWFile:
            def write(self, _b):
                raise ConnectionResetError(104, "Connection reset by peer")
        self._bare_handler(ResetWFile())._send_json(200, {"accepted": 1})

    def test_send_json_still_raises_unexpected_errors(self):
        # A genuine bug (not a client disconnect) must NOT be silently hidden.
        class WeirdWFile:
            def write(self, _b):
                raise ValueError("not a disconnect")
        with self.assertRaises(ValueError):
            self._bare_handler(WeirdWFile())._send_json(200, {"ok": True})


class EndToEndServerTests(unittest.TestCase):
    """One real HTTP round trip -- the parts a pure unit test cannot see:
    the handler wiring, header extraction, and status codes actually sent."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.server = collector.make_server(
            ("127.0.0.1", 0), data_dir=Path(self.tmp.name), max_body_bytes=65536)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_address[1]

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.tmp.cleanup()

    def _post(self, body: bytes, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("POST", "/collect", body=body, headers=headers or {})
        resp = conn.getresponse()
        data = resp.read()
        conn.close()
        return resp.status, data

    def test_healthz(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("GET", "/healthz")
        resp = conn.getresponse()
        self.assertEqual(resp.status, 200)
        conn.close()

    def test_collect_round_trip_persists_with_remote_user_and_received_at(self):
        status, data = self._post(
            json.dumps(batch()).encode(),
            headers={"Content-Type": "application/json", "X-Remote-User": "imam"})
        self.assertEqual(status, 200)
        result = json.loads(data)
        self.assertEqual(result["accepted"], 1)

        [path] = list((Path(self.tmp.name) / "accreditation").glob("*.ndjson"))
        line = json.loads(path.read_text().splitlines()[0])
        self.assertEqual(line["remote_user"], "imam")
        self.assertIn("received_at", line)

    def test_missing_remote_user_header_is_recorded_as_null_not_guessed(self):
        status, data = self._post(json.dumps(batch()).encode())
        self.assertEqual(status, 200)
        [path] = list((Path(self.tmp.name) / "accreditation").glob("*.ndjson"))
        line = json.loads(path.read_text().splitlines()[0])
        self.assertIsNone(line["remote_user"])

    def test_malformed_body_returns_400_and_writes_nothing(self):
        status, _ = self._post(b"{not json")
        self.assertEqual(status, 400)
        self.assertFalse((Path(self.tmp.name) / "accreditation").exists())

    def test_oversized_body_returns_413(self):
        huge = json.dumps(batch(events=[event(payload={"pad": "x" * 200_000})])).encode()
        status, _ = self._post(huge)
        self.assertEqual(status, 413)

    def test_get_to_collect_is_rejected(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("GET", "/collect")
        resp = conn.getresponse()
        self.assertEqual(resp.status, 405)
        conn.close()

    def test_unknown_path_is_404(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("GET", "/whatever")
        resp = conn.getresponse()
        self.assertEqual(resp.status, 404)
        conn.close()


if __name__ == "__main__":
    unittest.main()
