# Prompt: Weekly Repository Health Check (read-only)

For each registered project, report without changing anything:

- Current branch, and how many commits behind the default branch.
- Uncommitted or untracked files.
- Stale branches (no commit in 30+ days).
- Dependency audit result (`npm audit`, `composer audit`, `pip-audit`, `mvn versions:display-dependency-updates`) — summary counts only.
- Whether the test suite runs at all (run it; report pass/fail counts).
- Docs older than the last code change in the same area.

Output one table for all projects, then a short "needs attention this week" list
of at most five items, ordered by risk.

Change nothing. Merge nothing. Files modified: none.
