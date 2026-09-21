# Report — task-001

## Scope done
`greet.sh` added in the isolated worktree by the backend agent (Peluncur 2, codex).
Independently re-verified by a human-run check afterwards.

## Files changed
- `worktrees/task-001/greet.sh` (new, mode 100755) — untracked, not committed

## Commands run + results
- `ah run --exec backend task-001` — agent completed, produced the required Report block
- `./greet.sh Imam` -> `Hello, Imam!`
- `./greet.sh` -> exit 1, stderr `Usage: ./greet.sh NAME`
- `ls projects/sandbox/` -> `AGENTS.md README.md` only

## Tests
- AC1 exact greeting -> PASS
- AC2 no-arg exits non-zero with stderr usage -> PASS
- AC3 file is executable (-rwxr-xr-x) -> PASS
- Isolation: sandbox working tree unchanged, edit confined to the worktree -> PASS

## Risks
None. Throwaway script in a sandbox repository.

## Not done / blocked
The change is left uncommitted on branch `agent/task-001`, awaiting your decision —
the harness never commits or merges on its own.

## Suggested next task
Onboard the first real project under `~/AI-Workspace/projects/<class>/`.
