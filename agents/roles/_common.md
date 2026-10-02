# Common Role Preamble

Applies to every role. Read this before the role-specific file.

## Non-negotiables
- Read `~/AI-Workspace/AGENTS.md` and the project's own `AGENTS.md` before acting.
- Work only inside the assigned worktree path. Never touch another agent's worktree.
- Never read, print, or commit `.env`, `*.pem`, `*.key`, tokens, or passwords.
- Never run migrations, deploys, `git push`, or merges without explicit human approval.
- Pull before push, always: `git pull --rebase` first, re-run tests, then push.
- Never push to `main`/`master`/`production`/`prod`; use `dev` or `staging`.
- Production is off-limits unless the task states otherwise in writing.
- Mark every assumption with `ASSUMPTION:` so it is greppable.

## Required output block
End every task with exactly this structure:

```
## Report
- Scope done:
- Files changed:
- Commands run + results:
- Tests: (name -> pass/fail, with output excerpt)
- Risks:
- Not done / blocked:
- Suggested next task:
```

A report claiming success without command output is treated as a failed task.
