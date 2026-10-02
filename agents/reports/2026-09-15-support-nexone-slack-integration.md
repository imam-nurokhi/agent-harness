# SUPPORT → NEXONE → Slack integration

**Status:** dev wired and deployed; **blocked** on one NEXONE membership grant
**Last updated:** 2026-09-15
**Repos:** `Nexora-Tech-Team/SUPPORT`, `Nexora-Tech-Team/NEXONE`
**Related task:** `agents/tasks/task-038.md` (NEXONE auth finding — *not* to be executed yet)

**Continuation update, 2026-09-16 WIB:** code-level user-awareness gaps were closed on
`dev` in both repos. Local commits: NEXONE `413c9bb`, SUPPORT `197e541`. They have not
been pushed.

---

## 1. What this integration is

A ticket raised in SUPPORT should appear as a card on the NEXONE internal-project
board, and NEXONE should then announce it in Slack. Status changes flow back.

```
SUPPORT ticket ──► IntegrationOutbox ──► support-sync worker
                                              │  POST /api/v1/internal-projects/<id>/tasks
                                              ▼
                                      NEXONE card (external_source='support')
                                              │
                                              ▼
                                      NEXONE Slack dispatcher ──► #channel
                                              │  status change
                                              ▼
                                      back into SUPPORT (pullNexoneChanges)
```

Slack is the **last** link. It never fires on its own: no card ⇒ no
`external_source='support'` ⇒ NEXONE's dispatcher has nothing to announce.

---

## 2. Root cause (established 2026-09-15)

Not a code bug. `getNexoneConfig()` (`lib/nexone/config.ts:24-30`) returns `null`
unless `NEXONE_BASE_URL`, `NEXONE_SERVICE_EMAIL` **and** `NEXONE_SERVICE_PASSWORD`
are all present, and `scheduleNexoneSync()` then returns **silently** — no log line.
That silence is why this read as "nothing happened".

Tickets were still queued correctly (`enqueueTicketCreated` always writes an
`IntegrationOutbox` row — ticket TK-384A18 proved it). Nothing drained the queue.

The SUPPORT repo had **no NEXONE secrets and no repository variables at all**, so
the integration was off in *both* tiers — dev included. Earlier dev screenshots
proved the redirect fix, never the integration.

Production additionally lacked the plumbing, not just the values:

| | dev | prod (before this work) |
|---|---|---|
| `NEXONE_*` env on web container | yes | **absent** |
| Sync worker container | `support-dev-sync` | **absent** |
| `.env` written at deploy time | yes | **absent** |
| `NEXONE_SYNC_INTERVAL_MS` | 60000 | **absent** |

Without a worker, prod's web container drained the outbox only opportunistically
after an HTTP request.

---

## 3. Done

### 3.1 Code — `dev` branch, pushed, CI green

| Commit | What |
|---|---|
| `12c122e` | Production brought to parity with dev: `NEXONE_*` passthrough, `.env` written at deploy, `support-sync` service, deploy fails if the worker is not alive |
| `12420b2` | Dev reads **`NEXONE_DEV_*`** secret names instead of the shared ones |

Run `34938893656` — Verify ✓, Deploy to dev ✓, E2E smoke ✓.

**Why `12420b2` exists.** `deploy-dev.yml` and `deploy.yml` both read
`secrets.NEXONE_BASE_URL`, and repository secrets are shared by every workflow.
Whichever tier was configured last would have pointed the other tier at the wrong
NEXONE — dev tickets landing on the production board, or the reverse. GitHub
Environments are the correct separation but the API returns 404 on this
repository's plan, so the tiers are separated by **name**: dev reads
`NEXONE_DEV_*`, production keeps the unprefixed names.

### 3.2 Service account — NEXONE dev

Created via the public `POST /api/v1/auth/register`:

| Field | Value |
|---|---|
| Email | `support@nexoratech.co` |
| Name | SUPPORT Integration Bot |
| User id (dev) | 24 |
| Role | `member`, `app_role_id` NULL |
| Password | 28 random chars — GitHub secret + `~/.config/nexora/nexone-dev-support-bot.env` (0600) |

Dev NEXONE runs its own Postgres (`nexone_dev_postgres_data` in
`docker-compose.dev.yml`), so this account exists **only** in dev. Production has
no service account yet.

### 3.3 Environments confirmed

| Tier | NEXONE base URL | Host | Probe |
|---|---|---|---|
| dev | `https://dev-nexone.nexoratech.co` | `72.61.209.201` | `/` 200, `/api/v1/auth/me` 401 |
| prod | `https://nexone.nexoratech.co` | `72.61.209.201` | — |

The dev hostname is **not** in Notion; it came from the NEXONE repo
(`docker-compose.dev.yml:63`, `docs/deployment/dev-environment.md`). Notion records
only the production host, and its knowledge base forbids storing credentials by
policy — which is why the service account had to be created, not looked up.

### 3.4 Secrets set on `Nexora-Tech-Team/SUPPORT`

| Name | Kind | Value |
|---|---|---|
| `NEXONE_DEV_BASE_URL` | secret | `https://dev-nexone.nexoratech.co` |
| `NEXONE_DEV_SERVICE_EMAIL` | secret | `support@nexoratech.co` |
| `NEXONE_DEV_SERVICE_PASSWORD` | secret | (generated) |
| `NEXONE_DEV_PROJECT_ID` | variable | `15` — **unverified on dev, see §4** |

Production `NEXONE_BASE_URL` / `NEXONE_SERVICE_EMAIL` / `NEXONE_SERVICE_PASSWORD` /
`NEXONE_PROJECT_ID`: **not set**, deliberately.

### 3.5 Continuation — user-awareness coverage

The prior agent branch `origin/claude/ooda-enhancement-verification-kiy254` was checked
against current `dev`; its NEXONE commit `41a0042` and SUPPORT commit `8061cfb` are
already ancestors of `dev`.

Additional gaps found and fixed with TDD:

| Repo | Gap | Fix |
|---|---|---|
| NEXONE | Task creator was not always notified when an assigned/created task changed. Status moves notified assignees only; priority patches from SUPPORT created Slack activity but no personal app notification. | `moveInternalTaskTx`, `patchInternalTaskTx`, Slack assignment, and full task edit now include the creator plus assignees where applicable. |
| SUPPORT | Inbound NEXONE priority changes updated the ticket and audit log, but did not email the requester/assignee. | Added `sendPriorityChangedEmails()` and call it from `pullNexoneChanges()` when priority changes arrive from NEXONE. |

Verification run after the fix:

| Repo | Command | Result |
|---|---|---|
| NEXONE | `GOCACHE=/private/tmp/nexone-go-build-cache go test ./...` | pass |
| NEXONE | `GOCACHE=/private/tmp/nexone-go-build-cache go vet ./...` | pass |
| NEXONE | `GOCACHE=/private/tmp/nexone-go-build-cache go build ./...` | pass |
| SUPPORT | `npm test` | pass — 18 files / 201 tests |
| SUPPORT | `npm run lint` | pass |
| SUPPORT | `npm run build` | pass; one pre-existing Turbopack/NFT warning on upload-route tracing |

Changed files:

| Repo | Files |
|---|---|
| NEXONE | `Backend/internal/handlers/internal_task_service.go`, `Backend/internal/handlers/internal_project.go`, `Backend/internal/handlers/internal_task_patch_test.go`, `Backend/internal/handlers/internal_task_assignee_test.go` |
| SUPPORT | `lib/email.ts`, `lib/nexone/sync.ts`, `lib/nexone/sync.test.ts` |

---

## 4. Blocked — needs the owner

**The service account cannot reach the board.**
`GET /api/v1/internal-projects/15` → `403 "You do not have access to this internal
project"`.

`InternalProjectHandler.canAccess` (`Backend/internal/handlers/internal_project.go:29-38`)
requires an `internal_project_members` row, or `role = "admin"`. Adding a member
needs an admin or the project owner; neither is available to this session, and SSH
to the VPS is blocked by sandbox policy.

Three things are needed, all in NEXONE **dev** (`dev-nexone.nexoratech.co`):

1. **Add `support@nexoratech.co` as a member** of the target internal project.
2. **Confirm the project id on dev.** `15` is the *production* id. Dev has a separate
   database, so the id is very likely different. If it differs, the
   `NEXONE_DEV_PROJECT_ID` variable gets that value instead.
3. **Confirm the board has a `Backlog` column.** `sync.ts:132-135` refuses to drain
   the queue without one, and logs
   `[NEXONE] Project has no Backlog column; leaving the queue untouched.`

Until then the dev worker runs, authenticates, and fails on project access.

---

## 5. Plan

