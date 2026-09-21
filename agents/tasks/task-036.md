# Task: Fase 6: trigger berbasis event

- **ID:** task-036
- **Project:** AI-Workspace (`~/AI-Workspace`)
- **Class:** personal
- **Role:** devops
- **Worktree:** `~/AI-Workspace/worktrees/task-036`
- **Base branch:** main

## Background
Trigger sekarang hanya berbasis waktu (launchd/systemd calendar). Hal-hal yang sebenarnya
layak memicu kerja — branch tertinggal dari remote, worktree kotor berhari-hari — baru
ketahuan saat jadwal mingguan kebetulan lewat.

## Objective
Trigger bisa menyala karena keadaan berubah, bukan hanya karena jam berganti.

## Scope
- `agents/triggers.json` dapat blok opsional:
  `"when": { "type": "command", "run": "...", "min_interval": "2h" }`
- Tipe `command` (exit 0 = kondisi terpenuhi), plus bawaan `branch_behind` dan `worktree_stale`
  yang memakai `state.worktrees()` / `state._git()` yang sudah ada
- `bin/lib/trigwatch.py` — dievaluasi dari loop tgbot, menghormati `min_interval`,
  mencatat penyalaan lewat `trigmem.py` yang sudah ada

## Out of scope
- Webhook masuk dari GitHub — harness sengaja tidak punya port masuk
- Mengganti trigger berjadwal; `when` adalah tambahan

## Acceptance criteria
- [ ] Trigger uji dengan `when.type=command` yang pasti exit 0 menyala **sekali**
- [ ] Penyalaan kedua ditahan sampai `min_interval` lewat
- [ ] `ah trigger memo <id>` dan deteksi "terlambat" tetap bekerja tanpa perubahan
- [ ] Trigger tanpa blok `when` berperilaku persis seperti sebelumnya
- [ ] `branch_behind` benar untuk repo yang tertinggal dan untuk yang tidak
- [ ] Test baru hijau; suite lama tetap hijau

## Constraints
- `when.run` adalah perintah shell yang ditulis manusia di `triggers.json` — jalankan dengan
  cwd workspace, timeout, dan hasilkan log; jangan pernah berasal dari input agent.
- Evaluasi harus murah: jalan tiap poll bot (25 detik).

## Required checks
- [ ] Unit test
- [ ] Integration/API test
- [ ] Lint
- [ ] Build
- [ ] Diff reviewed for secrets and stray files

## Progress
- [ ] skema when
- [ ] trigwatch.py
- [ ] bawaan branch_behind + worktree_stale
- [ ] test

## Report
- Scope done:
- Files changed:
- Commands run + results:
- Tests:
- Risks:
- Not done / blocked:
- Suggested next task:
