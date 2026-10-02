# Report — task-006

## Scope done
Read-only contract analysis of NEXONE's internal-task API, run by Kuda (review) via the
harness against `projects/nexora/NEXONE`. Paired with task-007 (SUPPORT side) so the two
halves of the integration could be compared.

## Files changed
None.

## Commands run + results
- `go test ./internal/handlers ./internal/server ./internal/slack` -> pass
- `go vet` on the same packages -> pass
- `go build ./cmd/api` -> pass
- `git diff --check` -> clean; `git status --short` -> two pre-existing untracked
  performance-audit markdown files, not ours

## Answering the contract questions
1. **Endpoints.** List, create, update and move all exist; update is a targeted operation,
   not a general partial update.
2. **`updated_at` and column key.** Both exposed. `InternalTask` embeds `Base`, which
   exports `updated_at` (`internal/models/models.go:67`). The column is preloaded on list,
   create, update and move, so `column.key` is available
   (`internal/models/models.go:295`, `:305`; `internal/handlers/internal_project.go:686`).
3. **Can SUPPORT learn about new NEXONE tasks?** **No — this is the real gap.** There is no
   webhook or push from NEXONE. Only polling `GET /internal-projects/:id/tasks`, and that
   endpoint accepts just `page`, `limit`, `q` — no `updated_since` or cursor
   (`internal/handlers/handlers.go:64`, `internal/server/server.go:69`). Task creation does
   record a `created` activity (`internal_task_service.go:47`), but the dispatcher only
   forwards sprint-linked activity to Slack (`internal/slack/dispatcher.go:68`), never to
   SUPPORT.
4. **Response envelope.** Inconsistent. Only list wraps in `{data, total, page, limit}`
   (`internal_project.go:907`). Create, update and move return the bare task object
   (`:949`, `:1099`, `:1166`).

## The cross-check that matters
Read together with task-007, the two sides disagree in a way neither would notice alone:

| | NEXONE provides | SUPPORT expects |
|---|---|---|
| New-task signal | none (poll only, no `updated_since`) | relies on polling; **never creates tickets inbound anyway** |
| Envelope | `{data}` on list only | `{ data: NexoneTask[] }` on list — matches today |
| Update path | update/move endpoints exist | **client has no `updateTask` at all** |

So "two-way" is currently **one-and-a-half-way**: SUPPORT pushes ticket creation to NEXONE
and pulls column/status changes back, but nothing else flows either direction. Notably the
missing pieces are complementary — NEXONE exposes update endpoints SUPPORT never calls,
while SUPPORT wants a new-task signal NEXONE never sends.

## Tests
NEXONE: handlers, server and slack packages pass; vet and build pass.
SUPPORT (task-007): 69 tests, lint and build pass.

## Risks
HIGH — no reliable NEXONE -> SUPPORT signal for new or changed tasks.
MEDIUM — response envelope differs between list and create/update/move, so a future
SUPPORT `updateTask` would need to parse both shapes.
Every SUPPORT-side HTTP test is mocked; the contract has not been exercised live.

## Not done / blocked
The first attempt failed because its worktree was deleted mid-run (my error, now guarded
against). A second attempt on the `claude` engine hung for 861s with zero output in this
repo. A third attempt drowned in the 2,955-line plan document. This run succeeded once the
plan file was explicitly excluded and the questions narrowed.

## Suggested next task
Decide the sync contract before building anything:
1. NEXONE -> SUPPORT signal: webhook/outbox, or polling with `updated_since` + a stable
   cursor. AC: a new or changed task is delivered once and is retryable.
2. Add `updated_since` and a cursor to the task list endpoint. AC: SUPPORT can fetch all
   changes without scanning the whole board.
3. Normalise the response envelope, or give SUPPORT an adapter handling both shapes.
   AC: list/create/update/move all parse consistently, covered by an integration test.

Verdict: APPROVE WITH FIXES — nothing is broken, but "two-way" is not yet accurate.
