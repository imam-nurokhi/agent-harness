# Task: Fase 1b: sambungkan supervise.sh ke bot dan trigger

- **ID:** task-030
- **Project:** AI-Workspace (`~/AI-Workspace`)
- **Class:** personal
- **Role:** devops
- **Worktree:** `~/AI-Workspace/worktrees/task-030`
- **Base branch:** main

## Background
Harness akan pindah ke VPS Linux (task-032). Saat ini semua supervisi memakai launchd:
`bot.sh:bot_install` dan `trigger.sh:trg_install` masing-masing menulis plist sendiri.
Di Linux keduanya tidak akan jalan sama sekali.

`bin/lib/supervise.sh` sudah ditulis (Fase 1b, 15 Sep) tapi **belum disambungkan** —
belum ada yang me-source-nya, jadi belum mengubah perilaku apa pun.

Plan lengkap: `~/.claude-work/plans/cek-penerapan-agent-harness-generic-whale.md`

## Objective
`ah bot install` dan `ah trigger install` menghasilkan supervisi yang benar di macOS
maupun Linux, lewat satu antarmuka.

## Scope
- `bin/ah` me-source `bin/lib/supervise.sh`
- `bot.sh` — `bot_install`/`bot_uninstall`/`_bot_managed_by_launchd` memakai
  `sv_install_daemon` / `sv_uninstall` / `sv_is_managed`
- `trigger.sh` — `trg_install`/`trg_uninstall` memakai `sv_install_timer` / `sv_uninstall`;
  hapus `_trg_calendar` yang sekarang duplikat dari `_sv_schedule`
- `state.py:_launchd_installed()` jadi sadar-OS, supaya tab triggers di Command Center
  dan `/triggers` di Telegram tidak berbohong di Linux
- `state.py:_live_engine_procs()` — di Linux baca `/proc/<pid>/cwd`, bukan `lsof`

## Out of scope
- Menyentuh VPS (itu task-032)
- Mengubah jadwal trigger yang ada

## Acceptance criteria
- [ ] `ah bot install` lalu `ah bot status` melaporkan keadaan sebenarnya di macOS
- [ ] `ah trigger install standup` menghasilkan plist yang identik isinya dengan sebelumnya
- [ ] `_sv_schedule` diuji untuk kedua target: "daily 07:00" dan "weekly Mon 09:00"
- [ ] `state.triggers()` melaporkan `installed` dengan benar tanpa memanggil launchctl di Linux
- [ ] Test baru `tests/test_supervise.py` hijau
- [ ] Seluruh suite lama tetap hijau

## Constraints
- Stdlib-only, tanpa dependency Python baru.
- Label tetap reverse-DNS (`com.ah.telegram`, `com.ah.trigger.<id>`) di kedua platform.
- Satu parser jadwal, dua rendering — jadwal tidak boleh berarti dua waktu berbeda
  tergantung mesin yang memasang.

## Required checks
- [ ] Unit test
- [ ] Integration/API test
- [ ] Lint
- [ ] Build
- [ ] Diff reviewed for secrets and stray files

## Progress
- [ ] `supervise.sh` di-source dari `bin/ah`
- [ ] `bot.sh` dialihkan
- [ ] `trigger.sh` dialihkan, `_trg_calendar` dihapus
- [ ] `state.py` sadar-OS
- [ ] test

## Report
- Scope done:
- Files changed:
- Commands run + results:
- Tests:
- Risks:
- Not done / blocked:
- Suggested next task:
