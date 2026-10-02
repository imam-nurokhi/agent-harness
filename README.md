# Agent Harness

A virtual engineering office at `~/AI-Workspace`. Seven role-bound agents, each working
in its own git worktree, driven from one CLI and watched from one Command Center.

Everything lives under `/Users/user/`. **`~/Documents` is off-limits** — the guard is
enforced in code (`assert_allowed_path`), not just written down.

---

## The team

| | Persona | Piece | Role (what you type) | Owns |
|---|---|---|---|---|
| ♚ | **Raja** | King | `lead` | Breaks work into tasks, assigns, consolidates. Never implements. |
| ♛ | **Ster** | Queen | `qa` | Test plans, reproduction, regression. May not say "looks fine". |
| ♜ | **Benteng** | Rook | `devops` | Docker, CI, environments. Staging only. |
| ♞ | **Kuda** | Knight | `review` | Security, correctness, architecture drift. |
| ♝ | **Peluncur 1** | Bishop | `frontend` | React, UI, accessibility. |
| ♝ | **Peluncur 2** | Bishop | `backend` | APIs, database, business logic. |
| ♟ | **Pion** | Pawn | `docs` | PRD, API docs, changelog, handover. |

The CLI always takes the **role**, never the persona: `ah run backend task-007`.
Personas are how you read the floor; roles are how you drive it.

---

## Daily loop

```bash
ah doctor                              # is everything wired?
ah engine                              # which engine runs, and what refused to
ah dash                                # Command Center at :7777

ah task new "Fix invoice total rounding"
#   then edit agents/tasks/task-003.md — Role, Project, Objective, Acceptance criteria

ah wt add task-003 projects/nexora/nexone    # isolated branch agent/task-003
ah run backend task-003                      # interactive, you watch
ah run --exec backend task-003               # unattended, transcript to reports/

ah run review task-003                       # second opinion, its own model
git -C worktrees/task-003 diff               # you read the diff
# you commit, you merge — the harness never does
```

`ah recon <project>` first on any repo you have not used before: read-only survey of
stack, commands, risks, and three safe starter tasks.

---

## Why it holds together

**One agent, one worktree, one diff.** `ah wt add` creates a real git worktree on
`agent/<task-id>`. Two agents can run at once without touching each other's files.

**One holder per task.** `ah run` claims the task for as long as it lives, and releases
it when the process ends; `ah task claim <id> "why"` holds one by hand until you release
it. A second agent that tries to take a held task or build its worktree is stopped with
the holder's name, not left to collide silently. `ah task list` shows who holds what.
Task ids are reserved by creating the file, so two agents running `ah task new` at the
same moment cannot be handed the same number.

**Role contracts are prepended to every run.** `agents/roles/_common.md` plus the
role file plus `AGENTS.md` plus the task go in front of the model on every launch. The
common preamble forces a Report block with commands, test output, risks, and blockers —
a success claim with no command output is treated as a failed task.

