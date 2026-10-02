# Task: Verifikasi dan hardening Telegram task management untuk task-004

- **ID:** task-005
- **Project:** AI-Workspace harness (`/Users/user/AI-Workspace`)
- **Class:** personal
- **Role:** backend
- **Worktree:** `/Users/user/AI-Workspace/worktrees/task-005`
- **Base branch:** main

## Background
Implementasi awal task-004 sudah ada di `main`, tetapi belum memiliki automated tests atau bukti verifikasi yang cukup untuk menutup task.

## Objective
Menyediakan regression tests stdlib-only dan memperbaiki temuan implementasi yang diperlukan agar task-004 dapat diverifikasi aman.

## Scope
- Tambahkan unit tests untuk handler mutasi task, otorisasi chat, dan kontrol notifikasi.
- Tambahkan integration-style tests untuk dispatch Telegram dengan transport yang dimock.
- Perbaiki hanya bug yang ditemukan oleh tests atau review, di dalam modul Telegram harness.
- Jalankan lint/build Python yang tersedia tanpa dependensi baru.

## Out of scope
- Mengubah proyek di luar harness.
- Menjalankan bot terhadap Telegram produksi, deploy, push, merge, atau membaca `.env`.
- Perubahan fitur yang tidak dibutuhkan untuk acceptance criteria task-004.

## Acceptance criteria
- [x] Tests membuktikan chat belum dipasangkan tidak dapat menjalankan handler mutasi.
- [x] Tests membuktikan `/new`, `/assign`, `/wt`, dan `/tick` mengubah task hanya untuk chat yang diizinkan.
- [x] Tests membuktikan notifikasi hanya untuk event penting, `/quiet` bekerja, dan `/digest` tersedia sesuai permintaan.
- [x] `unittest`, compile/lint yang relevan, dan pemeriksaan diff lulus tanpa secrets atau stray files.

## Constraints
Python stdlib saja. Jangan baca, cetak, atau ubah `.env`, token, atau konfigurasi Telegram privat. ASSUMPTION: task-004 adalah baseline fitur yang harus dipertahankan, bukan ditulis ulang.

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
