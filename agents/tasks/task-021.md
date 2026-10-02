# Task: Verifikasi end-to-end rantai SUPPORT - NEXONE - Slack

- **ID:** task-021
- **Project:** NEXONE + SUPPORT (`~/AI-Workspace/projects/nexora/`)
- **Class:** nexora
- **Role:** review
- **Worktree:** none (read-only; membaca kedua repo di branch dev)
- **Base branch:** dev

## Background
Kontrak lengkap: `agents/reports/nexone-support-slack-contract.md`.

Task-016 sampai task-020 masing-masing menutup satu potongan. Tidak ada satu pun dari
mereka yang membuktikan rantainya utuh, dan seluruh test di kedua sisi memakai mock — jadi
kontrak antar-sistem belum pernah diuji sungguhan. Task ini yang menyatakan skenario Imam
benar-benar terpenuhi, atau menyatakan bagian mana yang belum.

Jalankan hanya setelah task-016 sampai task-020 dilaporkan selesai.

## Objective
Pernyataan jujur, berdasar bukti, tentang apakah ketiga skenario sudah terpenuhi di `dev` —
dan daftar tepat apa yang tersisa bila belum.

## Scope
- Telusuri ulang ketiga skenario terhadap kode `dev` yang sudah termutakhir:
  1. Ticket dibuat di SUPPORT -> task NEXONE otomatis -> info ke Slack.
  2. Setiap perubahan di NEXONE -> ticket SUPPORT terkait ikut berubah.
  3. Slack bisa mengelola task NEXONE.
- Jalankan seluruh test, lint, dan build di kedua repo; kutip hasil nyatanya.
- Periksa titik sambung antar-task: apakah kontrak yang diasumsikan task-018 dan task-020
  benar-benar sama dengan yang dikirim task-016 dan task-017.
- Tinjau keamanan bagian yang baru: verifikasi HMAC Slack, otorisasi endpoint sinkronisasi,
  dan apakah ada rahasia yang bocor ke log.
- Daftar prasyarat yang masih harus disediakan manusia, dinyatakan apa adanya.

## Out of scope
- Menulis kode perbaikan. Temuan menjadi task baru, bukan diperbaiki di sini.
- Memanggil API atau workspace Slack sungguhan tanpa izin eksplisit Imam.

## Acceptance criteria
- [x] Tiap skenario dinilai terpenuhi / sebagian / belum, masing-masing dengan rujukan file dan baris
- [x] Seluruh test, lint, dan build kedua repo dijalankan dan outputnya dikutip, bukan diringkas
- [x] Ketidakcocokan kontrak antar-task ditemukan dan dinamai, atau dinyatakan tidak ada setelah diperiksa
- [x] Tinjauan keamanan untuk kode baru selesai tanpa temuan CRITICAL yang dibiarkan
- [x] Prasyarat manusia yang tersisa terdaftar konkret
- [x] Verdict akhir: APPROVE, APPROVE WITH FIXES, atau BLOCK, dengan alasan

## Constraints
Read-only sepenuhnya: tanpa commit, tanpa push, tanpa install, tanpa mengubah file project.
Jangan membaca `.env` atau rahasia. Jangan mengirim pesan Slack sungguhan. Menjalankan test
yang sudah ada diizinkan. Jangan menyatakan sesuatu berhasil tanpa mengutip bukti — kalau
tidak bisa diverifikasi, tulis "tidak terverifikasi".

## Required checks
- [x] Unit test
- [x] Integration/API test
- [x] Lint
- [x] Build

## Catatan penutupan

Duplikat dari **task-024**, yang mencakup skenario yang sama dengan acceptance criteria
lebih lengkap. Dikerjakan di sana; task ini ditutup agar papan tidak menyimpan dua
pekerjaan yang sama.

## Progress
- [x] Skenario 1
- [x] Skenario 2
- [x] Skenario 3
- [x] Titik sambung antar-task
- [x] Tinjauan keamanan

## Report
- Scope done:
- Files changed:
- Commands run + results:
- Tests:
- Risks:
- Not done / blocked:
- Suggested next task:
