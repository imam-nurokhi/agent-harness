# Task: Fase 5: pipeline antar-role

- **ID:** task-035
- **Project:** AI-Workspace (`~/AI-Workspace`)
- **Class:** personal
- **Role:** backend
- **Worktree:** `~/AI-Workspace/worktrees/task-035`
- **Base branch:** main

## Background
Satu run = satu role. Menyambung backend → review → qa harus dilakukan tangan, satu per satu,
dan itu berarti pekerjaan berhenti setiap kali tidak ada yang memperhatikan.

Task ini juga menutup utang dari Fase 1a: sejak codex dilepas, "reviewer bukan implementor"
tidak lagi dijamin vendor. Pemisahan lewat model sudah ada (`AH_MODEL_REVIEW`); **pemisahan
lewat konteks belum** — dan chain adalah tempat paling mungkin konteks itu bocor.

## Objective
Job yang sukses memicu role berikutnya otomatis, dengan reviewer yang tidak pernah melihat
sesi implementor.

## Scope
- Task file dapat field opsional `- **Pipeline:** backend, review, qa`
- `jobs.spawn(..., chain=[...])` menyimpannya di meta
- `bin/lib/pipeline.py` — `tick()`: job selesai `exit == done` dengan sisa chain → spawn role
  berikutnya dengan blok `## Report` sebelumnya sebagai konteks
- Job `failed` menghentikan chain dan mengirim satu notifikasi
- `tick()` dipanggil dari loop tgbot dan dari `GET /api/state`
- `/pipeline task-007 backend review qa` di Telegram
- Role `review`/`qa` menerima **diff + acceptance criteria saja**, bukan transkrip implementor

## Out of scope
- Percabangan bersyarat dalam chain — urutan linier saja

## Acceptance criteria
- [ ] Task sandbox dengan `Pipeline: backend, review`: `review` menyala sendiri setelah
      `backend` sukses
- [ ] `review` **tidak** menyala saat `backend` gagal, dan satu notifikasi dikirim
- [ ] Prompt `review` berisi diff dan acceptance criteria, dan **tidak** berisi transkrip
      atau session id implementor — dibuktikan dengan assertion di test, bukan inspeksi mata
- [ ] `review` memakai `AH_MODEL_REVIEW` bila di-set
- [ ] Chain yang sudah habis tidak memicu apa pun
- [ ] Suite lama tetap hijau

## Constraints
- Pipeline maju selama bot atau dash hidup — didokumentasikan, bukan disembunyikan.
- `tick()` tidak boleh punya efek samping saat dipanggil dari pembacaan state yang gagal
  separuh jalan (idempoten per job).

## Required checks
- [ ] Unit test
- [ ] Integration/API test
- [ ] Lint
- [ ] Build
- [ ] Diff reviewed for secrets and stray files

## Progress
- [ ] field Pipeline + chain di meta
- [ ] pipeline.tick
- [ ] pemisahan konteks reviewer
- [ ] /pipeline
- [ ] test

## Report
- Scope done:
- Files changed:
- Commands run + results:
- Tests:
- Risks:
- Not done / blocked:
- Suggested next task:
