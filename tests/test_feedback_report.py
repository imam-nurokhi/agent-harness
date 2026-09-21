"""ah feedback must surface the KB gap list (CLARIFICATION_NEEDED), not just a
question count — that's the whole point of Fase 1's "daftar lubang KB" per
docs/ai-assistant-widget-rollout-plan.md.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin" / "lib"))
import feedback_report  # noqa: E402


def rec(app="accreditation", type_="question.asked", email="imam@nexoratech.co",
        remote_user="user.demo", classification=None, at="2026-09-18T05:00:00Z", **payload_extra):
    payload = dict(payload_extra)
    if classification:
        payload["classification"] = classification
    return {
        "app": app,
        "type": type_,
        "payload": {**payload, "reviewer": {"name": "Imam", "email": email}},
        "remote_user": remote_user,
        "received_at": at,
    }


class ReviewerKeyTests(unittest.TestCase):
    def test_prefers_reviewer_email(self):
        self.assertEqual(feedback_report.reviewer_key(rec()), "imam@nexoratech.co")

    def test_falls_back_to_basic_auth_user_without_identity(self):
        r = rec()
        r["payload"]["reviewer"] = None
        self.assertEqual(feedback_report.reviewer_key(r), "basic-auth:user.demo")

    def test_unknown_when_nothing_is_present(self):
        self.assertEqual(feedback_report.reviewer_key({"payload": {}}), "unknown")


class SummarizeTests(unittest.TestCase):
    def test_counts_questions_per_reviewer(self):
        records = [rec(), rec(), rec(email="lain@nexoratech.co")]
        summary = feedback_report.summarize(records)
        self.assertEqual(summary["accreditation"]["reviewers"]["imam@nexoratech.co"]["questions"], 2)
        self.assertEqual(summary["accreditation"]["reviewers"]["lain@nexoratech.co"]["questions"], 1)

    def test_clarification_needed_is_the_kb_gap_list(self):
        records = [
            rec(type_="answer.given", classification="ANSWERED_FROM_SOURCE"),
            rec(type_="answer.given", classification="CLARIFICATION_NEEDED", at="2026-09-18T05:01:00Z"),
        ]
        summary = feedback_report.summarize(records)
        gaps = summary["accreditation"]["reviewers"]["imam@nexoratech.co"]["clarification_needed"]
        self.assertEqual(gaps, ["2026-09-18T05:01:00Z"])

    def test_findings_recorded_are_counted(self):
        records = [rec(type_="finding.recorded"), rec(type_="finding.recorded")]
        summary = feedback_report.summarize(records)
        self.assertEqual(summary["accreditation"]["reviewers"]["imam@nexoratech.co"]["findings_recorded"], 2)

    def test_latest_signoff_is_tracked_per_app(self):
        records = [rec(type_="baseline.signoff", status="APPROVED")]
        records[0]["payload"]["status"] = "APPROVED"
        summary = feedback_report.summarize(records)
        self.assertEqual(summary["accreditation"]["latest_signoff"]["status"], "APPROVED")

    def test_apps_do_not_bleed_into_each_other(self):
        records = [rec(app="accreditation"), rec(app="academy")]
        summary = feedback_report.summarize(records)
        self.assertEqual(set(summary.keys()), {"accreditation", "academy"})

    def test_last_seen_is_the_most_recent_timestamp(self):
        records = [rec(at="2026-09-18T05:00:00Z"), rec(at="2026-09-18T06:00:00Z")]
        summary = feedback_report.summarize(records)
        self.assertEqual(
            summary["accreditation"]["reviewers"]["imam@nexoratech.co"]["last_seen"],
            "2026-09-18T06:00:00Z")


class RenderTests(unittest.TestCase):
    def test_empty_summary_says_so_plainly(self):
        self.assertEqual(feedback_report.render({}), "no feedback recorded yet")

    def test_render_surfaces_the_gap_count_by_name(self):
        summary = feedback_report.summarize([
            rec(type_="answer.given", classification="CLARIFICATION_NEEDED"),
        ])
        text = feedback_report.render(summary)
        self.assertIn("1 CLARIFICATION_NEEDED (KB gap)", text)


class LoadNdjsonTests(unittest.TestCase):
    def test_corrupt_line_is_skipped_not_fatal(self, ):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "day.ndjson"
            path.write_text('{"app":"accreditation","type":"question.asked"}\nnot json\n')
            records = feedback_report.load_ndjson(path)
            self.assertEqual(len(records), 1)


class CollectRecordsTests(unittest.TestCase):
    def test_since_days_filters_by_filename_date(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            app_dir = base / "accreditation"
            app_dir.mkdir()
            (app_dir / "2020-01-01.ndjson").write_text('{"app":"accreditation","type":"question.asked"}\n')
            (app_dir / "2099-01-01.ndjson").write_text('{"app":"accreditation","type":"question.asked"}\n')
            recent = feedback_report.collect_records(base, "accreditation", since_days=1)
            self.assertEqual(len(recent), 1)

    def test_missing_data_dir_returns_no_records(self):
        records = feedback_report.collect_records(Path("/nonexistent/path/xyz"), None, None)
        self.assertEqual(records, [])


if __name__ == "__main__":
    unittest.main()
