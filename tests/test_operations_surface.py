"""Operations status must degrade safely when optional local services are absent."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin" / "lib"))

import operations  # noqa: E402
import tgwatch  # noqa: E402


class OperationsSurfaceTests(unittest.TestCase):
    def test_snapshot_marks_a_reachable_automation_service_healthy(self):
        with patch.object(operations, "_http_status", return_value=200), \
             patch.object(operations, "_service_active", return_value=True):
            result = operations.snapshot()

        automation = next(item for item in result["services"] if item["id"] == "automation")
        backup = next(item for item in result["services"] if item["id"] == "backup")
        self.assertEqual(automation["status"], "ok")
        self.assertEqual(backup["status"], "ok")

    def test_snapshot_never_reports_unreachable_service_as_healthy(self):
        with patch.object(operations, "_http_status", return_value=None), \
             patch.object(operations, "_service_active", return_value=False):
            result = operations.snapshot()

        automation = next(item for item in result["services"] if item["id"] == "automation")
        self.assertEqual(automation["status"], "unavailable")
        self.assertTrue(any(link["status"] == "not-configured" for link in result["links"]))

    def test_disk_capacity_uses_explicit_warning_thresholds(self):
        self.assertEqual("ok", operations._disk_status(84))
        self.assertEqual("warn", operations._disk_status(85))
        self.assertEqual("critical", operations._disk_status(95))

    def test_telegram_digest_surfaces_operations_without_secrets(self):
        snapshot = {
            "summary": {"tasks_total": 0}, "tasks": [], "worktrees": [],
            "health": {"disk_free_gb": 8},
            "operations": {"services": [{"label": "n8n automation", "status": "ok"}]},
        }
        with patch.object(tgwatch.state, "snapshot", return_value=snapshot), \
             patch.object(tgwatch.jobs, "listing", return_value=[]):
            message = tgwatch.digest()
        self.assertIn("n8n automation: ok", message)
        self.assertNotIn("password", message.lower())


if __name__ == "__main__":
    unittest.main()
