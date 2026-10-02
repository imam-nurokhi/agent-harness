#!/usr/bin/env bash
# ah feedback [app] [--since DAYS] — summarize what the widget feedback
# collector has recorded (question counts, CLARIFICATION_NEEDED = KB gaps,
# findings, latest sign-off). Reads NDJSON off disk via
# bin/lib/feedback_report.py; does not require ah-feedback to be running.
# See docs/ai-assistant-widget-rollout-plan.md Fase 1.

cmd_feedback() {
  python3 "${LIB_DIR}/feedback_report.py" "$@"
}
