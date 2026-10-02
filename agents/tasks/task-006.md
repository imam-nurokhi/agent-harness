# Task: Analisa gap Slack two-way integration NEXONE + SUPPORT

- **ID:** task-006
- **Project:** NEXONE (`projects/nexora/NEXONE`) + SUPPORT (`projects/nexora/SUPPORT`)
- **Class:** nexora
- **Role:** review
- **Worktree:** none (read-only analysis)
- **Base branch:** dev

## Background
Integrasi Slack dua arah sudah sebagian besar mendarat di dev (10 commit slack di NEXONE, sinkronisasi tiket dua arah di SUPPORT). Build dan test kedua sisi hijau. Namun plan `docs/superpowers/plans/2026-09-07-slack-two-way-integration.md` masih memiliki 69 kotak centang kosong, jadi tidak jelas apa yang benar-benar belum selesai.

## Objective
Laporan gap yang menyebutkan dengan bukti file:line apa yang sudah selesai, apa yang belum, dan tiga langkah berikutnya yang paling bernilai.

## Scope
- Baca plan dan spec Slack di NEXONE
- Bandingkan dengan kode yang benar-benar ada di NEXONE/Backend/internal/slack dan SUPPORT/lib/nexone
- Periksa TODO, jalur yang belum terhubung, dan arah sinkronisasi yang belum dua arah
- Periksa apakah checkbox plan hanya basi atau memang menandakan pekerjaan nyata

## Out of scope
- Mengubah kode apa pun
- Commit, push, merge, atau menyentuh branch dev
- Menyentuh repo cbqa atau NEXFINANCE yang sedang ON HOLD

## Acceptance criteria
- [x] Setiap klaim 'sudah selesai' didukung bukti file:line
- [x] Daftar pekerjaan yang benar-benar belum selesai, bukan sekadar checkbox yang belum dicentang
- [x] Tiga langkah berikutnya diurutkan berdasarkan nilai, masing-masing dengan acceptance criteria
- [x] Laporan menyatakan 'Files modified: none'

## Constraints
READ-ONLY. Jangan ubah satu file pun. Sebutkan bukti sebagai file:line untuk setiap klaim. Jawab dalam Bahasa Indonesia.

## Required checks
- [x] Unit test
- [x] Integration/API test
- [x] Lint
- [x] Build
- [x] Diff reviewed for secrets and stray files

## Report
- Scope done:
- Files changed:
- Commands run + results:
- Tests:
- Risks:
- Not done / blocked:
- Suggested next task:
