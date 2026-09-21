# SUPPORT + NEXONE + Slack — Full-Loop E2E Verification & Fix Plan

**Tanggal:** 2026-09-21 (UTC)
**Definisi done (user):** Full loop E2E
**Klasifikasi:** nexora (strict approval — no prod, no push ke `main`, no `--no-verify`)
**Metode:** OODA + TDD
**Konteks sebelumnya:** `2026-09-15-support-nexone-slack-integration.md` (blocked: service account `support@nexoratech.co` belum jadi member proyek dev; project id dev belum konfirmasi) + `nexone-support-slack-contract.md` (skenario 1/2/3, N1–N4/S1–S4 — sebagian besar sudah dikerjakan).

## 1. Status awal sesi ini (Observe, read-only 21 Sep)

- SUPPORT `dev@ffa5988` (`feat: sync nexone task details`), bersih, tracking `origin/dev`.
- NEXONE `dev@c0f416a` (`feat: expand slack task update controls`), 2 file untracked audit report.
- Kode integrasi inti ada di kedua sisi:
  - SUPPORT: `lib/nexone/{config,client,mapping,sync,outbound,index}.ts`, `app/api/integrations/nexone/sync/route.ts`, `scripts/nexone-sync.mts`, `compose.nexone-sync.yml`, `Dockerfile (sync-worker)`.
  - NEXONE: `Backend/internal/slack/dispatcher.go`, `handlers/slack_commands.go`, `handlers/internal_project.go:PatchTask`, `models.InternalTask{ExternalSource,ExternalRef}`, `server.go` routes slack + `PATCH /:id/tasks/:taskId`.

## 2. Hipotesis gap baru (belum RCA — TDD Red dulu sebelum fix)

| # | Hipotesis | Lokasi | Dampak |
|---|-----------|--------|--------|
| G1 | CLOSED→RESOLVED flap: outbound `CLOSED→done`, inbound `done→RESOLVED` | `SUPPORT/lib/nexone/mapping.ts:114` vs `toTicketStatus` | Tiket CLOSED bisa terbuka kembali jadi RESOLVED tiap pass |
| G2 | Outbound title/desc/dept didukung `sync.ts` tapi tak pernah di-queue (`PATCH tickets/[id]` hanya status/priority/assigneeEmail) | `app/api/tickets/[id]/route.ts:128-134` | Dead code atau edit judul tak tersinkron |
| G3 | Assignee hanya first-assignee + match email persis, tanpa mapping | `sync.ts:firstAssigneeEmail`, `pullNexoneChanges:449` | Assign dari NEXONE hilang diam-diam |
| G4 | Dispatcher `lookbackWindow=1h`: activity >1h saat outage tak pernah diposting & tak pernah di-stamp | `dispatcher.go:17,53` | Event hilang permanen pasca-outage panjang |
| G5 | `SUPPORT/.github/workflows/deploy.yml` tulis ulang `.env` hanya 4 key NEXONE → hapus `SMTP_*`, `DATABASE_URL`, dsb | `deploy.yml:99-105` | Email + config prod hilang tiap deploy |
| G6 | Healthcheck wajib `support-sync Up` padahal service `nexone-sync` butuh `profiles: [nexone-sync]` | `deploy.yml:119-123` vs `compose.nexone-sync.yml:4` | Deploy gagal kecuali profile diaktifkan eksplisit |
| G7 | Pull selalu `board=true` full-dump, abaikan `updated_since`+cursor | `client.ts:201-207`, `sync.ts:378` | O(n) tiap pass, berat saat board besar |
| G8 | `abandoned` outbox hanya di log, tanpa UI admin | `sync.ts:296-297` | Failure invisibel |

Blokir lama yang masih perlu konfirmasi owner: membership service account di proyek dev, project id dev yang benar, kolom Backlog ada.

## 3. Rencana OODA

### Observe
1. `git pull --rebase origin dev` di SUPPORT & NEXONE; catat `status/diff/log`.
2. Baseline (tanpa ubah kode): SUPPORT `npm ci && npm run lint && npm test && npm run build`; NEXONE `go build ./... && go test ./...`, Frontend `npm ci && npm run build`.
3. Cek env dev (nilai secret tidak dicetak): keberadaan `NEXONE_*`, `SLACK_*`, `NEXONE_SYNC_INTERVAL_MS`.

### Orient (RCA + TDD Red)
- Tulis failing test per G1–G8 sebelum sentuh kode produksi.
- Trace loop-prevention (`lastPushedAt` vs `lastSeenRemoteUpdatedAt`, skew jam SQLite vs Postgres), `patchInternalTaskTx` handling `assignee_email/category`, autentikasi service account + `canAccess`.

### Decide
- Prioritas: (a) G1 flap CLOSED, (b) G5+G6 deploy, (c) G2+G3 outbound/assignee, (d) G4 Slack retry, (e) G7+G8 perf/observabilitas.
- Satu perubahan kecil per commit, PR ke `dev` saja. Stop di PR — merge ke `main` owner-controlled.

### Act
- Green → refactor → suite penuh → E2E manual full-loop di dev:
  1. Buat tiket → card Backlog (`external_source='support'`) <60 dtk.
  2. Thread Slack root + reply.
  3. `/task move/done` dari Slack → kolom NEXONE → status tiket + email.
  4. Outbox `delivered`, bukan retry selamanya.

## 4. Verifikasi & DoD
- SUPPORT: `npm run lint`, `npm test`, `npm run build`.
- NEXONE Backend: `go build ./...`, `go test ./...`, `go vet ./...`; Frontend: `npm run build`.
- Diff review: tanpa secret, tanpa file tak terkait.
- Laporan: file diubah, command + hasil, risiko, follow-up. Commit `Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>`.

## 5. Log sesi
- [2026-09-21] Plan dicatat; mulai O1 pull dev + baseline.
- [2026-09-21] O1 done: kedua repo `Already up to date` di `dev`. Baseline hijau: SUPPORT lint/test (210 pass)/build; NEXONE `go build/vet/test` pass.
- [2026-09-21] Orient done (RCA):
  - G1 CONFIRMED (bug) → fix `sync.ts` + 2 tests (SUPPORT `27cc4e7`).
  - G4 CONFIRMED (bug) → fix `dispatcher.go` + 1 test (NEXONE `997e79b`).
  - G6 BUSTED: `support-sync` ada di `docker-compose.yml` base — healthcheck valid.
  - G5 DOWNGRADED: `.env` rewrite aman untuk compose saat ini (SMTP tak pernah via `.env`); hardening merge-vs-overwrite jadi follow-up.
  - G2 BUSTED (non-issue): title/desc/dept paths forward-compat; semua route edit saat ini ter-queue.
  - G3 inherent (single-assignee + warn log) — dokumentasi, tanpa fix.
  - G7/G8 follow-up (incremental pull `updated_since`+cursor; UI observabilitas `abandoned`).
- [2026-09-21] Verifikasi: SUPPORT 212/212 tests + lint + build; NEXONE `go vet` + full `go test` + `go build` pass. Commit lokal di `dev`, belum push.
- Blokir tersisa (owner): membership `support@nexoratech.co` di proyek dev, project id dev, kolom Backlog — untuk E2E live full-loop.
- [2026-09-21] PR dibuka: SUPPORT #6 (`dev`→`main`), NEXONE #15 (`dev`→`main`). Push ke `dev` only; merge ke `main` owner-controlled.
- [2026-09-21] Owner merge ke `main`. Monitor production:
  - CI pasca-merge hijau: SUPPORT run 35626965467 (5m1s), NEXONE run 35626972271 (2m57s), keduanya `success`.
  - Live: `support.nexoratech.co/login` 200 (~1.2s), `nexone.nexoratech.co/` 200, `/health` 200.
  - Playwright vs prod: SUPPORT smoke 3/3 pass (reverse-proxy, login form, zero console-error/failed-request). NEXONE login 1/1 pass (form visible, zero error) via temp spec (dihapus setelah run).
  - False alarm saat run NEXONE: selector `.first()` kena form-variant tersembunyi (mobile+desktop) — bukan bug aplikasi; diperbaiki dengan filter visible.
  - Repo bersih: temp spec + artefak dihapus, `main` sinkron `origin/main`.
- Blokir tersisa untuk full-loop E2E live: service account prod + `NEXONE_*` secrets prod (sengaja belum diset).
- [2026-09-21] Secrets prod dipasang owner. Deploy manual `35629920553` success, tanpa warning "NEXONE sync stays disabled" → integrasi aktif di prod.
- [2026-09-21] E2E live parsial PASS (Playwright vs prod): registrasi akun disposable + wizard tiket `[E2E-DISPOSABLE] Prod sync check <stamp>` terbuat dan muncul di daftar. Dua false alarm test (selector hidden variant, hydration race) — bukan bug aplikasi.
- Sisa verifikasi (butuh akses owner): card muncul di Backlog NEXONE + thread Slack. Cleanup: hapus tiket `[E2E-DISPOSABLE]` + akun `e2e-prod-*@example.com`.
- [2026-09-22] Enhancement comment sync dua arah (OODA+TDD, SUPPORT `715c302`, PR #7): outbound CREATE_COMMENT (skip internal notes + bot echo), inbound cursor `lastSeenRemoteCommentId` + audit COMMENT_ADDED + email, bare comment tak geser status. 223/223 tests, lint+build hijau. NEXONE untouched. Live E2E + cleanup menunggu owner pasca-merge.
