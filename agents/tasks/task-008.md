# Task: Scope trigger health dan drift ke project yang tidak ON HOLD

- **ID:** task-008
- **Project:** AI-Workspace harness (`~/AI-Workspace`)
- **Class:** personal
- **Role:** devops
- **Worktree:** none (bekerja langsung di repo harness)
- **Base branch:** main

## Background
Prompt trigger health dan drift menyuruh agent memeriksa 'setiap project di projects/', padahal sekarang ada 9 repo cbqa/NEXFINANCE yang sedang ON HOLD dan tidak boleh disentuh.

## Objective
Trigger health dan drift hanya melihat project yang boleh dikerjakan, dan daftar itu dihitung dari state langsung sehingga tidak bisa basi.

## Scope
- state.workable_projects() dan penanda held per project
- Placeholder {PROJECTS} yang diekspansi saat trigger jalan
- Menjalankan kedua trigger sungguhan untuk membuktikan

## Out of scope
- Mengubah repo cbqa atau NEXFINANCE
- Mengubah jadwal trigger

## Acceptance criteria
- [x] Prompt health dan drift memakai {PROJECTS} yang diekspansi dari state langsung
- [x] Tidak ada repo ON HOLD yang bocor ke prompt (terverifikasi: 0 kebocoran)
- [x] Setiap path yang diemit benar-benar ada di disk
- [x] Kedua trigger dijalankan sungguhan dan menghasilkan laporan

## Constraints
Bash + Python stdlib. Daftar project dihitung saat runtime, bukan di-hardcode di prompt.

## Required checks
- [ ] Unit test
- [ ] Integration/API test
- [ ] Lint
- [ ] Build
- [x] Diff reviewed for secrets and stray files

## Report
- Scope done:
- Files changed:
- Commands run + results:
- Tests:
- Risks:
- Not done / blocked:
- Suggested next task:

## Progress
Diisi agar sesi lain bisa melanjutkan tanpa mengulang.

- [x] `state.is_held()` / `state.workable_projects()` ditambahkan di `bin/lib/state.py`
- [x] Field `held` ditambahkan ke tiap baris project
- [x] `bin/lib/scope.py` dibuat untuk mencetak daftar project yang boleh dikerjakan
- [x] `bin/lib/trigger.sh` mengekspansi `{PROJECTS}` saat runtime
- [x] Prompt `health` dan `drift` di `agents/triggers.json` ditulis ulang (Bahasa Indonesia, read-only, memakai {PROJECTS})
- [x] Kedua trigger dijalankan: laporan ada di `agents/reports/trigger-health.20260913-0917.log` dan `trigger-drift.20260913-0917.log`
- [x] BUG DITEMUKAN OLEH KEDUA AGENT: `scope.py` mengemit `projects/sandbox/sandbox` yang tidak ada. Penyebab: path disusun dari class+name, padahal repo yang berada langsung di `projects/<name>` punya class == name. Sudah diperbaiki dengan memakai `p["path"]`.
