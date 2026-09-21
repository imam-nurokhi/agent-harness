# Task: Telegram sebagai permukaan manajemen task penuh

- **ID:** task-004
- **Project:** AI-Workspace harness (`~/AI-Workspace`)
- **Class:** personal
- **Role:** backend
- **Worktree:** none (koordinasi; implementasi di repo utama)
- **Base branch:** main

## Background
Imam ingin mengelola harness sepenuhnya dari HP. Saat ini Telegram bisa melihat dan menjalankan, tetapi belum bisa membuat atau mengubah task. Semua update penting harus sampai ke Telegram tanpa menjadi spam.

## Objective
Telegram menjadi permukaan manajemen task penuh: buat, tetapkan, pantau, dan tutup task, dengan notifikasi yang informatif tetapi tidak berisik.

## Scope
- Perintah pembuatan dan pengubahan task dari Telegram
- Notifikasi peristiwa penting saja, dengan ringkasan berkala
- Kontrol kebisingan yang bisa diatur pengguna

## Out of scope
- Mengubah kode project di luar harness
- Mengakses ~/Documents
- Mengirim notifikasi untuk polling rutin atau perubahan sepele

## Acceptance criteria
- [x] Task baru bisa dibuat dari Telegram dan langsung muncul di `ah task list`
- [x] Role dan worktree sebuah task bisa ditetapkan dari Telegram
- [x] Acceptance criteria bisa dicentang dari Telegram
- [x] Notifikasi dikirim untuk peristiwa penting saja, bukan untuk setiap perubahan
- [x] Pengguna bisa mematikan/menyalakan notifikasi dan meminta ringkasan sesuai permintaan
- [x] Tidak ada perintah yang bisa dijalankan chat yang belum dipasangkan

## Constraints
Hanya chat yang sudah dipasangkan yang boleh mengubah apa pun. Python stdlib saja. Pesan harus ringkas: detail panjang diambil lewat perintah, bukan didorong otomatis.

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
