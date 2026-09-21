# Task: NEXONE: tandai asal task dan kirim aktivitas SUPPORT ke Slack

- **ID:** task-016
- **Project:** NEXONE (`~/AI-Workspace/projects/nexora/NEXONE`)
- **Class:** nexora
- **Role:** backend
- **Worktree:** `~/AI-Workspace/worktrees/task-016`
- **Base branch:** dev

## Background
Kontrak lengkap ada di `agents/reports/nexone-support-slack-contract.md` (item N1 dan N2).
Baca itu dulu sebelum menulis kode.

Skenario yang diminta: ticket dibuat di SUPPORT -> otomatis jadi task NEXONE -> otomatis
muncul di Slack. Bagian terakhir tidak pernah terjadi. `processActivity` di
`Backend/internal/slack/dispatcher.go` membuang setiap aktivitas task yang tidak
sprint-linked, sementara task dari SUPPORT mendarat di kolom Backlog dan bukan bagian dari
sprint. `InternalTask` (`Backend/internal/models/models.go`) juga tidak punya kolom
referensi eksternal, jadi tidak ada cara mengenali "task ini berasal dari ticket SUPPORT".

## Objective
Satu ticket baru di SUPPORT menghasilkan satu pesan Slack, dan setiap perubahan
berikutnya pada task itu menjadi balasan di thread yang sama.

## Scope
- Tambah `ExternalSource` dan `ExternalRef` pada `InternalTask` beserta migrasinya, dengan
  index yang mencegah dua task menunjuk referensi eksternal yang sama.
- Terima kedua field itu sebagai input opsional pada endpoint create internal task, dan
  kembalikan keduanya pada response list/show/create.
- Ubah `processActivity` agar mengirim ketika task sprint-linked **atau** punya
  `external_source` yang terisi. Reuse thread lewat `ensureThread` yang sudah ada.
- Pesan Slack untuk task ber-referensi SUPPORT harus menyebut referensi ticket-nya, supaya
  pembaca di Slack tahu ini datang dari mana.

## Out of scope
- Mengubah sisi SUPPORT (itu task-018 sampai task-020).
- Endpoint `updated_since`/cursor (itu task-017).
- Mengirim pesan Slack sungguhan ke workspace nyata.

## Acceptance criteria
- [x] Migrasi menambah kolom referensi eksternal dan jalan bersih di database kosong maupun yang sudah terisi
- [x] Create task dengan `external_source=support` + `external_ref=<ticketId>` tersimpan dan terbaca kembali lewat API
- [x] Aktivitas pada task ber-`external_source` dikirim ke Slack; unit test membuktikan dispatcher tidak lagi membuangnya
- [x] Aktivitas kedua pada task yang sama masuk sebagai balasan thread, bukan pesan root baru
- [x] Task tanpa sprint dan tanpa `external_source` tetap diabaikan seperti sebelumnya (regresi terjaga)
- [x] `go test ./...`, `go vet`, dan `go build ./cmd/api` hijau, dengan output nyata dikutip di Report

## Constraints
Baca `CLAUDE.md` dan `AGENTS.md` milik NEXONE lebih dulu. Jangan membaca `.env` atau rahasia
apa pun. Jangan menyentuh production. Jangan mengirim pesan Slack sungguhan — test harus
memakai client palsu. Bekerja hanya di worktree ini. Jangan commit dan jangan push; parent
yang memverifikasi lalu mendorong ke `dev` dengan pull-before-push. Kalau ada yang tidak
bisa diselesaikan, tulis apa adanya di Report, jangan dipoles.

## Required checks
- [x] Unit test
- [x] Integration/API test
- [x] Lint
- [x] Build
- [x] Diff reviewed for secrets and stray files

## Progress
- [x] Baca kontrak dan kode dispatcher, catat rencana perubahan
- [x] Migrasi + model
- [x] Endpoint create menerima referensi eksternal
- [x] Dispatcher mengirim aktivitas ber-referensi SUPPORT
- [x] Test regresi untuk task non-sprint tanpa referensi

## Report
- Scope done:
- Files changed:
- Commands run + results:
- Tests:
- Risks:
- Not done / blocked:
- Suggested next task:
