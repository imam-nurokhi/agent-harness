# Task: Fase 7: kirim artefak (diff, report, log) ke Telegram

- **ID:** task-037
- **Project:** AI-Workspace (`~/AI-Workspace`)
- **Class:** personal
- **Role:** backend
- **Worktree:** `~/AI-Workspace/worktrees/task-037`
- **Base branch:** main

## Background
`/tail` memotong output di 2800 karakter dan `tgcore.send()` memecah pesan di 3800.
Diff dan laporan panjang tidak bisa dibaca dari HP sama sekali. Telegram bisa menerima
dokumen, tapi `tgcore` hanya bisa mengirim teks.

## Objective
Diff, laporan, dan log penuh bisa dibaca dari HP sebagai berkas.

## Scope
- `tgcore.send_document(chat_id, path, caption)` — encoder multipart/form-data manual, stdlib
- `/diff <task-id>` — `git -C worktrees/<id> diff` ke berkas sementara
- `/report <task-id>` — laporan/transkrip dari `agents/reports/`
- `/log <job-id>` — log penuh saat `/tail` terpotong

## Out of scope
- Mengirim gambar/screenshot otomatis

## Acceptance criteria
- [ ] `/diff` pada worktree kotor mengirim berkas yang isinya sama dengan `git diff`
- [ ] Mencoba mengirim `.env` **ditolak**, dan penolakannya diuji — bukan hanya ditulis
- [ ] Path di luar workspace ditolak
- [ ] Berkas > 20 MB ditolak dengan pesan jelas, bukan gagal diam-diam
- [ ] `/report` pada task tanpa laporan memberi pesan yang berguna
- [ ] Suite lama tetap hijau

## Constraints
- Guard wajib dan diuji: tolak path di luar workspace, tolak `.env`/`*.pem`/`*.key`/`*.p12`,
  batas 20 MB.
- Stdlib-only — tidak ada `requests`.

## Required checks
- [ ] Unit test
- [ ] Integration/API test
- [ ] Lint
- [ ] Build
- [ ] Diff reviewed for secrets and stray files

## Progress
- [ ] send_document
- [ ] /diff /report /log
- [ ] guard + test

## Report
- Scope done:
- Files changed:
- Commands run + results:
- Tests:
- Risks:
- Not done / blocked:
- Suggested next task:
