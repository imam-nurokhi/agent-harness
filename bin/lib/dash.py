"""Command Center server. Local-only, token-guarded, stdlib only."""
from __future__ import annotations

import json
import secrets
import subprocess
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).parent))
import jobs   # noqa: E402
import state  # noqa: E402

HERE = Path(__file__).parent
PORT = 7777
MAX_BODY = 256 * 1024

# This server starts processes. Bound to loopback, and every mutating call must
# carry this token, so another page in the browser cannot drive the harness.
TOKEN = secrets.token_urlsafe(24)

STATIC = {
    "dash.css": "text/css; charset=utf-8",
    "dash.js": "application/javascript; charset=utf-8",
}


class Handler(BaseHTTPRequestHandler):
    server_version = "AgentHarness"

    # ---------------------------------------------------------------- plumbing

    def _send(self, body: bytes, ctype: str, code: int = 200) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _json(self, obj, code: int = 200) -> None:
        self._send(json.dumps(obj).encode(), "application/json", code)

    def _authed(self) -> bool:
        return secrets.compare_digest(self.headers.get("X-AH-Token", ""), TOKEN)

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0 or n > MAX_BODY:
            return {}
        try:
            return json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            return {}

    # ------------------------------------------------------------------- GET

    def do_GET(self) -> None:  # noqa: N802
        url = urlparse(self.path)
        path, qs = url.path, parse_qs(url.query)
        try:
            if path in ("/", "/index.html"):
                html = (HERE / "dash.html").read_text()
                html = html.replace("__AH_TOKEN__", TOKEN)
                self._send(html.encode(), "text/html; charset=utf-8")
            elif path.lstrip("/") in STATIC:
                name = path.lstrip("/")
                self._send((HERE / name).read_bytes(), STATIC[name])
            elif path == "/api/state":
                snap = state.snapshot()
                snap["jobs"] = jobs.listing()
                self._json(snap)
            elif path == "/api/tail":
                jid = (qs.get("id") or [""])[0]
                off = int((qs.get("offset") or ["0"])[0])
                self._json(jobs.tail(jid, off))
            else:
                self._send(b"not found", "text/plain", 404)
        except Exception as exc:
            self._json({"error": str(exc)}, 500)

    # ------------------------------------------------------------------ POST

    def do_POST(self) -> None:  # noqa: N802
        if not self._authed():
            return self._json({"error": "bad or missing token"}, 403)
        path = urlparse(self.path).path
        body = self._body()
        try:
            if path == "/api/dispatch":
                meta = jobs.spawn(
                    role=body.get("role", ""),
                    prompt=body.get("prompt", ""),
                    task_id=body.get("task", ""),
                )
                self._json({"ok": True, "job": meta})
            elif path == "/api/stop":
                self._json(jobs.stop(body.get("id", "")))
            elif path == "/api/task/new":
                self._json(self._new_task(body.get("title", "")))
            elif path == "/api/trigger/run":
                self._json(self._run_trigger(body.get("id", "")))
            else:
                self._json({"error": "not found"}, 404)
        except ValueError as exc:
            self._json({"error": str(exc)}, 400)
        except Exception as exc:
            self._json({"error": str(exc)}, 500)

    # ------------------------------------------------------------- operations

    def _new_task(self, title: str) -> dict:
        title = (title or "").strip()
        if not title:
            raise ValueError("title is required")
        out = subprocess.run(
            [str(state.WORKSPACE / "bin" / "ah"), "task", "new", title],
            capture_output=True, text=True, timeout=20,
        )
        if out.returncode != 0:
            raise ValueError(out.stderr.strip() or "ah task new failed")
        return {"ok": True, "output": out.stdout.strip()}

    def _run_trigger(self, tid: str) -> dict:
        trg = next((t for t in state.triggers() if t["id"] == tid), None)
        if not trg:
            raise ValueError(f"no such trigger: {tid}")
        meta = jobs.spawn(role=trg.get("role") or "lead", prompt=trg["prompt"])
        return {"ok": True, "job": meta}

    def log_message(self, *_args) -> None:
        pass


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else PORT
    url = f"http://127.0.0.1:{port}/"
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"\n  Command Center  ->  {url}")
    print("  Local only. Mutating calls are token-guarded.")
    print("  Ctrl-C to stop\n")
    try:
        webbrowser.open(url)
    except Exception:
        pass
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n  stopped\n")


if __name__ == "__main__":
    main()