### Phase A — unblock dev *(owner: 2 minutes)*
Grant the membership, confirm the project id and the Backlog column.

### Phase B — verify the full chain on dev *(this session)*
1. Raise a ticket in dev SUPPORT.
2. Confirm the card appears in the dev NEXONE Backlog with `external_source='support'`.
3. Confirm Slack posts.
4. Move the card in NEXONE; confirm the status flows back into SUPPORT.
5. Confirm the outbox row is marked processed, not retried forever.

### Phase C — production *(owner approval required — not started)*
1. Create the service account on production NEXONE and add it to project 15.
   It will **not** be self-registered: production should get an explicit AppRole
   (see §6), not the NULL-role bypass.
2. Set the unprefixed `NEXONE_*` secrets + `NEXONE_PROJECT_ID=15`.
3. PR `dev` → `main`, owner review, merge.
4. Re-run the prod deploy; confirm the `support-sync` worker is alive (the deploy
   now fails if it is not).
5. Repeat the Phase B walkthrough against production, with a disposable ticket.

Pushing to `main` is owner-controlled; this session stops at the PR.

---

## 6. Security findings

### 6.1 NEXONE — self-registration grants full permissions *(new, 2026-09-15)*

`POST /api/v1/auth/register` is public (`server.go:48`) and creates a user with
`app_role_id` NULL. `requirePermissions` (`middleware/permissions.go:42-45`) treats
a NULL role as **allow everything** rather than allow nothing:

```go
if user.AppRoleID == nil {
    c.Next()
    return
}
```

Verified with the newly created account, which holds no role at all:
`GET /clients` 200, `GET /dashboard` 200, `GET /internal-projects/dashboard` 200.
Client data is readable by anyone who can self-register. The internal-project
endpoints survive only because of the separate `canAccess` membership check —
other route groups have no such second gate. The same code is on `main`, so
production must be assumed affected.

Written up as **`agents/tasks/task-038.md`**, deliberately left `planned` — no claim,
no worktree, no run — pending the owner's decision.

**Coupling to note:** the dev service account currently depends on this very bypass.
Closing the hole without giving that account an explicit AppRole
(`internal-project.projects` read + edit) plus project membership will break the
SUPPORT integration. Both belong in the same change.

### 6.2 Carried over from earlier in the session

- A GitHub token (`gho_…`) sits in plaintext in `/root/.git-credentials` on the VPS
  and is embedded in NEXONE's git remote URL. **Rotate.**
- The VPS root password was shared in chat. **Rotate.**
- Prod CI→VPS SSH is still unproven: both prod deploy runs failed on
  `dial tcp :22 i/o timeout`, and the deploy that landed came from the server-side
  cron fallback. `maxstartups 10:30:100` against ~14.7k logged auth failures makes
  sshd drop runner connections at random. Consider raising MaxStartups or moving
  prod to a self-hosted runner as dev already does.

---

## 7. Reference

| Thing | Where |
|---|---|
| Config gate | `lib/nexone/config.ts:24-30` |
| Silent skip | `lib/nexone/index.ts:41-46` |
| API base path | `lib/nexone/client.ts:85` — `<base>/api/v1` |
| Login | `lib/nexone/client.ts:108-146` |
| Project-scoped endpoints | `lib/nexone/client.ts:172-196` |
| Backlog column requirement | `lib/nexone/sync.ts:132-135` |
| NEXONE access check | `Backend/internal/handlers/internal_project.go:29-38` |
| NEXONE permission middleware | `Backend/internal/middleware/permissions.go:24-65` |
| Dev routing | `NEXONE/docker-compose.dev.yml:63,85` |
| Two-way Slack control (separate, unexecuted) | `NEXONE/docs/superpowers/plans/2026-09-07-slack-two-way-integration.md` |

### Earlier in this session, resolved
Dual-role redirect (agent + customer forced to `/admin`) fixed in production.
`origin/main` and `origin/dev` were byte-identical; production was running `ecf2685`
(2026-05-21) because SUPPORT had **zero** deploy secrets, so `Check deploy secrets`
skipped the SSH deploy on every run while reporting green. Production now runs
`abece91`. Backups before the jump (the entrypoint runs
`prisma db push --accept-data-loss`): `/root/backups/support/prod.db.20260915-024400`,
`uploads.20260915-024400.tgz`. Test ticket TK-384A18 and its dependent rows were
deleted afterwards; backup `prod.db.pre-delete.20260915-042820`.
