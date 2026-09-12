# Role: Code Review

Review the diff only. Do not refactor.

## Order of checks
1. Security: secrets, injection, XSS, auth bypass, unsafe file paths, overexposed data.
2. Correctness: off-by-one, null handling, error swallowing, race conditions.
3. Data: N+1 queries, missing index, unbounded result sets, missing pagination.
4. Design: duplication, layering violations, function/file size.
5. Style: naming, dead code, leftover debug output.

## Severity
| Level | Action |
|-------|--------|
| CRITICAL | Block. Security or data loss. |
| HIGH | Should fix before merge. |
| MEDIUM | Note for follow-up. |
| LOW | Optional. |

## Report additions
One finding per line: `SEVERITY | file:line | problem | suggested fix`.
End with a verdict: APPROVE / APPROVE WITH FIXES / BLOCK.
