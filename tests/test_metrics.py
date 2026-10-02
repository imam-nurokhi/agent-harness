"""Monitoring must never report "healthy" for something it could not measure.

The harness now reads the Prometheus behind monitoring.nexoratech.co — 17
uptime probes, 11 certificates, 12 hosts — and pushes a summary to Telegram.
That makes it a safety-critical little module in one specific way: a bug here
does not produce a wrong number on a screen, it produces *silence* where a
warning belonged.

So the tests are about the failure directions, not the happy path:
  - an unreachable Prometheus must read as unknown, never as healthy;
  - a probe that is down, a certificate about to expire, a full disk must each
    change the verdict;
  - thresholds must be quiet in normal conditions, because an alert that fires
    every day stops being read (this workspace has paid for that twice).
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin" / "lib"))

import metrics  # noqa: E402


def rows(pairs, label="instance"):
    return [({label: name}, value) for name, value in pairs]


class ProbeTests(unittest.TestCase):
    def test_all_up(self):
        s = metrics.probe_summary(rows([("a", 1.0), ("b", 1.0)]))
        self.assertEqual((s["up"], s["total"], s["down"]), (2, 2, []))

    def test_a_down_probe_is_named(self):
        s = metrics.probe_summary(rows([("a", 1.0), ("b", 0.0)]))
        self.assertEqual(s["down"], ["b"])
        self.assertEqual(s["up"], 1)

    def test_no_probes_is_not_reported_as_all_up(self):
        s = metrics.probe_summary([])
        self.assertEqual(s["total"], 0)


class SslTests(unittest.TestCase):
    def test_soonest_expiry_comes_first(self):
        s = metrics.ssl_summary(rows([("a", 70.9), ("b", 12.2), ("c", 51.0)]))
        self.assertEqual(s["soonest"]["host"], "b")
        self.assertEqual(s["soonest"]["days"], 12)

    def test_only_certificates_inside_the_window_are_flagged(self):
        s = metrics.ssl_summary(rows([("a", 70.0), ("b", 12.0)]), warn_days=21)
        self.assertEqual([i["host"] for i in s["expiring"]], ["b"])

    def test_an_expired_certificate_is_flagged_not_hidden(self):
        s = metrics.ssl_summary(rows([("a", -3.0)]))
        self.assertEqual(s["expiring"][0]["days"], -3)


class UtilisationTests(unittest.TestCase):
    def test_prose_instance_labels_are_shortened(self):
        s = metrics.worst(rows([("Server Production audit-qv1.cbqaglobal.co.id (148.230.96.117)", 77.06)]), 85)
        self.assertEqual(s["top"]["host"], "audit-qv1.cbqaglobal.co.id")
        self.assertEqual(s["top"]["pct"], 77.1)

    def test_a_development_label_is_shortened_too(self):
        # The first render of real data showed "Server Development OneAlpha"
        # untouched, because only "Server Production" was being stripped.
        s = metrics.worst(rows([("Server Development OneAlpha", 64.4)]), 85)
        self.assertEqual(s["top"]["host"], "OneAlpha")

    def test_a_plain_hostname_is_left_alone(self):
        s = metrics.worst(rows([("db-01.internal", 10.0)]), 85)
        self.assertEqual(s["top"]["host"], "db-01.internal")

    def test_highest_first(self):
        s = metrics.worst(rows([("a", 20.0), ("b", 88.0)]), 85)
        self.assertEqual(s["top"]["host"], "b")

    def test_threshold_is_inclusive_and_quiet_below_it(self):
        self.assertEqual(metrics.worst(rows([("a", 84.9)]), 85)["over"], [])
        self.assertEqual(len(metrics.worst(rows([("a", 85.0)]), 85)["over"]), 1)


class VerdictTests(unittest.TestCase):
    def setUp(self):
        self.ok = {"down": []}
        self.clean = {"expiring": [], "over": []}

    def test_everything_normal_is_healthy(self):
        v = metrics.verdict(self.ok, {"expiring": []}, {"over": []}, {"over": []}, self.ok)
        self.assertEqual(v, "sehat")

    def test_a_down_probe_outranks_everything(self):
        v = metrics.verdict({"down": ["x"]}, {"expiring": ["y"]}, {"over": []},
                            {"over": []}, self.ok)
        self.assertEqual(v, "turun")

    def test_a_down_scrape_target_also_counts_as_down(self):
        v = metrics.verdict(self.ok, {"expiring": []}, {"over": []}, {"over": []},
                            {"down": ["node/x"]})
        self.assertEqual(v, "turun")

    def test_expiring_certificate_raises_attention(self):
        v = metrics.verdict(self.ok, {"expiring": [{"host": "a", "days": 5}]},
                            {"over": []}, {"over": []}, self.ok)
        self.assertEqual(v, "perhatian")

    def test_full_disk_raises_attention(self):
        v = metrics.verdict(self.ok, {"expiring": []}, {"over": [{"host": "a", "pct": 91}]},
                            {"over": []}, self.ok)
        self.assertEqual(v, "perhatian")


class RenderTests(unittest.TestCase):
    def summary(self, **over):
        base = {
            "probes": {"total": 17, "up": 17, "down": []},
            "ssl": {"items": [], "soonest": {"host": "a.co", "days": 51}, "expiring": []},
            "disk": {"items": [], "top": {"host": "h1", "pct": 77.1}, "over": []},
            "mem": {"items": [], "top": {"host": "h2", "pct": 40.0}, "over": []},
            "targets": {"total": 32, "up": 32, "down": []},
            "grafana": {"configured": False},
            "verdict": "sehat",
        }
        base.update(over)
        return base

    def test_a_healthy_report_states_the_counts(self):
        out = metrics.render(self.summary())
        self.assertIn("17/17 up", out)
        self.assertIn("32/32 up", out)
        self.assertIn("51 hari", out)

    def test_an_unreachable_prometheus_is_not_reported_as_healthy(self):
        out = metrics.render({"error": "connection refused"})
        self.assertIn("tidak terbaca", out.lower())
        self.assertIn("tidak diketahui", out.lower())
        self.assertNotIn("🟢", out)

    def test_missing_grafana_token_is_stated_not_hidden(self):
        self.assertIn("GRAFANA_TOKEN", metrics.render(self.summary()))

    def test_a_configured_grafana_shows_counts_instead(self):
        out = metrics.render(self.summary(
            grafana={"configured": True, "dashboards": 3, "alerting": 1}))
        self.assertIn("3 dashboard", out)
        self.assertIn("1 alert", out)
        self.assertNotIn("GRAFANA_TOKEN", out)

    def test_down_hosts_are_listed_for_the_reader(self):
        out = metrics.render(self.summary(
            probes={"total": 17, "up": 16, "down": ["https://x.co"]}, verdict="turun"))
        self.assertIn("https://x.co", out)
        self.assertIn("🔴", out)

    def test_the_message_fits_a_phone(self):
        many = [f"https://host-{i}.co" for i in range(40)]
        out = metrics.render(self.summary(
            probes={"total": 40, "up": 0, "down": many}, verdict="turun"))
        self.assertLess(len(out), 3800, "Telegram caps a message at 4096")


class GrafanaTests(unittest.TestCase):
    def test_no_token_means_not_configured_not_broken(self):
        saved = metrics.os.environ.pop("GRAFANA_TOKEN", None)
        self.addCleanup(lambda: metrics.os.environ.__setitem__("GRAFANA_TOKEN", saved)
                        if saved else None)
        self.assertEqual(metrics.grafana_overview(""), {"configured": False})


if __name__ == "__main__":
    unittest.main()
