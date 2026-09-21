# Task: Smoke test the harness end to end

- **ID:** task-001
- **Project:** sandbox (`~/AI-Workspace/projects/sandbox`)
- **Class:** sandbox
- **Role:** backend
- **Worktree:** `~/AI-Workspace/worktrees/task-001`
- **Base branch:** develop

## Background
First run of the harness. We need proof that role contract, worktree isolation and the report block all work before real repositories are onboarded.

## Objective
Add `greet.sh` to the sandbox that prints a greeting for a name argument.

## Scope
- Create `greet.sh` at the sandbox root
- Make it executable

## Out of scope
- Any change to README.md
- Any git commit, push, or branch operation

## Acceptance criteria
- [x] `./greet.sh Imam` prints exactly `Hello, Imam!`
- [x] `./greet.sh` with no argument exits non-zero with a usage message on stderr
- [x] The file is executable

## Constraints
POSIX sh. No dependencies. Under 20 lines.

## Required checks
- [ ] Unit test
- [ ] Integration/API test
- [x] Lint
- [x] Build
- [x] Diff reviewed for secrets and stray files

## Report
- Scope done:
- Files changed:
- Commands run + results:
- Tests:
- Risks:
- Not done / blocked:
- Suggested next task:
