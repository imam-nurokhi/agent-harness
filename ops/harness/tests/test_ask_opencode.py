"""Permukaan izin + helper OpenAgentic untuk @AskNexAIBot.

Menjaga dua hal:
1. Pelebaran `asknexai-settings.json` tetap sempit: tepat dua allow
   path-scoped (satu Bash prefix ke helper, satu Write ke state file),
   tanpa bare `Bash`, tanpa bypass, dengan seluruh deny utuh.
2. Helper `ask-opencode` membentuk request OpenAI-compatible yang benar,
   memakai model utama lalu fallback, dan tidak pernah membocorkan API key.
"""
from __future__ import annotations

import importlib.util
import io
import json
import unittest
import urllib.error
from importlib.machinery import SourceFileLoader
from pathlib import Path
from unittest import mock


AIWS = Path("/home/ahagent/AI-Workspace")
ASKDIR = Path("/home/ahagent/ask-nexai")
SETTINGS = AIWS / "ops/channels/asknexai-settings.json"
HELPER = ASKDIR / "bin" / "ask-opencode"
STATE = ASKDIR / ".ai-provider.json"

REQUIRED_ALLOWS = {
    "Bash(/home/ahagent/ask-nexai/bin/ask-opencode *)",
    "Write(/home/ahagent/ask-nexai/.ai-provider.json)",
}


def load_helper():
    loader = SourceFileLoader("ask_opencode", str(HELPER))
    spec = importlib.util.spec_from_loader("ask_opencode", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


class SettingsNarrowTests(unittest.TestCase):
    def setUp(self):
        self.settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
        self.permissions = self.settings.get("permissions", {})
        self.allow = self.permissions.get("allow", [])
        self.deny = self.permissions.get("deny", [])

    def test_file_valid_dan_mode_bukan_bypass(self):
        self.assertIn("permissions", self.settings)
        self.assertNotEqual("bypassPermissions",
                            self.permissions.get("defaultMode"))

    def test_dua_allow_baru_ada_dan_tetap_sempit(self):
        for rule in REQUIRED_ALLOWS:
            self.assertIn(rule, self.allow)
        for rule in self.allow:
            self.assertNotEqual("Bash", rule)
            self.assertNotIn("Bash(*)", rule)

    def test_deny_utuh_bash_network_dan_kredensial(self):
        joined = " ".join(self.deny)
        for token in ("Bash", ".env", "mcp__claude_ai_Slack",
                      "mcp__claude_ai_github"):
            self.assertIn(token, joined, f"deny kehilangan {token}")


class StateDefaultTests(unittest.TestCase):
    def test_default_adalah_claude(self):
        state = json.loads(STATE.read_text(encoding="utf-8"))
        self.assertEqual("claude", state.get("provider"),
                         "default harus claude = perilaku persis seperti sekarang")


class HelperRequestTests(unittest.TestCase):
    def setUp(self):
        self.mod = load_helper()
        self.env_file = Path("/tmp/test-ask-opencode.env")
        self.env_file.write_text(
            "OPENCODE_BASE_URL=https://openagentic.id/api/v1\n"
            "OPENCODE_API_KEY=kunci-rahasia-uji\n", encoding="utf-8")
        self.mod.ENV_FILE = str(self.env_file)

    def tearDown(self):
        self.env_file.unlink(missing_ok=True)

    def _ok_response(self, text="jawaban"):
        body = json.dumps(
            {"choices": [{"message": {"content": text}}]}).encode()
        resp = mock.MagicMock()
        resp.read.return_value = body
        resp.__enter__.return_value = resp
        return resp

    def test_request_benar_dan_key_tidak_bocor_ke_output(self):
        with mock.patch.object(self.mod.urllib.request, "urlopen",
                               return_value=self._ok_response("halo")) as uo:
            code, out = self.mod.ask("apa itu NexAccred?")
        self.assertEqual(0, code)
        self.assertEqual("halo", out)
        self.assertNotIn("kunci-rahasia-uji", out)
        req = uo.call_args[0][0]
        self.assertTrue(
            req.full_url.endswith("/chat/completions"))
        self.assertEqual("Bearer kunci-rahasia-uji",
                         req.get_header("Authorization"))
        payload = json.loads(req.data.decode("utf-8"))
        self.assertEqual("openagentic/muse-spark-1.3-free",
                         payload["model"])
        self.assertEqual(1000, payload["max_tokens"])

    def test_model_ditolak_coba_fallback(self):
        err = urllib.error.HTTPError(
            "url", 400, "bad", {}, io.BytesIO(b'{"error":"no such model"}'))
        calls = []

        def fake(req, timeout=None):
            calls.append(json.loads(req.data.decode())["model"])
            if len(calls) == 1:
                raise err
            return self._ok_response("via fallback")

        with mock.patch.object(self.mod.urllib.request, "urlopen",
                               side_effect=fake):
            code, out = self.mod.ask("halo")
        self.assertEqual(0, code)
        self.assertEqual("via fallback", out)
        self.assertEqual(["openagentic/muse-spark-1.3-free",
                          "muse-spark-1.3-free"], calls)

    def test_retry_sekali_saat_502_lalu_sukses(self):
        err = urllib.error.HTTPError(
            "url", 502, "bad gateway", {},
            io.BytesIO(b'{"error":"proxy_error"}'))
        with mock.patch.object(self.mod.urllib.request, "urlopen",
                               side_effect=[err,
                                            self._ok_response("pulih")]):
            with mock.patch.object(self.mod.time, "sleep") as slp:
                code, out = self.mod.ask("halo")
        self.assertEqual(0, code)
        self.assertEqual("pulih", out)
        slp.assert_called_once()

    def test_gagal_total_kode_dua_tanpa_key_di_output(self):
        with mock.patch.object(self.mod.urllib.request, "urlopen",
                               side_effect=Exception("putus")):
            code, out = self.mod.ask("halo")
        self.assertEqual(2, code)
        self.assertTrue(out.startswith("ERROR:"))
        self.assertNotIn("kunci-rahasia-uji", out)


if __name__ == "__main__":
    unittest.main()
