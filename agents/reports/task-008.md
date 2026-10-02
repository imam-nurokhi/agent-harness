# Report — task-008

## Scope done
`health` and `drift` triggers now see only projects that are not ON HOLD, and the list is
computed from live state at run time rather than written into the prompt.

## Files changed
- `bin/lib/state.py` — `is_held()`, `workable_projects()`, `held` field per project row
- `bin/lib/scope.py` (new) — prints the workable project list
- `bin/lib/trigger.sh` — expands `{PROJECTS}` from live state before dispatch
- `agents/triggers.json` — `health` and `drift` prompts rewritten

## Commands run + results
- `python3 bin/lib/scope.py` -> 3 workable projects; held repos leaked: **0**
- Expanded both prompts and inspected them -> only NEXONE, SUPPORT, sandbox listed
- `ah trigger run health` -> completed, report at `agents/reports/trigger-health.20260913-0917.log`
- `ah trigger run drift` -> completed, report at `agents/reports/trigger-drift.20260913-0917.log`
- Every emitted path checked against disk -> all exist

## Bug found by the triggers themselves
Both agents independently reported `projects/sandbox/sandbox` as missing. They were right:
`scope.py` composed the path from class + name, but a repository sitting directly at
`projects/<name>` has class == name, so it emitted a doubled path. Fixed by using the
row's real `path`, and verified every emitted path now exists.

## Tests
- Held-repo leakage into prompts -> 0 (PASS)
- Every emitted path exists on disk -> PASS
- Both triggers execute end to end and produce reports -> PASS

## Findings the triggers surfaced (for follow-up, not fixed here)
- SUPPORT `npm audit`: 1 critical (`next`), 9 high (incl. `nodemailer`), 18 moderate
- SUPPORT `npm test` fails under the agent sandbox with `EPERM` — Vitest writes
  `.vite-temp` into the real repo path, which sits outside the agent's writable root
- NEXONE has no root `AGENTS.md`; its README is stale since 2026-05-14 and contains
  credential-like development defaults

## Risks
The `EPERM` above means agents cannot currently run SUPPORT's test suite through the
symlink. Harmless for read-only reporting; it will block any implementation task on
SUPPORT until the writable root covers the real path.

## Not done / blocked
Nothing in scope. The three findings above are follow-up work, deliberately not actioned
in a read-only task.

## Suggested next task
Decide how agents should run SUPPORT's tests given the sandbox boundary, then triage the
critical `next` advisory.
