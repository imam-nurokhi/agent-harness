# Report — task-005

## Scope done
Stdlib regression suite covering task-004's behaviour, plus the two input-handling
defects the suite exposed. Work was done in worktree `agent/task-005` and merged to
`main` with `--no-ff`.

## Files changed
- `tests/test_telegram_task_management.py` (new, 14 cases, 228 lines)
- `bin/lib/tgtask.py` — task-id validation
- `bin/lib/task.sh` — title handling in `task_new`

## Defects found by the tests
1. **Shell-injection / corruption in `ah task new`.** The title was interpolated into a
   `sed` expression, so `|`, `&`, or a backslash broke it. Reproduced:
   `sed: 1: "s|<TITLE>|Fix a|b & <TI ...": bad flag in substitute command`.
   Replaced with bash parameter substitution, which treats the title as data. A title
   containing `|`, `&`, `<TITLE>` and `\n` now round-trips intact; newlines are rejected.
2. **Unvalidated task id used as a path component.** `_require` now demands the canonical
   `task-NNN` form, and `/wt` confirms the task exists before shelling out.

## Commands run + results
- `python3 -m unittest discover -s tests -v` -> `Ran 14 tests in 0.309s ... OK`
- Re-run after merging to main -> `Ran 14 tests ... OK`
- `python3 -m py_compile bin/lib/*.py tests/*.py` -> PASS
- `python3 -m tabnanny` -> PASS
- `bash -n` over `bin/ah` and every `bin/lib/*.sh` -> PASS
- Secret scan over the merge range -> 0 hits
- `git status --short` -> 0 untracked, 0 stray files

## Tests
- Unpaired chat cannot reach any mutation handler -> PASS
- `/new` `/assign` `/wt` `/tick` mutate only for allowed chats -> PASS
- Malicious and non-canonical task ids rejected; cannot escape the tasks directory -> PASS
- Notifications only for completion events; repeated polls do not re-notify -> PASS
- `/quiet` respected, `/digest` available -> PASS
- Transport mocked; long messages split rather than truncated -> PASS
- Shell-sensitive and unicode titles preserved; newline titles rejected -> PASS

## Risks
The suite mocks the Telegram transport, so it proves handler and policy behaviour but not
live API delivery. Live delivery was exercised separately against the real bot.

## Not done / blocked
Nothing. All four acceptance criteria met.

## Suggested next task
Wire `python3 -m unittest discover -s tests` into a pre-merge check so these
regressions cannot come back silently.
