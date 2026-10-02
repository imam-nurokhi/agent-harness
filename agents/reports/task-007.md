# Report — task-007

## Scope done
Read-only analysis of the SUPPORT side of the two-way NEXONE sync, performed by
Ster (qa) through the harness against `projects/nexora/SUPPORT` on branch `dev`.

## Files changed
None.

## Commands run + results
- `npm test -- lib/nexone/{client,mapping,sync}.test.ts` -> 3 files / 64 tests passed
- `npm test -- app/api/integrations/nexone/sync/route.test.ts` -> 1 file / 5 tests passed
- `npm run lint` -> exit 0
- `npm run build` -> exit 0
- `git diff --check`, `git status --short` -> no output, no changes

## Findings — what works
Outbound SUPPORT -> NEXONE ticket creation works, with priority and column/status
mapping covered by tests (`lib/nexone/mapping.ts:10`, `:31`). Correlation is stored
locally via `lastPushedAt` / `lastSeenRemoteUpdatedAt`, because NEXONE tasks carry no
external reference field (`prisma/schema.prisma:119`).

## Findings — what is NOT actually two-way
1. **No update path outbound.** The client exposes only `getProject`, `createTask`,
   `listTasks` (`lib/nexone/client.ts:157`). Once a ticket is created, any later change
   to status, title, description, priority, department, or assignee in SUPPORT is never
   pushed to NEXONE.
2. **Inbound never creates tickets.** Pull only processes tasks whose id already exists
   in a local link (`lib/nexone/sync.ts:227`, `:252`). A task created in NEXONE produces
   no SUPPORT ticket. The title can be parsed for a ticket reference
   (`lib/nexone/mapping.ts:61`) but pull does not use it to find or create a link.
3. **Inbound ignores everything but column/status.** Other field changes are dropped, and
   deleted tasks are skipped with no reconciliation (`lib/nexone/sync.ts:254`).
4. **Unmapped NEXONE columns are silently inert** (`lib/nexone/sync.ts:277`).
5. **No scheduler.** Failures recover only on the next manual or cron trigger
   (`app/api/integrations/nexone/sync/route.ts:6`, `scripts/nexone-sync.mts:2`).

## Contract SUPPORT expects from NEXONE
| Concern | SUPPORT's expectation |
|---|---|
| Auth | `POST /api/v1/auth/login` -> `{ token }`, Bearer JWT (`client.ts:94`) |
| Board | `GET /internal-projects/{id}` -> `columns[]` with `id`, `key`, `label` (`client.ts:31`) |
| Create | `POST /internal-projects/{id}/tasks` with `title`, `description`, `category`, lowercase `priority`, `column_id` (`client.ts:50`) |
| Read | `GET .../tasks?board=true` -> `{ data: NexoneTask[] }` with `id`, `project_id`, `column_id`/`column.key`, `status`, `updated_at` (`client.ts:37`, `:168`) |

## Tests
All SUPPORT-side checks pass: 69 tests across unit and route integration, lint, build.

## Risks
Every HTTP test is mocked. The contract above has not been verified against the live
NEXONE API. Main regression risks: column keys change, `updated_at` format drifts, or
NEXONE stops returning the `{ data }` envelope.

## Not done / blocked
No real sync was run, no `.env` read, no live NEXONE API exercised — all out of scope.

## Suggested next task
Match these contract expectations against task-006's NEXONE findings, then decide
whether outbound updates and inbound ticket creation are actually wanted before
building either.
