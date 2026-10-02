# Task: SUPPORT: scheduler agar sinkronisasi benar-benar otomatis

- **ID:** task-019
- **Project:** SUPPORT (`~/AI-Workspace/projects/nexora/SUPPORT`)
- **Class:** nexora
- **Role:** devops
- **Worktree:** `~/AI-Workspace/worktrees/task-019`
- **Base branch:** dev

## Background
Kontrak lengkap: `agents/reports/nexone-support-slack-contract.md` (item S1).

Pembuatan ticket sudah memasukkan baris ke outbox (`app/api/tickets/route.ts`), tetapi
tidak ada apa pun yang mengurasnya. Satu-satunya pemicu adalah admin menekan POST manual
(`app/api/integrations/nexone/sync/route.ts`) atau cron eksternal ke
`scripts/nexone-sync.mts`. Tanpa ini, kata "otomatis" dalam skenario tidak pernah benar.

## Objective
Ticket yang dibuat di SUPPORT muncul di papan NEXONE tanpa ada manusia yang menekan apa pun.

## Scope
- Kuras outbox segera setelah ticket dibuat, tanpa memblokir response ke pengguna dan tanpa
  membuat request gagal kalau NEXONE sedang mati.
- Pasang penjadwalan berkala sebagai jaring pengaman untuk baris yang gagal terkirim.
  Pilih mekanisme yang cocok dengan cara SUPPORT di-deploy — periksa dulu bagaimana
  aplikasi ini dijalankan di server sebelum memilih, dan jelaskan pilihannya di Report.
- Pastikan dua pemicu yang berjalan bersamaan tidak memproses baris outbox yang sama dua kali.
- Beri cara melihat kesehatan sinkronisasi: berapa baris tertunda, kapan pass terakhir
  berhasil, apa kegagalan terakhirnya.

## Out of scope
- Mengubah isi apa yang disinkronkan (task-018 dan task-020).
- Memasang cron di server production.

## Acceptance criteria
- [x] Ticket baru terkirim ke NEXONE tanpa intervensi manual, dibuktikan test
- [x] NEXONE yang sedang mati tidak membuat pembuatan ticket gagal; baris tetap di outbox dan terkirim di percobaan berikutnya
- [x] Dua pass yang tumpang tindih tidak mengirim ticket yang sama dua kali, dibuktikan test
- [x] Kesehatan sinkronisasi bisa dilihat tanpa membaca log mentah
- [x] Cara menjalankan penjadwalan terdokumentasi di repo, termasuk yang masih harus dipasang manusia di server
- [x] `npm test`, `npm run lint`, `npm run build` hijau dengan output dikutip

## Constraints
Baca `AGENTS.md`/README SUPPORT lebih dulu, terutama bagian deployment. Jangan membaca
`.env`, jangan menyentuh server atau cron production — task ini hanya menyiapkan mekanisme
dan dokumentasinya. Bekerja hanya di worktree ini. Jangan commit, jangan push.

## Required checks
- [x] Unit test
- [x] Integration/API test
- [x] Lint
- [x] Build
- [x] Diff reviewed for secrets and stray files

## Progress
- [x] Pastikan cara SUPPORT dijalankan di server
- [x] Drain segera setelah ticket dibuat
- [x] Penjadwalan berkala + anti-tumpang-tindih
- [x] Permukaan kesehatan sinkronisasi + dokumentasi

## Report
- Scope done:
- Files changed:
- Commands run + results:
- Tests:
- Risks:
- Not done / blocked:
- Suggested next task:
