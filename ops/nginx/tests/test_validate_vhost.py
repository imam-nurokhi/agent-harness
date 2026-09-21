from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import validate_vhost  # noqa: E402


# The rate-limit zone and vhost as they were deployed on 31.97.67.241 before
# this pass. Both symptoms the owner reported (dashboard stuck on "connecting…",
# /automation/ blank) trace to this shape: a browser page load issues far more
# requests than 60r/m sustains, so nginx answers 429 for dash.js and for the
# n8n asset chunks.
DEPLOYED_ZONE = """
limit_req_zone $binary_remote_addr zone=agents_per_ip:10m rate=60r/m;
limit_conn_zone $binary_remote_addr zone=agents_conn:10m;
"""

DEPLOYED_VHOST = """
server {
    listen 443 ssl http2;
    server_name agents.nexoratech.co;
    auth_basic "restricted";
    auth_basic_user_file /etc/nginx/agents.htpasswd;
    limit_req zone=agents_per_ip burst=200 nodelay;
    limit_conn agents_conn 20;
    location / { proxy_pass http://127.0.0.1:7777; }
    location /automation/ { proxy_pass http://127.0.0.1:5678; }
}
"""


def artifact(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


class DeployedConfigTests(unittest.TestCase):
    """The shape that produced the reported outage must be rejected."""

    def test_sustained_rate_too_low_for_a_browser_page_load(self):
        problems = validate_vhost.validate(DEPLOYED_ZONE, DEPLOYED_VHOST)
        self.assertIn(validate_vhost.RATE_TOO_LOW, problems)

    def test_burst_alone_does_not_make_the_config_acceptable(self):
        problems = validate_vhost.validate(DEPLOYED_ZONE, DEPLOYED_VHOST)
        self.assertNotEqual([], problems)


class WidgetFeedbackLocationTests(unittest.TestCase):
    """docs/ai-assistant-widget-rollout-plan.md Fase 1: one new, additive
    location for the feedback collector. It must restate every header (an
    add_header anywhere in a location replaces the whole inherited set, same
    lesson as the three prototype blocks above it) and must not touch them.
    """

    def setUp(self):
        self.vhost = artifact("agents.nexoratech.co.conf")
        match = re.search(
            r"location \^~ /widget-feedback/ \{.*?\n    \}\n", self.vhost, re.S)
        self.assertIsNotNone(match, "no /widget-feedback/ location found")
        self.block = match.group(0)

    def test_proxies_to_the_collector_on_loopback(self):
        self.assertIn("proxy_pass http://127.0.0.1:7788/;", self.block)

    def test_forwards_remote_user_and_client_ip_for_the_collector_to_trust(self):
        # The collector treats remote_user/received_at as server-asserted
        # facts (ops/feedback/collector.py); it can only do that if nginx is
        # the one setting them, not a header the browser could forge.
        self.assertIn("proxy_set_header X-Remote-User $remote_user;", self.block)
        self.assertIn("proxy_set_header X-Real-IP $remote_addr;", self.block)

    def test_uses_the_same_prototype_credential_as_the_three_apps(self):
        self.assertIn("auth_basic_user_file /etc/nginx/.prototypes.htpasswd;", self.block)

    def test_restates_every_required_header(self):
        for header in ("X-Content-Type-Options", "X-Frame-Options", "Referrer-Policy",
                       "Permissions-Policy", "Strict-Transport-Security", "X-Robots-Tag"):
            self.assertIn(header, self.block, f"{header} missing from /widget-feedback/ block")

    def test_the_three_prototype_blocks_are_untouched(self):
        for app in ("academy", "accreditation", "servicedesk"):
            match = re.search(rf"location \^~ /{app}/ \{{.*?\n    \}}\n", self.vhost, re.S)
            self.assertIsNotNone(match, f"{app} location missing entirely")
            self.assertIn("root /var/www/prototypes;", match.group(0))

    def test_full_artifact_still_satisfies_the_vhost_contract(self):
        zone = artifact("agents-rate-limit.conf")
        self.assertEqual([], validate_vhost.validate(zone, self.vhost))


class ReviewedArtifactTests(unittest.TestCase):
    """The artifact committed here is what should be deployed."""

    def setUp(self):
        self.zone = artifact("agents-rate-limit.conf")
        self.vhost = artifact("agents.nexoratech.co.conf")

    def test_reviewed_artifact_is_accepted(self):
        self.assertEqual([], validate_vhost.validate(self.zone, self.vhost))

    def test_rate_sustains_a_full_editor_cold_load_every_twenty_seconds(self):
        self.assertGreaterEqual(validate_vhost.sustained_rate_per_second(self.zone),
                                validate_vhost.MIN_SUSTAINED_RPS)

    def test_burst_absorbs_one_whole_editor_cold_load(self):
        # Measured through this vhost on 2026-09-17: 797 requests, 794 of them
        # 200, for one cold load of the editor with an empty cache. The earlier
        # "40+ chunks" estimate under-sized burst and rate by more than 10x and
        # the editor stayed blank behind 429/503 even once routing was correct.
        self.assertGreaterEqual(validate_vhost.EDITOR_COLD_LOAD_REQUESTS, 797)
        problems = validate_vhost.validate(
            self.zone, self.vhost.replace("burst=1200", "burst=200"))
        self.assertIn(validate_vhost.BURST_TOO_LOW, problems)

    def test_connection_limit_clears_the_http2_stream_ceiling(self):
        # nginx 1.24 counts each HTTP/2 stream as a connection for limit_conn.
        # Measured through this vhost on 2026-09-17, one editor load each:
        #   limit_conn 10 -> 629 x 503
        #   limit_conn 64 -> 407 x 503
        #   limit_conn 256 -> 0 x 503, editor renders
        self.assertGreaterEqual(validate_vhost.MIN_CONN_LIMIT,
                                2 * validate_vhost.H2_MAX_CONCURRENT_STREAMS)
        problems = validate_vhost.validate(
            self.zone, self.vhost.replace("agents_conn_per_ip 256", "agents_conn_per_ip 64"))
        self.assertIn(validate_vhost.CONN_LIMIT_TOO_LOW, problems)

    def test_http2_stream_ceiling_is_pinned_not_left_to_the_default(self):
        # limit_conn is only meaningful relative to this number, so it must be
        # stated in the file rather than inherited from whatever nginx defaults
        # to in the version that happens to be installed.
        problems = validate_vhost.validate(
            self.zone, self.vhost.replace("http2_max_concurrent_streams", "# pinned"))
        self.assertIn(validate_vhost.NO_H2_STREAM_CEILING, problems)

    def test_automation_prefix_is_stripped_before_the_upstream(self):
        # Verified against the running container (n8n 2.39.6) on 2026-09-17, not
        # assumed. n8n serves its bundles from the server ROOT -- /assets/... and
        # /static/... -- and no longer mounts them under N8N_PATH. N8N_PATH only
        # still controls the prefix the HTML *references*.
        #
        #   GET 127.0.0.1:5678/assets/index-DbGpghR9.js
        #       -> 200 text/javascript        890935 bytes
        #   GET 127.0.0.1:5678/automation/assets/index-DbGpghR9.js
        #       -> 200 text/html               56733 bytes   (the SPA catch-all)
        #
        # So without the trailing slash every asset resolves to index.html, and
        # `nosniff` stops the browser executing it: a blank white editor. The
        # trailing slash is load-bearing, and an earlier handoff asserted the
        # exact opposite -- hence this test.
        self.assertEqual([], validate_vhost.validate(self.zone, self.vhost))
        self.assertIn("proxy_pass http://127.0.0.1:5678/;", self.vhost)

    def test_a_vhost_that_keeps_the_prefix_is_rejected(self):
        kept = self.vhost.replace("proxy_pass http://127.0.0.1:5678/;",
                                  "proxy_pass http://127.0.0.1:5678;")
        self.assertIn(validate_vhost.AUTOMATION_PREFIX_NOT_STRIPPED,
                      validate_vhost.validate(self.zone, kept))

    def test_bare_automation_redirects_to_the_trailing_slash_form(self):
        # location ^~ /automation/ does not match /automation, so without this
        # the bare URL falls through to the dashboard upstream.
        self.assertIn(validate_vhost.NO_AUTOMATION_REDIRECT,
                      validate_vhost.validate(
                          self.zone,
                          self.vhost.replace("location = /automation ", "location = /unused ")))

    def test_websocket_upgrade_is_forwarded_for_the_editor(self):
        problems = validate_vhost.validate(
            self.zone, self.vhost.replace("proxy_set_header Upgrade $http_upgrade;", ""))
        self.assertIn(validate_vhost.NO_WEBSOCKET, problems)

    def test_auth_and_connection_limit_are_still_required(self):
        self.assertIn(validate_vhost.NO_AUTH,
                      validate_vhost.validate(self.zone, self.vhost.replace("auth_basic ", "# auth_basic ")))
        self.assertIn(validate_vhost.NO_CONN_LIMIT,
                      validate_vhost.validate(self.zone, self.vhost.replace("limit_conn ", "# limit_conn ")))

    def test_inline_svg_favicon_is_allowed_but_nothing_wider(self):
        # The dashboard's favicon is a data: URI. Allowing it is the only
        # widening this policy has had; scripts must stay same-origin.
        self.assertIn("img-src 'self' data:", self.vhost)
        self.assertNotIn("script-src 'self' 'unsafe-inline' data:", self.vhost)
        self.assertNotIn("'unsafe-eval'", self.vhost)

    def test_security_headers_are_still_required(self):
        stripped = self.vhost.replace("X-Content-Type-Options", "X-Removed-Header")
        self.assertIn(validate_vhost.MISSING_HEADER % "X-Content-Type-Options",
                      validate_vhost.validate(self.zone, stripped))


if __name__ == "__main__":
    unittest.main()
