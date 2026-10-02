# Report — task-004

## Scope done
Telegram is now a full task-management surface, not just a viewer, and its
notification policy was rewritten so it informs without spamming.

Added: `/new` `/assign` `/ac` `/tick` `/wt` `/note` `/close` for task mutation,
`/kanban` for the board, `/digest` for an on-demand summary, `/quiet on|off` to mute.
23 commands are registered with Telegram so they autocomplete on the phone.

## Files changed
- `bin/lib/tgtask.py` (new) — task mutation handlers
- `bin/lib/tgwatch.py` (new) — event detection, batching, digest, quiet mode
- `bin/lib/tgcmd.py` — kanban board, help text
- `bin/lib/tgcore.py` — full command menu
- `bin/lib/tgbot.py` — handler routing, batched notifier

## Commands run + results
Live verification against the real modules, not mocks:
- `/new` -> created `task-006`, present in `ah task list` -> True
- `/assign task-006 devops` -> `✅ ditetapkan ke ♜ Benteng (devops)`
- `/wt task-006 projects/sandbox` -> worktree present on disk -> True
- `/ac` + `/tick task-006 1` -> `1/1`, persisted to the task file
- `/quiet on` then `off` -> both acknowledged
- Two consecutive polls with no change -> `0` and `0` events
- `python3 -m unittest discover -s tests` -> `Ran 14 tests ... OK`

## Tests
- AC1 create from Telegram, appears in listing -> PASS
- AC2 assign role and create worktree -> PASS
- AC3 tick a criterion, persisted to file -> PASS
- AC4 notify only on important events; routine polls silent -> PASS
- AC5 `/quiet` toggles, `/digest` available -> PASS
- AC6 unpaired chat cannot run any command -> PASS (`denied: chat_id=77 (stranger)`)

## Risks
The bot is a remote-control surface for an agent runner. Authorisation rests on the
paired-chat allowlist and on the bot token staying secret. The token was pasted into a
chat transcript and should be rotated via @BotFather.

## Not done / blocked
Nothing. All six acceptance criteria verified.

## Suggested next task
Onboard a real repository under `projects/<class>/` — the harness is now fully
operable from the phone but has still only ever been exercised on `sandbox`.