**Reviewers do not grade their own homework.** This used to be guaranteed by provider:
`review` and `qa` ran on a different vendor from the implementer. Since the harness went
single-vendor that guarantee is gone, and the replacement is weaker — separation by
**model** (`AH_MODEL_REVIEW` vs `AH_MODEL_IMPL`) and by **context** (a reviewer is handed
the diff and the acceptance criteria, never the implementer's session). The context half
is not built yet; it is task-035. Said plainly rather than left implied.

**Approval stays human.** No agent commits, pushes, merges, deploys, or touches
production. Acceptance criteria are ticked by you, not by the agent that wrote the code.

---

## Command Center — `ah dash`

It is not a read-only dashboard. You can dispatch agents from it.

- **terminal** — the Queue: pick a piece, optionally pick a task, type an instruction,
  press send (or Cmd+Enter). The agent is spawned with the *same* contract the CLI
  builds, and its output streams into the pane live. Stop a run mid-flight. Past runs
  are listed on the left and stay readable after they finish.
- **floor** — every desk, who is idle / assigned / working right now. "Working" is
  detected from live `codex`/`claude` processes whose cwd is inside a worktree, so it
  cannot lie. Includes the chess-piece legend.
- **tasks** — kanban derived from real state: *To do* (no worktree) → *Doing* (worktree
  exists) → *Needs review* (all criteria met, nothing reported) → *Done* (report exists).
- **monitor** — engines, auth, disk, worktrees with dirty files and diffstat, projects
  and whether each has an `AGENTS.md`, reports with verdicts. On the VPS it also
  shows the read-only n8n loopback probe, local backup timer, and approved
  operations links; unavailable integrations are labelled as such.
- **triggers** — scheduled work, and whether it is installed in launchd.
- **activity** — every task, report, and worktree change, newest first.

Task cards and triggers have **run** buttons; agent desks have **brief**.

Refreshes every 4s; the terminal streams every 1.2s.

**Security.** The server starts real processes, so it binds to `127.0.0.1` only and every
mutating call must carry a per-session token embedded in the page. Another site open in
your browser cannot drive your agents. The token changes each time you start `ah dash`.

---

## Telegram — control it from your phone

The bot (`@KaraImamiBot`) is a full control surface, not just notifications.

```bash
ah bot install     # run at login, restart on crash (launchd)
ah bot pair        # issue a one-time code, then send /pair <code> to the bot
ah bot status | stop | log
```

From Telegram:

| | |
|---|---|
| `/status` `/agents` `/tasks` `/task task-001` | see the floor |
| `/jobs` `/tail <job-id>` | read any run's output |
| `/run backend task-001` | put an agent to work |
| `/ask lead ringkas status hari ini` | ad-hoc instruction |
| `/trigger standup` `/stop <job-id>` | fire or halt work |
| `/doctor` | engines, auth, disk |

When a run finishes you get a push with its Report block.

**Security.** A Telegram bot that dispatches agents is remote code execution, so only
**paired chat ids** may issue any command — everyone else is refused and logged. Pairing
needs a one-time code generated on this Mac, so finding the bot on Telegram is not enough
to control it. The token lives in `.env` (chmod 600, git-ignored); anyone holding it can
impersonate the bot, so rotate it via @BotFather if it leaks.

## Triggers

Defined in `agents/triggers.json`, scheduled through launchd.

```bash
ah trigger list                  # what exists, what is installed
ah trigger run standup           # run one now
ah trigger memo standup          # what its recent runs reported
ah trigger install standup       # schedule it (daily 09:00)
ah trigger uninstall standup
```

Each run is handed what the previous runs learned. The contract asks every trigger to
end with a single `MEMO:` line; that line is stored in `agents/memory/trigger-runs.json`
(last 5 per trigger) and injected into the next run's prompt, so a scheduled agent
reports what *changed* instead of re-deriving the same state every morning. A run with
no `MEMO:` line falls back to its last line of output.

Failures no longer wait for a human to notice them. The Telegram watcher pushes one
message when a trigger exits nonzero, and one when a trigger is more than two hours past
its scheduled time without running. Both are deduplicated — one alert per failure, one
per missed fire.

Shipped: `standup` (daily task review), `health` (weekly repo health), `drift` (weekly
docs-vs-code), `sweep` (weekly stale worktrees). All read-only reporting — none of them
change code. Keep it that way until you trust the output.

`health` and `drift` set `per_project: true`: the CLI obtains the live allowed list
from `scope.py` / `state.workable_projects()`, then starts one agent per project
from its resolved physical directory. Held projects are filtered before Git
metadata is read. Existing tests may create disposable caches; agents must not
edit project files or install dependencies. Each project has a transcript in
`agents/reports/trigger-<id>-<project>.<timestamp>.log`; the main trigger log combines
these transcripts with cwd and exit status. A failed engine does not prevent
remaining projects from running, and the trigger exits nonzero after failures.
`standup` and `sweep` continue to start one agent in the workspace.

---

## Onboarding a project

Real repositories must live under `~/AI-Workspace/projects/<class>/` — clone or copy
them there. Classes: `cbqa`, `nexora`, `freelance`, `personal`, `sandbox`.

Then work through `agents/checklists/onboard.md`. The step that matters most is writing
the project's own `AGENTS.md`: stack, exact commands, architecture boundaries, business
rules, dangerous commands, definition of done. Agents trust those commands literally, so
run each one yourself before you write it down.

---

## Layout

```
~/AI-Workspace/
├── bin/ah                 the CLI
├── bin/lib/               common, doctor, task, claim, wt, run, trigger, trigmem.py, state.py, dash.*
├── AGENTS.md              rules every agent gets, every run
├── agents/
│   ├── roles/             seven contracts + _common.md
│   ├── prompts/           recon, implement, review, healthcheck
│   ├── task-templates/    task.md
│   ├── checklists/        review · release · onboard
│   ├── tasks/             live tasks
│   ├── reports/           reports and transcripts
│   ├── claims/            who holds which task (runtime, gitignored)
│   ├── memory/            what past trigger runs learned (runtime, gitignored)
│   └── triggers.json      scheduled work
├── projects/<class>/      onboarded repositories
├── worktrees/<task-id>/   one per active task
└── archives/
```

## Work in progress

The harness is being moved off this Mac and onto a VPS, with Claude as the only engine and
a two-way Telegram surface. Engine defaults have already changed: `ah run` and every trigger
now launch `claude`, not `codex` — override with `AH_ENGINE=codex`. Claude is a preference,
not an assumption: `AH_ENGINE_ORDER` (default `claude codex`) sets which engines are tried,
and an engine this account is not authorised to use is skipped until a run with it succeeds
again. `ah engine` shows what was refused; `ah engine clear <name>` undoes it by hand.

Read `docs/harness-upgrade.md` before touching `jobs.py`, `trigger.sh`, `bot.sh`, or anything
under `bin/lib/tg*`. The remaining work is on the board as task-030 through task-037.

## Checklists

`agents/checklists/review.md` before any merge · `release.md` before any deploy ·
`onboard.md` before an agent touches a new repository.
