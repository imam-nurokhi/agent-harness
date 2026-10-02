# Task: Create and email the local agent-harness guide

- **ID:** task-003
- **Project:** AI-Workspace harness (`~/AI-Workspace`)
- **Class:** personal
- **Role:** docs
- **Worktree:** none (reporting artifact only; no project-code change)
- **Base branch:** n/a

## Background
The human requested a complete local reference guide for the configured agent harness and delivery to their email address. The guide must reflect live harness state, rather than hand-typed task counts or statuses.

## Objective
Create a polished Indonesian PDF guide documenting the configured local agent harness, verify its rendered layout, and email the PDF to mimamnuro@gmail.com via the configured Mail.app account.

## Scope
- Inspect live harness state with the read-only state collector and documented local configuration.
- Explain architecture, roles, isolation/worktrees, task lifecycle, CLI usage, Command Center, guardrails, triggers, project onboarding, verification, and current task state.
- Include an explicit verified-working versus pending/attention-needed section derived from live state.
- Create the final PDF under `output/pdf/` with a stable descriptive name.
- Render and visually inspect every final PDF page before sending.
- Send exactly one email, to `mimamnuro@gmail.com` only, with the final PDF attached; verify it appears in Mail.app Sent.
- Write the required task report with command output excerpts and delivery verification.

## Out of scope
- Scanning, reading, or modifying `~/Documents`.
- Editing project code, changing harness configuration, creating worktrees, migrations, deployment, git push, merge, or credential changes.
- Accessing the recipient inbox or any production system.

## Acceptance criteria
- [x] A complete, readable Bahasa Indonesia PDF guide is created from local, live harness information.
- [x] Every task currently present in the live harness is listed with its actual status, without hand-typed counts.
- [x] The PDF identifies verified functionality and clearly names pending or attention-needed items.
- [x] Rendered pages have been inspected and show no clipped, overlapping, or unreadable content.
- [x] One email with the PDF attachment is sent only to mimamnuro@gmail.com and is visible in Mail.app Sent.
- [x] The final report records commands and their results, document QA, and delivery verification.

## Constraints
ASSUMPTION: the PDF language is Bahasa Indonesia. Derive task state at generation time from `bin/lib/state.py`; do not expose credentials, tokens, absolute paths outside the workspace, or sensitive data. Follow the PDF skill's creation and visual-QA workflow, including the artifact-operation marker immediately before the first PDF-authoring command.

## Required checks
- [ ] Unit test (not applicable: documentation artifact; state-derived content check required)
- [ ] Integration/API test (not applicable: no API; Mail.app Sent verification required)
- [ ] Lint (not applicable: no code change)
- [ ] Build (not applicable: PDF render and structural validation required)
- [x] Diff reviewed for secrets and stray files

## Report
- Scope done:
- Files changed:
- Commands run + results:
- Tests:
- Risks:
- Not done / blocked:
- Suggested next task:
