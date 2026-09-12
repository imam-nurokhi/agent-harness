# Shared Agent Rules

## Purpose

This file defines baseline rules for every project managed through the agent harness.

## Operating mode

- Treat the user as the final decision-maker.
- Ask before destructive actions, migrations, deployment, push, merge, or credential changes.
- Never access production unless explicitly authorized.
- Never expose or commit secrets.
- Do not assume business rules; mark assumptions clearly.
- Prefer small, reviewable changes over broad refactors.

## Filesystem boundaries

- The only workspace root is `~/AI-Workspace`. Work happens in `projects/` or in a
  worktree under `worktrees/`.
- `~/Documents` is **off-limits** — never read, scan, index, or modify anything under it,
  including `~/Documents/GitHub` and `~/Documents/Projects`. Ask first if a task seems
  to require it.
- Never add the home directory as a project root.

## Required workflow

1. Inspect the project and identify its stack.
2. Read the project-specific `AGENTS.md`, README, and relevant documentation.
3. Restate the task and acceptance criteria.
4. Work in an isolated branch or worktree.
5. Implement the smallest safe change.
6. Run relevant tests, lint, type checks, and build.
7. Review the diff for accidental changes and secrets.
8. Report files changed, commands run, results, risks, and follow-up items.

## Definition of done

- Acceptance criteria are satisfied.
- Relevant automated checks pass.
- No credential or sensitive data is exposed.
- No unrelated files are changed.
- Documentation is updated when behavior or setup changes.
- Final report is complete.

## Project classification

Before working, classify the project as one of:

- `cbqa`
- `nexora`
- `freelance`
- `personal`
- `sandbox`

Use stricter approval for `cbqa` and `nexora` repositories.

