# Task: Fase 1d: bot Telegram non-blocking + level izin per-chat

- **ID:** task-031
- **Project:** AI-Workspace (`~/AI-Workspace`)
- **Class:** personal
- **Role:** backend
- **Worktree:** `~/AI-Workspace/worktrees/task-031`
- **Base branch:** main

## Background
Dua masalah di `bin/lib/tgbot.py`:

1. `_dispatch` memanggil handler **sinkron di dalam poll loop**. `/doctor` punya timeout
   60 detik — selama itu seluruh bot membeku, termasuk notifikasi.
2. Allow-list rata: setiap chat yang ter-pair boleh `/run` apa pun, termasuk ke repo cbqa.
   Tidak ada beda antara "baca /status" dan "dispatch agent".

Level izin ini jadi prasyarat approval gate (task-033): yang boleh menyetujui push harus
lebih sempit daripada yang boleh melihat papan.

## Objective
Bot tetap responsif saat handler lambat, dan hak setiap chat dibatasi sesuai perannya.

## Scope
- `tgbot.py` — eksekusi handler pindah ke `concurrent.futures.ThreadPoolExecutor(4)`;
  `_notify()` di thread sendiri dengan cadence sendiri
- `agents/.telegram/config.json` dapat `roles: {chat_id: level}`,
  level `viewer | operator | owner`
- Chat yang sudah ter-pair diperlakukan `owner` (kompatibel mundur, tidak mengunci diri sendiri)
- Setiap handler diberi tag level minimum; `_dispatch` menolak sebelum memanggil
- Perintah baru `/grant <chat_id> <level>` (khusus owner)
- `tgwatch.detect()` memakai ikon `failed` + exit code (menyusul Fase 1c)
- `dash.js` dapat state visual `failed`

## Out of scope
- Approval gate (task-033)
- Tombol inline (task-034)

## Acceptance criteria
- [ ] `/doctor` yang lambat tidak menghalangi `/status` yang dikirim sesudahnya
- [ ] Chat level `viewer` ditolak saat mencoba `/run`, dan penolakan tercatat di log
- [ ] Chat yang sudah ter-pair sebelum perubahan ini tetap punya akses penuh
- [ ] Job gagal tampil `🛑` + exit code di Telegram dan di Command Center, bukan `✅`
- [ ] Test baru untuk matriks izin hijau; suite lama tetap hijau

## Constraints
- Stdlib-only.
- Penolakan harus dicatat (chat id + username + perintah), seperti penolakan pairing sekarang.
- Jangan sampai owner terakhir bisa menurunkan dirinya sendiri hingga tidak ada owner tersisa.

## Required checks
- [ ] Unit test
- [ ] Integration/API test
- [ ] Lint
- [ ] Build
- [ ] Diff reviewed for secrets and stray files

## Progress
- [ ] thread pool
- [ ] level izin + `/grant`
- [ ] ikon failed di tgwatch + dash
- [ ] test

## Report
- Scope done:
- Files changed:
- Commands run + results:
- Tests:
- Risks:
- Not done / blocked:
- Suggested next task:
