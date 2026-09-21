# Task: SUPPORT: outbound update status + proteksi loop

- **ID:** task-020
- **Project:** SUPPORT (`~/AI-Workspace/projects/nexora/SUPPORT`)
- **Class:** nexora
- **Role:** backend
- **Worktree:** `~/AI-Workspace/worktrees/task-020`
- **Base branch:** dev

## Background
Kontrak lengkap: `agents/reports/nexone-support-slack-contract.md` (item S3 dan S4).

Keputusan Imam: perubahan **status** ticket di SUPPORT ikut dikirim ke NEXONE. Tanpa ini
kedua sistem berpisah begitu ada orang menyunting dari sisi SUPPORT. Saat ini
`lib/nexone/client.ts` hanya punya `getProject`, `createTask`, `listTasks` — endpoint
update dan move milik NEXONE sudah ada dan menganggur.

Bahaya utamanya loop: perubahan dari Slack masuk ke NEXONE, ditarik SUPPORT, lalu didorong
balik ke NEXONE, dan seterusnya. Fondasi penangkalnya sudah ada (`lastPushedAt` dan
`lastSeenRemoteUpdatedAt` di `TicketExternalLink`) tetapi belum pernah dibuktikan test.

## Objective
Perubahan status di SUPPORT sampai ke NEXONE, dan tidak ada perubahan yang memantul
bolak-balik antara kedua sistem.

## Scope
- Tambah `updateTask`/`moveTask` di client NEXONE.
- Antrikan pengiriman saat status ticket berubah, lewat outbox yang sama dengan create
  supaya retry dan urutannya konsisten.
- Bukti proteksi loop lewat test: `/task move` di Slack -> kolom NEXONE berubah -> ticket
  SUPPORT ter-update -> SUPPORT **tidak** mendorong balik ke NEXONE.
- Tentukan pemenang saat kedua sisi berubah sebelum sempat sinkron, implementasikan, dan
  tuliskan aturannya di kode maupun Report.

## Out of scope
- Mendorong field selain status untuk sekarang. Kalau menurut Anda field lain wajib ikut,
  tulis argumennya di Report; jangan diam-diam menambah cakupan.

## Acceptance criteria
- [x] Mengubah status ticket di SUPPORT memindahkan task NEXONE ke kolom yang sesuai, dibuktikan test
- [x] NEXONE yang sedang mati tidak membuat perubahan status di SUPPORT gagal; pengiriman diulang belakangan
- [x] Regression test membuktikan rantai Slack -> NEXONE -> SUPPORT berhenti dan tidak memantul balik
- [x] Aturan pemenang saat konflik terdefinisi dan tertutup test
- [x] Bentuk response create/update/move NEXONE ditangani konsisten oleh client
- [x] `npm test`, `npm run lint`, `npm run build` hijau dengan output dikutip

## Constraints
Baca `AGENTS.md`/README SUPPORT lebih dulu, dan baca task-016 sampai task-018 bila sudah
mendarat agar kontraknya tidak bertabrakan. Jangan membaca `.env`, jangan menyentuh
production, jangan memanggil API NEXONE sungguhan — pakai mock. Bekerja hanya di worktree
ini. Jangan commit, jangan push.

## Required checks
- [x] Unit test
- [x] Integration/API test
- [x] Lint
- [x] Build
- [x] Diff reviewed for secrets and stray files

## Progress
- [x] `updateTask`/`moveTask` di client
- [x] Antrikan perubahan status lewat outbox
- [x] Test proteksi loop
- [x] Aturan konflik

## Report
- Scope done:
- Files changed:
- Commands run + results:
- Tests:
- Risks:
- Not done / blocked:
- Suggested next task:
