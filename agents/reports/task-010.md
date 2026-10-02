# Report — task-010

## Scope done
Triggers that need to touch a project now fan out: one agent per workable project, each
started with its cwd set to the project's **real** path rather than the workspace. This
fixes the `EPERM` that stopped SUPPORT's test suite from running.

Implemented by Benteng (devops) through the harness; verified by me afterwards, because
the agent could not verify its own work (below).

## Files changed
- `bin/lib/trigger.sh` — per-project fan-out, per-project logs, aggregated summary
- `agents/triggers.json` — `per_project: true` on `health` and `drift`
- `bin/lib/state.py` — supporting lookups
- `tests/test_triggers.py` (new) — trigger unit tests
- `README.md` — documents the behaviour

## Root cause
Not a SUPPORT bug. The codex sandbox fixes its writable root at process start. A trigger
running from `~/AI-Workspace` reached SUPPORT through the symlink, so Vitest's attempt to
create `node_modules/.vite-temp` under `/Users/user/projects/internal/SUPPORT` landed
outside that root and was denied. Counter-evidence that pinned it down: task-007 ran with
cwd set to the real SUPPORT path and `npm test` passed there. `cd` inside a prompt cannot
help, because the root is locked before the agent starts.

## Commands run + results
- `bash -n bin/lib/trigger.sh` -> pass
- `python3 -m unittest discover -s tests` -> `Ran 16 tests ... OK`
- `./bin/ah trigger run health` -> fanned out to 3 projects, each with its own log
- `./bin/ah trigger run standup` -> single run, 0 per-project logs (unchanged)

## Tests — the acceptance criteria, each proven
1. **Fan-out with real cwd** — SUPPORT's log reports `workdir: /Users/user/projects/internal/SUPPORT`.
2. **`npm test` runs without EPERM** — `EPERM occurrences: 0`; `Test Files 16 passed (16)`,
   `Tests 176 passed (176)`, exit 0. NEXONE's Go suite also passed (`ok .../internal/server`).
3. **Held repos untouched** — logs mentioning cbqa/AUDIT-QV/NEXFINANCE: **0**. Only
   NEXONE, SUPPORT and sandbox logs were produced.
4. **Non-per-project triggers unchanged** — standup produced one log and zero per-project
   logs.

## Risks
Fan-out multiplies cost: `health` now starts one agent per project instead of one total.
Fine at three projects; worth revisiting if many more are cleared for work.

## Not done / blocked
Nothing outstanding. Note that the implementing agent reported
`failed to initialize in-process app-server client: Operation not permitted` — a codex
agent cannot spawn a nested codex, so it could not run the triggers to verify itself and
correctly declined to claim success. I ran the verification instead. Worth remembering:
tasks whose acceptance requires dispatching agents cannot be self-verified by an agent.

## Findings surfaced by the now-working health run (follow-up, not fixed here)
- SUPPORT: 1 critical + 9 high npm advisories (`next`, `nodemailer` among them)
- NEXONE: 8 high npm advisories; 7 of 36 Go modules match OSV advisories; `main` is 44
  commits behind `dev`; no root `AGENTS.md`; README contains credential-like defaults

## Suggested next task
Triage SUPPORT's critical `next` advisory, then plan the dependency upgrades against
`dev` with tests and a rollback path.
