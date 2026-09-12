# Agent Harness

A virtual engineering office you run on your own machine. Seven role-bound agents,
each working in its own git worktree, driven from one CLI and watched from one
Command Center.

Built on top of whatever coding-agent CLIs you already have installed (Codex, Claude
Code, and friends) — this repo does not replace them, it orchestrates them: task
files, role contracts, isolated worktrees, a live dashboard, and scheduled read-only
checks, all as plain bash/Python you can read end to end.

---

## Why this exists

Running multiple coding agents against real projects gets messy fast: which agent
touched which files, is anything still uncommitted, did the "security review" agent
actually check anything or just say "looks fine". This harness fixes that with a few
rules, enforced in code, not just written down:

- **One agent, one worktree, one diff.** Every task gets its own git worktree on
  branch `agent/<task-id>`. Two agents can run at once without touching each other.
- **Role contracts are prepended to every run.** The common preamble, the role file,
  your project's `AGENTS.md`, and the task all go in front of the model on every
  launch — and it forces a Report block (commands run, test output, risks, blockers).
  A success claim with no command output is a failed task.
- **Reviewers use a different provider than implementers**, so nothing grades its own
  homework.
- **Approval stays human.** No agent commits, pushes, merges, deploys, or touches
  production. You tick the acceptance criteria, not the agent that wrote the code.

---

## Install

Requires macOS with Homebrew, Python 3 (stdlib only, no pip deps), and Node.js (for
the agent CLIs).

```bash
git clone https://github.com/imam-nurokhi/agent-harness.git ~/AI-Workspace
cd ~/AI-Workspace
./bootstrap-mac.sh
```

`bootstrap-mac.sh` installs Node/Homebrew prerequisites if missing, installs the
`codex` and `claude` CLIs, and creates the working directories (`projects/`,
`worktrees/`, `archives/`, `agents/reports/`). Log in to each CLI once
(`codex`, then `claude`) before running your first task.

Add `~/AI-Workspace/bin` to your `PATH` (or symlink `bin/ah` onto it) so the `ah`
command is available anywhere:

```bash
echo 'export PATH="$HOME/AI-Workspace/bin:$PATH"' >> ~/.zshrc
```

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
ah dash                                # Command Center at :7777

ah task new "Fix invoice total rounding"
#   then edit agents/tasks/task-003.md — Role, Project, Objective, Acceptance criteria

ah wt add task-003 projects/nexora/nexone    # isolated branch agent/task-003
ah run backend task-003                      # interactive, you watch
ah run --exec backend task-003               # unattended, transcript to reports/

ah run review task-003                       # second opinion, different provider
git -C worktrees/task-003 diff               # you read the diff
# you commit, you merge — the harness never does
```

`ah recon <project>` first on any repo you have not used before: read-only survey of
stack, commands, risks, and three safe starter tasks.

---

## Command Center — `ah dash`

- **floor** — every desk, who is idle / assigned / working right now. "Working" is
  detected from live `codex`/`claude` processes whose cwd is inside a worktree, so it
  cannot lie. Includes the chess-piece legend.
- **tasks** — kanban derived from real state: *To do* (no worktree) → *Doing* (worktree
  exists) → *Needs review* (all criteria met, nothing reported) → *Done* (report exists).
- **monitor** — engines, auth, disk, worktrees with dirty files and diffstat, projects
  and whether each has an `AGENTS.md`, reports with verdicts.
- **triggers** — scheduled work, and whether it is installed in launchd.
- **activity** — every task, report, and worktree change, newest first.

Refreshes every 4s. Read-only: it shows you the floor, the CLI drives it. Every
mutating call carries a per-session token embedded in the page (`bin/lib/dash.py`),
so another tab in your browser cannot drive your agents.

---

## Triggers

Defined in `agents/triggers.json`, scheduled through `launchd`.

```bash
ah trigger list                  # what exists, what is installed
ah trigger run standup           # run one now
ah trigger install standup       # schedule it (daily 09:00)
ah trigger uninstall standup
```

Shipped: `standup` (daily task review), `health` (weekly repo health), `drift` (weekly
docs-vs-code), `sweep` (weekly stale worktrees). All read-only reporting — none of them
change code. Keep it that way until you trust the output.

---

## Onboarding a project

Real repositories live under `~/AI-Workspace/projects/<class>/` — clone or copy them
there. Classes: `cbqa`, `nexora`, `freelance`, `personal`, `sandbox` (rename these in
`AGENTS.md` and `project-onboarding-checklist.md` to whatever fits your own work).

Then work through `agents/checklists/onboard.md`. The step that matters most is
writing the project's own `AGENTS.md`: stack, exact commands, architecture boundaries,
business rules, dangerous commands, definition of done. Agents trust those commands
literally, so run each one yourself before you write it down.

---

## Filesystem boundaries

- The only workspace root is `~/AI-Workspace`. Work happens in `projects/` or in a
  worktree under `worktrees/`.
- Never expand the workspace root to your entire home directory or another personal
  folder — declare an explicit off-limits path in `AGENTS.md` (the original design
  keeps `~/Documents` off-limits) and enforce it the same way: in code, not just docs.

---

## Layout

```
~/AI-Workspace/
├── bin/ah                 the CLI
├── bin/lib/               common, doctor, task, wt, run, trigger, state.py, dash.*
├── AGENTS.md              rules every agent gets, every run
├── agents/
│   ├── roles/             seven contracts + _common.md
│   ├── prompts/           recon, implement, review, healthcheck
│   ├── task-templates/    task.md
│   ├── checklists/        review · release · onboard
│   ├── tasks/             live tasks (gitignored — your own work, not this repo's)
│   ├── reports/           reports and transcripts (gitignored)
│   └── triggers.json      scheduled work
├── projects/<class>/      onboarded repositories (gitignored)
├── worktrees/<task-id>/   one per active task (gitignored)
└── archives/
```

`agent-harness-multi-project-setup-plan.md` has the original design rationale (in
Indonesian) if you want the full reasoning behind the architecture.

## Checklists

`agents/checklists/review.md` before any merge · `release.md` before any deploy ·
`onboard.md` before an agent touches a new repository.

---

## Design principles

1. **Local-first.** Everything — tasks, reports, config — lives on your machine as
   plain files. Only what an agent actually reads gets sent to whichever provider
   you've configured for that role.
2. **Human-in-the-loop.** Agents ask before destructive actions, migrations, deploys,
   production access, or credential changes. This is written into `AGENTS.md` and the
   common role preamble, and it is the one rule every role file repeats.
3. **Isolated work.** Git worktrees, not shared working directories, so parallel
   agents cannot clobber each other's edits.
4. **No secrets in prompts or diffs.** Every role and checklist explicitly calls out
   `.env`, `*.pem`, `*.key`, tokens, and passwords as things to never read, print,
   commit, or send to a model.

---

## Contributing

Issues and pull requests are welcome — this is a personal tool shared in case it's
useful to your own setup too. Keep changes small and reviewable, matching the spirit
of the harness itself.

## License

[MIT](LICENSE) © Imam Nurokhi
