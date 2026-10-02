# Task: Fase 3: approval gate - agent bertanya lewat Telegram

- **ID:** task-033
- **Project:** AI-Workspace (`~/AI-Workspace`)
- **Class:** personal
- **Role:** backend
- **Worktree:** `~/AI-Workspace/worktrees/task-033`
- **Base branch:** main

## Background
`agents/roles/_common.md` mewajibkan "never run migrations, deploys, git push without
explicit human approval" — tapi trigger jam 07:00 tidak punya kanal untuk meminta izin itu.
Akibatnya semua trigger dipaksa read-only. Ini lubang terbesar di harness.

Keputusan kebijakan yang sudah diambil: **tap ✅ di Telegram sah sebagai persetujuan manusia
sampai push ke dev/staging**, tidak pernah untuk production/main.

Prasyarat: task-031 (level izin) — yang boleh menyetujui push harus lebih sempit daripada
yang boleh melihat papan.

## Objective
Agent yang menyentuh batas berhenti, bertanya lewat Telegram, dan lanjut setelah dijawab.

## Scope
- `bin/lib/gate.py` — `ask(question, options, kind, job_id, timeout)` menulis
  `agents/.gates/<gid>.json` lalu polling; `answer(gid, choice, by_chat)` mencatat keputusan
  **dan siapa yang memutuskan**; `pending()` untuk tgwatch dan dash
- `bin/lib/gate.sh` + `bin/ah` — `ah ask "<pertanyaan>" --kind push --options ya,tidak --timeout 900`
  stdout = jawaban; exit 0 dijawab, exit 2 timeout
- `tgcore.py` — `send(..., markup=)`, `kb(rows)`, `answer_callback()`, `edit_text()`
- `tgbot.py` — cabang `callback_query`, parse `gate:<gid>:<choice>` (≤64 byte), cek level izin,
  lalu `editMessageText` supaya tombol hilang dan terlihat siapa memutuskan apa
- `tgwatch.py` — `_gate_events(w)` di `detect()`, di-mirror di `prime()`
- `dash.py`/`dash.js` — `gates` di `/api/state`, panel gate, `POST /api/gate/answer`
- `AGENTS.md` + `_common.md` — bagian "Meminta izin" dengan contoh perintah persis

## Out of scope
- Mengendurkan trigger jadi read-write (langkah terpisah setelah gate terbukti)

## Acceptance criteria
- [ ] `ah ask "test" --kind question --options ya,tidak` memunculkan tombol di HP; tap Ya
      membuat perintah mengembalikan `ya` dan exit 0
- [ ] `--kind push` dari chat level `viewer` **ditolak**
- [ ] `--kind deploy` **ditolak saat gate dibuat**, bukan saat dijawab
- [ ] Timeout mengembalikan exit 2, dan agent berhenti melapor blocked — tidak lanjut
- [ ] Gate yang sama bisa dijawab dari Command Center, hasilnya sama
- [ ] Jawaban tercatat lengkap dengan chat id penjawab dan waktunya
- [ ] Callback dari chat tak berizin ditolak dan dicatat

## Constraints
- Daftar-tolak dikunci di `gate.py`, dievaluasi **saat pembuatan** — supaya tidak bergantung
  pada agent yang jujur. Terlarang: push ke main/master/production/prod, merge, deploy,
  migration produksi, perubahan kredensial.
- `ah protect` (pre-push hook) tetap lapisan kedua, tidak digantikan.
- Protokol berbasis file: tidak butuh port terbuka, bekerja untuk engine apa pun.

## Required checks
- [ ] Unit test
- [ ] Integration/API test
- [ ] Lint
- [ ] Build
- [ ] Diff reviewed for secrets and stray files

## Progress
- [ ] gate.py + gate.sh + ah ask
- [ ] tgcore markup/callback
- [ ] tgbot callback_query
- [ ] tgwatch gate events
- [ ] dash panel
- [ ] AGENTS.md + _common.md
- [ ] test

## Report
- Scope done:
- Files changed:
- Commands run + results:
- Tests:
- Risks:
- Not done / blocked:
- Suggested next task:
