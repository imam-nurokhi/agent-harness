# Task: Branch protection: blokir push ke main/production

- **ID:** task-009
- **Project:** AI-Workspace harness + repo yang di-onboard
- **Class:** personal
- **Role:** devops
- **Worktree:** none
- **Base branch:** main

## Background
Imam mengizinkan agent push ke dev/staging, tetapi push ke main/production tidak boleh terjadi sama sekali. Aturan tertulis saja tidak cukup; harus ditegakkan oleh mesin.

## Objective
Push ke main/master/production/prod ditolak oleh git hook di setiap repo yang boleh dikerjakan, sementara push ke dev/staging tetap jalan.

## Scope
- Hook pre-push di NEXONE dan SUPPORT
- Subcommand `ah protect install|status|uninstall`
- Bukti exit code: non-zero untuk main, zero untuk dev

## Out of scope
- Push sungguhan ke remote mana pun
- Commit di dalam NEXONE atau SUPPORT
- Menyentuh repo yang sedang ON HOLD

## Acceptance criteria
- [x] Push ke main/master/production/prod ditolak oleh hook, dibuktikan dengan exit code
- [x] Push ke dev dan staging tidak terhalang
- [x] `ah protect status` menampilkan status terpasang per project
- [x] Hook yang sudah ada tidak ditimpa diam-diam

## Constraints
Harus bekerja juga saat git dipanggil dari worktree. Jangan menimpa hook pre-push yang sudah ada; laporkan saja kalau ada.

## Required checks
- [x] Unit test
- [x] Integration/API test
- [x] Lint
- [x] Build
- [x] Diff reviewed for secrets and stray files

## Progress
<Update this as you work. Another agent in another session must be able to read
this and continue without redoing anything. One line per step, tick as you go.>

- [x] Sub-agent menulis bin/lib/protect.sh dan mendaftarkannya di bin/ah
- [x] Hook terpasang di NEXONE dan SUPPORT
- [x] Bukti: hook menolak ref main (exit != 0) dan mengizinkan dev (exit 0)
- [x] bash -n lolos untuk tiap file shell yang disentuh

## Report
- Scope done:
- Files changed:
- Commands run + results:
- Tests:
- Risks:
- Not done / blocked:
- Suggested next task:
