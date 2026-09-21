# Task: Analisa gap sisi SUPPORT untuk sinkronisasi dua arah NEXONE

- **ID:** task-007
- **Project:** SUPPORT (`projects/nexora/SUPPORT`)
- **Class:** nexora
- **Role:** qa
- **Worktree:** none (read-only analysis)
- **Base branch:** dev

## Background
Pasangan dari task-006. NEXONE dianalisa paralel oleh Kuda. Sisi SUPPORT membawa sinkronisasi tiket dua arah ke papan Backlog NEXONE (commit 5e50612) dan 176 test lolos, tetapi belum jelas bagian mana yang benar-benar dua arah dan mana yang masih satu arah.

## Objective
Laporan berbukti file:line tentang apa yang sudah bekerja di sisi SUPPORT, apa yang belum, dan apa yang perlu diselaraskan dengan NEXONE.

## Scope
- Baca lib/nexone/{client,config,mapping,sync}.ts dan test-nya
- Baca app/api/integrations/nexone/sync dan scripts/nexone-sync.mts
- Tentukan arah sinkronisasi yang benar-benar terimplementasi (SUPPORT->NEXONE, NEXONE->SUPPORT, atau keduanya)
- Catat kontrak/field yang harus cocok dengan sisi NEXONE

## Out of scope
- Mengubah kode, commit, push, atau menyentuh branch dev
- Menjalankan sinkronisasi sungguhan ke API NEXONE
- Membaca .env atau kredensial

## Acceptance criteria
- [x] Arah sinkronisasi yang benar-benar terimplementasi disebutkan dengan bukti file:line
- [x] Field/kontrak yang harus cocok dengan NEXONE didaftar
- [x] Bagian yang masih satu arah atau belum selesai disebutkan eksplisit
- [x] Laporan menyatakan 'Files modified: none'

## Constraints
READ-ONLY. Jangan jalankan npm run nexone:sync. Bukti file:line wajib. Bahasa Indonesia.

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
