# Task: Fase 4: percakapan dua arah dengan agent + tombol inline

- **ID:** task-034
- **Project:** AI-Workspace (`~/AI-Workspace`)
- **Class:** personal
- **Role:** backend
- **Worktree:** `~/AI-Workspace/worktrees/task-034`
- **Base branch:** main

## Background
Setiap run sekarang sekali jalan: `jobs.spawn()` memanggil `claude -p <prompt>` lalu melepas.
Tidak ada kanal untuk membalas agent yang sedang bekerja. `tgbot._dispatch` juga men-drop
setiap pesan yang tidak diawali `/`.

Sudah diverifikasi di mesin ini (claude 2.1.272): `--session-id <uuid>` di depan, lalu
`claude -p --resume <uuid> "<prompt>"` untuk melanjutkan.

Prasyarat: task-033 (cabang `callback_query` sudah ada di sana).

## Objective
Membalas notifikasi job di Telegram = melanjutkan percakapan dengan agent yang sama,
konteks utuh. Dan kendali penuh tanpa mengetik command.

## Scope
- `jobs.py` — `spawn()` membuat UUID sesi dan menyimpannya di meta;
  `followup(jid, text)` resume dan **append ke log yang sama**, naikkan `turns`,
  reset `finished`/`exit`
- `tgwatch` menyimpan `message_id -> job_id` di `watch.json` saat mengirim notifikasi selesai
- `tgbot._dispatch` — pesan yang merupakan *reply* ke notifikasi itu dan bukan command
  → `jobs.followup()`
- `/reply <job-id> <teks>` sebagai jalur eksplisit
- Pesan bebas tanpa slash (bukan reply) → role `lead`; `/chat off` mematikannya
- Handler boleh mengembalikan `str` **atau** `(str, markup)`; `_dispatch` menangani keduanya
- Tombol: `/kanban` → `▶ Run` `👁 Detail`; `/jobs` → `📄 Tail` `🛑 Stop` `💬 Reply`;
  `/task` → `▶ Run` `✅ Tick` `🌿 Worktree`; `/triggers` → `▶ Run now`

## Out of scope
- Mengubah 24 handler yang sudah ada — perubahan tipe kembalian harus kompatibel mundur

## Acceptance criteria
- [ ] `/ask lead ringkas status`, balas notifikasinya dengan instruksi lanjutan;
      `/tail` menunjukkan **satu** transkrip dengan dua giliran dan konteks terbawa
- [ ] `/kanban` lalu tap `▶ Run` memunculkan job di Command Center
- [ ] Pesan bebas tanpa slash sampai ke role `lead`; `/chat off` menghentikannya
- [ ] 24 handler lama tetap berfungsi tanpa disentuh
- [ ] Tombol dari chat tak berizin ditolak
- [ ] Suite lama tetap hijau

## Constraints
- `lead` adalah role perencanaan read-only — itu sebabnya pesan bebas aman diarahkan ke sana.
- `callback_data` Telegram maksimum 64 byte.
- Satu transkrip per job: Command Center tidak boleh perlu tahu soal follow-up.

## Required checks
- [ ] Unit test
- [ ] Integration/API test
- [ ] Lint
- [ ] Build
- [ ] Diff reviewed for secrets and stray files

## Progress
- [ ] jobs.followup + session id
- [ ] peta message_id -> job_id
- [ ] reply-to jadi follow-up
- [ ] pesan bebas -> lead, /chat
- [ ] markup di handler + tombol
- [ ] test

## Report
- Scope done:
- Files changed:
- Commands run + results:
- Tests:
- Risks:
- Not done / blocked:
- Suggested next task:
