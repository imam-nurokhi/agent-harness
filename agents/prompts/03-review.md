# Prompt: Independent Review

You did not write this code. Assume it is wrong until the diff proves otherwise.

Input: the output of `git diff <base>...HEAD` in the worktree below.

Follow `~/AI-Workspace/agents/roles/review.md`. Check security first.

Rules:
- Judge the diff, not the whole codebase.
- Every finding needs `file:line` and a concrete suggested fix.
- Do not edit files. Report only.
- If the diff contains a secret, that is CRITICAL and the verdict is BLOCK.

Finish with a verdict line: APPROVE / APPROVE WITH FIXES / BLOCK.

Worktree: <path>
Base: <branch>
