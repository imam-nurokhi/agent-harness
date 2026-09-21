# Report — task-009

## Scope done
A `pre-push` hook now rejects pushes to `main`, `master`, `production` and `prod` in every
workable project, while leaving `dev`, `staging` and feature branches alone. Built by a
sub-agent, then verified independently.

## Files changed
- `bin/lib/protect.sh` (new) — `ah protect install | status | uninstall`
- `bin/ah` — sourced protect.sh, added the case branch and a Guardrails help block
- `pre-push` hooks installed in NEXONE, SUPPORT and sandbox (under `.git/hooks`, untracked)

The hook is written to the repository's **common** git dir, so one install covers every
worktree cut from that repo — an agent cannot dodge it by working in a worktree.

## Commands run + results
Independent re-verification, invoking the hook with git's stdin format:

    main BLOCKED(1)   master BLOCKED(1)   production BLOCKED(1)   prod BLOCKED(1)
    dev allowed(0)    staging allowed(0)  feature/x allowed(0)

Real `git push` against a throwaway local bare remote (no network):

    push dev            -> exit 0
    push dev:main       -> exit 1
    push dev:staging    -> exit 0
    push dev:production -> exit 1
    refs on remote afterwards: refs/heads/dev, refs/heads/staging   # no main, no production

`ah protect status` reports `installed` for all three projects.
`bash -n` passes on `bin/ah`, `bin/lib/protect.sh`, and both installed hooks.

## Tests
- Four protected branches blocked, three allowed branches permitted -> PASS
- Real push: protected refs never reached the remote -> PASS
- Existing foreign hook not clobbered: install warns and leaves it byte-identical,
  uninstall refuses to delete it -> PASS
- Mixed batch (dev + main in one push) -> blocked -> PASS
- Empty stdin -> exit 0 -> PASS

## Risks
**This is a local guardrail, not an enforcement boundary.** A `pre-push` hook can be
bypassed with `git push --no-verify`, or by deleting the file. For a rule that must hold
regardless of what runs locally, pair it with server-side branch protection on GitHub.
Worth noting: a Claude Code hook in this environment independently refuses `--no-verify`
on git push, so an agent running through Claude Code hits two layers — but an agent on
another engine only hits this one.

## Not done / blocked
Server-side branch protection on the GitHub remotes is not configured; that needs the
owner's GitHub permissions.

## Process note
My `git add -A` in commit `c92a3ad` swept up this sub-agent's in-progress files
(`bin/ah`, `bin/lib/protect.sh`) and bundled them with unrelated trigger work. The
sub-agent flagged it as a mystery auto-committer; it was not — it was me committing while
it was still writing. History left as-is rather than rewritten. Lesson: stage explicit
paths, not `-A`, while a sub-agent is working in the same tree.

## Suggested next task
Enable branch protection on the GitHub remotes for NEXONE and SUPPORT so the rule holds
server-side, then decide the SUPPORT `EPERM` sandbox question from task-008.
