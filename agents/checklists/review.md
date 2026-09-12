# Code Review Checklist

Severity: **CRITICAL** blocks merge · **HIGH** fix before merge · **MEDIUM** consider · **LOW** note.

## Security (check first)
- [ ] No credential, token, key, or password in the diff — including test fixtures
- [ ] No `.env`, `*.pem`, `*.key`, or dump file added
- [ ] User input validated at the boundary before use
- [ ] Queries parameterised — no string-concatenated SQL
- [ ] Output escaped where it reaches HTML
- [ ] Authorization checked on every new endpoint, not just authentication
- [ ] Error responses leak no stack trace, query, or internal path

## Correctness
- [ ] The diff does what the acceptance criteria say — reread them
- [ ] Edge cases: empty, null, zero, very large, concurrent
- [ ] Errors handled explicitly; nothing silently swallowed
- [ ] No behaviour change outside the stated scope

## Quality
- [ ] Functions under 50 lines, files under 800
- [ ] Nesting under 4 levels — early returns instead
- [ ] No magic numbers; named constants
- [ ] No duplicated logic that already exists elsewhere in the repo
- [ ] Naming matches the surrounding code, not a new convention

## Data and performance
- [ ] No N+1 query introduced
- [ ] List endpoints paginated and bounded
- [ ] Migrations are reversible and do not rewrite existing history
- [ ] Indexes exist for new query patterns

## Hygiene
- [ ] No debug statement, commented-out block, or stray file
- [ ] Tests exist for the new behaviour and actually fail without the change
- [ ] Documentation updated if setup or behaviour changed

## Verdict
State one of: **Approve** · **Approve with notes** · **Block**, then list findings by
severity with `file:line` for each.
