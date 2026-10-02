# Task: Complete SUPPORT integration on dev

- **ID:** task-012
- **Project:** SUPPORT (`projects/nexora/SUPPORT`)
- **Class:** nexora
- **Role:** backend
- **Base branch:** dev
- **Worktree:** worktrees/task-012

## Objective
Audit and complete safe two-way synchronization for linked tickets: outbound updates/status, inbound status and fields, correlation/retries/loop protection. Assess native NEXONE task import against documented business scope; do not import arbitrary tasks blindly. Coordinate NEXONE task-011.
User requests auditing pending tasks and completing NEXONE <-> Slack <-> SUPPORT integration on dev.

## Acceptance criteria
- [x] Current dev code and pending design/task gaps audited with evidence
- [x] Concrete integration defects fixed with regression tests
- [x] Relevant tests, lint, build and security review pass
- [x] Remaining external configuration prerequisites documented honestly
- [x] Parent verifies, commits, pull-before-push to dev

## Constraints
Read project instructions and relevant README/docs. Never read secrets/.env or touch production. No live Slack messages. Work only assigned worktree, preserve others changes. Do not commit/push; parent handles authorized dev push after review. Use existing docs location. Report actual commands and failures.
