# Harness Upgrade — Progress

> **Dokumen kanonik: [`docs/harness-upgrade.md`](../../docs/harness-upgrade.md).**
> Berkas ini adalah log kronologis per sesi — berguna untuk melihat urutan kejadian,
> bukan untuk mengetahui keadaan sekarang. Kalau keduanya berbeda, yang benar docs/.

**Plan:** `~/.claude-work/plans/cek-penerapan-agent-harness-generic-whale.md`
**Mulai:** 2026-09-15
**Target:** harness pindah ke VPS 72.61.209.201, engine Claude-only, agent jadi interaktif

Semua pekerjaan sejauh ini **lokal di Mac**. VPS belum disentuh sama sekali.

---

## Status per fase

**Dihentikan atas permintaan setelah Fase 1a selesai.** Lanjut nanti dari Fase 1b.

| Fase | Isi | Status |
|---|---|---|
| **1a** | **Engine Claude-only** → dikoreksi 16 Sep jadi **Claude didahulukan + fallback** | **selesai** |
| 1b | Supervisor abstraction (launchd ↔ systemd) | ditulis, **belum disambungkan** |
| **1c** | **Exit code yang benar** | **selesai** |
| 1d | Bot tidak membeku + level izin per-chat | belum |
| 2 | Bring-up VPS (sandbox saja) | belum — dimulai dengan survei read-only |
| 3 | Approval gate (agent bertanya lewat Telegram) | belum |
| 4 | Percakapan dua arah + tombol inline | belum |
| 5 | Pipeline antar-role | belum |
| 6 | Trigger berbasis event | belum |
| 7 | Artefak ke Telegram | belum |

---

## 2026-09-16 — Semua run Command Center gagal dalam 1 detik ✅

**Gejala.** Papan penuh merah: enam run gagal — task-030 dua kali, tiga run `lead` — masing-masing
mati dalam ~1 detik. Satu-satunya run `done` di papan adalah yang memakai `codex`. Pesannya
selalu persis sama:

```
Your organization has disabled Claude subscription access for Claude Code ·
Use an Anthropic API key instead, or ask your admin to enable access
```

**Akar masalah.** Fase 1a menjadikan `claude` satu-satunya engine yang dipilih harness,
hardcoded di dua tempat: `common.sh:engine_for_role` dan `jobs.py:_engine_for`. Yang tidak
diperiksa: bot dan dash dijalankan **launchd**, dan launchd tidak meneruskan
`CLAUDE_CONFIG_DIR`. Jadi `claude` yang dispawn tidak memakai konfigurasi yang dipakai sesi
interaktif, melainkan `~/.claude/.credentials.json` — akun tim `imam.nurokhi@nexoratech.co`,
yang org-nya sudah **mematikan** Claude Code. Terpasang, terautentikasi, dan tetap ditolak.

Direproduksi deterministik, bukan ditebak: `claude -p` berhasil dari sesi interaktif yang
punya `CLAUDE_CONFIG_DIR`, dan gagal dengan pesan itu persis begitu variabel-variabel tadi
dicopot — yaitu persis environment harness.

**Kenapa `ah doctor` tidak melihatnya.** `_claude_authed()` hanya memastikan kredensial
**ada**. Kredensial ada bukan berarti berhak memakainya. Jadi doctor melaporkan "claude
logged in" sepanjang waktu sementara setiap run ditolak. Itu sebabnya kegagalan ini tidak
terlihat sampai ia menatap operator dari dashboard.

**Yang menolong justru Fase 1c.** Sidecar `.rc` membuat keenam run muncul sebagai `failed`.
Tanpanya semuanya akan tampil ✅ dan masalahnya masih tersembunyi sampai sekarang.

**Perbaikan** — berkas baru `bin/lib/engine.py`, satu implementasi "engine mana, dan mana yang
berhenti diizinkan", supaya CLI dan dash tidak pernah berbeda pendapat:

- Penolakan dikenali dari keluaran engine, dicatat di `agents/.engine.json` (gitignored)
  dengan alasan + waktu, dan engine itu dilewati pada pemilihan berikutnya.
- Run yang **berhasil menghapus** catatan itu — akses yang dipulihkan admin langsung terpakai
  lagi, tanpa ada berkas yang harus diedit tangan.
- **Crash biasa tidak memblokir engine.** Hanya penolakan. Kalau tidak, satu prompt jelek
  bisa memindahkan seluruh run berikutnya ke vendor lain diam-diam.
- `AH_ENGINE_ORDER` (default `claude codex`) mengatur preferensi; `AH_ENGINE` tetap
  mengalahkan segalanya, karena operator tidak boleh dibantah oleh cache.
- `engine_exec` di `common.sh` mencoba ulang **sekali** dengan engine berikutnya kalau yang
  pertama ditolak, supaya run yang menemukan masalahnya sendiri tetap selesai.
- `jobs.refresh()` mencatat hasilnya dari ekor log job — tempat yang benar-benar melihat
  kegagalan.
- `ah engine` / `ah engine clear <name>` ditambahkan.
- `ah doctor` tidak lagi mengklaim "logged in": kredensial-ada dilaporkan terpisah dari
  engine-mana-yang-akan-jalan, dan penolakan yang tercatat ikut dicetak.

**Test** — `tests/test_engine_fallback.py`, termasuk kasus negatifnya: crash biasa tidak
boleh memblokir engine, state file yang korup tidak boleh membuat harness mogok, dan ketika
semua engine terblokir `pick()` tetap mengembalikan satu yang nyata — menolak memilih berarti
mengurung operator tanpa jalan pulang.

**Batasnya, jujur:** penolakan baru diketahui **setelah** ada run yang gagal. Tidak ada
pemeriksaan awal, karena memeriksa berarti satu putaran engine penuh di setiap run — biaya
yang dibayar selamanya untuk masalah yang muncul sekali-sekali. Jadi run pertama sesudah
akses dicabut akan tetap gagal; yang dijamin adalah run kedua tidak.

---

## Fase 1c — Exit code yang benar ✅

**Masalah.** `jobs.refresh()` hanya memeriksa `os.kill(pid, 0)`. Setiap job yang prosesnya
hilang ditandai `exit: "done"`, exit code-nya tidak pernah dibaca. Engine yang crash sampai
ke Telegram sebagai ✅.

**Bug kedua yang tersingkap saat menulis test.** Anak proses yang selesai jadi *zombie*
sampai ada yang me-reap. `os.kill(pid, 0)` pada zombie tetap sukses — jadi job yang sudah
selesai terlihat `running` selamanya di dash dan di `/status`. Ini bukan teori: ketiga test
pertama gantung karena persis ini.

**Bug ketiga.** Handle log (`fh`) tidak pernah ditutup parent setelah `Popen`. Di bot yang
hidup terus-menerus, bocor satu file descriptor per job.

**Perbaikan** — `bin/lib/jobs.py`:
- Engine dibungkus `/bin/sh -c '<cmd>; printf "%s" "$?" > <jid>.rc'` (quoting `shlex.quote`).
  Sidecar `.rc` di disk, bukan di memori, supaya tetap terbaca setelah supervisor me-restart bot.
- `refresh()` membaca `.rc`: `0` → `done`, selain itu → `failed` (+ simpan `code`).
  Wrapper mati tanpa menulis `.rc` (OOM, mesin mati) → `failed`, bukan sukses.
- `_reap()` membersihkan zombie sendiri sebelum memeriksa liveness.
- `stop()` tetap menang: `refresh()` keluar lebih awal kalau `finished` sudah diset.
- `_prune()` ikut menghapus `.rc`; `fh.close()` di `finally`.

**Test** — `tests/test_job_exit_status.py`, 4 kasus, semua hijau (1.3 s):
exit nonzero → `failed` + `code`; exit 0 → `done`; `stop()` → `stopped` bukan `failed`;
`listing()` (yang dibaca dash & Telegram) setuju dengan exit code.

Catatan: fake engine harus disisipkan ke `jobs.EXTRA_PATHS`, bukan ke `PATH` — `agent_env()`
menaruh `~/.local/bin` di depan PATH warisan, jadi engine asli akan menang.

**Belum dikerjakan di fase ini:** `tgwatch.detect()` masih memakai ikon lama, dan `dash.js`
belum punya state visual `failed`. Dikerjakan bersama 1d supaya UI dan notifikasi berubah sekali.

---

## Fase 1a — Engine Claude-only ✅

**Kenapa.** VPS jalan di team plan (`imam.nurokhi@nexoratech.co`); codex akun pribadi.
Sebelum ini `trigger.sh` memanggil `codex exec` hardcoded di dua tempat dan tidak pernah
bercabang berdasarkan engine — keempat trigger akan **mati total** begitu dipasang di VPS.

**Perbaikan.**
- `common.sh` — `engine_for_role()` dipindah ke sini (dulu di `run.sh`), sekarang selalu
  `claude` kecuali `AH_ENGINE` di-set. Dua helper baru, `engine_exec()` (unattended) dan
  `engine_interactive()` (attended), jadi **satu tempat** yang tahu cara meluncurkan engine.
  Sebelumnya pengetahuan itu tersebar di 5 titik.
- `run.sh` — `cmd_run` dan `cmd_recon` memakai helper; cabang `--skip-git-repo-check` hilang.
- `trigger.sh` — kedua `codex exec` jadi `engine_exec`, menghormati role trigger.
- `jobs.py` — `_engine_for()` default `claude`; `_model_for()` baru; `--model` diteruskan
  ke kedua engine; `model` disimpan di meta job.
- `doctor.sh` — `claude` + `git` jadi wajib, `codex` opsional. Cek auth nyata lewat
  `_claude_authed()`: `ANTHROPIC_API_KEY`, lalu Keychain di macOS, lalu `claudeAiOauth`
  di `~/.claude/.credentials.json` di Linux. Auth mati sekarang `fail`, bukan sekadar catatan.
- `.env.example` — `AH_ENGINE`, `AH_MODEL_IMPL`, `AH_MODEL_REVIEW`.

**Independensi reviewer.** Properti "reviewer pakai vendor berbeda" hilang bersama codex.
Penggantinya lebih lemah dan saya catat terang-terangan: pemisahan lewat **model**
(`AH_MODEL_REVIEW` vs `AH_MODEL_IMPL`) dan lewat **konteks** (reviewer menerima diff, bukan
sesi implementor). Bagian konteks belum dikerjakan — menyusul di Fase 5.

**Test.** `test_triggers.py` dan `test_trigger_memory.py` dulu nge-stub `codex()`; kalau
tidak diubah keduanya tetap hijau sambil produksi sudah pakai claude. Stub diganti `claude()`.

---

## Bug lain yang ditemukan dan diperbaiki

1. **Test gagal by-calendar.** `test_trigger_alerts.py` menanam `last_run="2026-09-14 07:01"`,
   jadi lulus hanya pada hari ia ditulis. Sejak 15 Sep alert "terlambat" bocor ke assertion
   soal alert kegagalan. Diganti `self.fresh()` yang menghitung waktu relatif.
   Diverifikasi gagal juga tanpa perubahan saya (`git stash`), jadi ini pre-existing.
2. **Zombie** — lihat Fase 1c.
3. **fd leak** — lihat Fase 1c.

---

## Fase 1b — ditulis, belum disambungkan ⚠️

`bin/lib/supervise.sh` sudah ada: `sv_platform`, `sv_install_daemon`, `sv_install_timer`,
`sv_uninstall`, `sv_is_managed`, `sv_pid`. macOS → plist launchd, Linux → systemd user unit
dengan `enable-linger` dan `Persistent=true` (supaya VPS yang mati jam 07:00 tetap menjalankan
standup saat hidup lagi). Satu parser jadwal, dua rendering — `_sv_schedule launchd|systemd`.

**Belum disentuh:** `bot.sh` dan `trigger.sh` masih menulis plist sendiri, `bin/ah` belum
me-source `supervise.sh`, dan belum ada test. Jadi file ini **belum dipakai siapa pun** —
tidak mengubah perilaku apa pun saat ini. Lanjutan dimulai dari sini.

---

## Keadaan sekarang

- 52/52 test hijau per 15 Sep; `tests/test_engine_fallback.py` menambah jumlahnya pada 16 Sep.
  Syntax check bersih untuk semua file shell yang disentuh.
- `ah doctor`, `ah task list`, `ah trigger list` normal — tapi sejak 16 Sep `ah doctor` hijau
  **bukan** jaminan run bisa jalan sampai barisnya berbunyi `runs will use: <engine>`.
- **Belum ada commit.** Semua di working tree.
- **Bot Telegram live (launchd) masih memakai kode lama** — proses Python sudah memuat
  `jobs.py` ke memori saat start. Perbaikan exit-code baru aktif setelah
  `ah bot uninstall && ah bot install`. Belum dilakukan.
- Perubahan perilaku harian di Mac: `ah run` dan trigger sekarang memakai claude.
  Balik ke codex: `AH_ENGINE=codex ah run <role> <task>`.

---

## Pembersihan papan + backlog fase (2026-09-15)

**Diarsipkan ke `archives/tasks/2026-09-15/`** — dipindah, tidak dihapus:
task-018, 022, 023, 024, 025, 026, 027, 028, 029.

**task-025 punya kerja yang belum di-commit.** Worktree-nya adalah worktree repo SUPPORT
di branch `agent/task-025`, dengan `M .github/workflows/deploy-dev.yml` (+8/-2) dan
`?? deploy/DEV_ENVIRONMENT.md` (43 baris), dipegang claim manual Benteng sejak 14 Sep.
Sebelum mengarsipkan task-nya, isinya disimpan:
- `task-025-uncommitted.patch` — `git diff`
- `task-025-DEV_ENVIRONMENT.md` — berkas yang belum ter-track
- `task-025-worktree-status.txt`

**Worktree dan claim-nya sengaja tidak disentuh.** Claim jadi yatim (task file sudah pindah)
tapi justru itu yang menahan agent lain mengambil alih worktree berisi kerja belum selesai.
Menghapus worktree adalah keputusan terpisah.

**Bug yang tersingkap saat mengarsipkan.** `reserve_task_id` mengambil nomor bebas pertama,
jadi setelah task-018 diarsipkan task berikutnya akan **dipakai ulang jadi task-018** —
mewarisi `agents/reports/task-018.*` dan nama worktree milik yang lama. Ditutup dengan
`_task_id_retired()`: id yang ada di `archives/` tidak pernah dibagikan lagi.
Diverifikasi: task baru berikutnya dapat 038, bukan 018.

**Backlog fase masuk TO DO** — task-030 s/d task-037, isinya diturunkan dari plan:

| Task | Fase | Role | Prasyarat |
|---|---|---|---|
| task-030 | 1b supervisor abstraction | devops | — |
| task-031 | 1d bot non-blocking + level izin | backend | — |
| task-032 | 2 bring-up VPS | devops | task-030 |
| task-033 | 3 approval gate | backend | task-031 |
| task-034 | 4 percakapan dua arah + tombol | backend | task-033 |
| task-035 | 5 pipeline antar-role | backend | task-034 |
| task-036 | 6 trigger berbasis event | devops | — |
| task-037 | 7 artefak ke Telegram | backend | — |

**Tidak ada yang dieksekusi.** Tidak ada worktree yang dibuat, tidak ada run yang dimulai.
`ah run` untuk role selain `lead`/`docs` menolak jalan tanpa worktree, jadi kedelapan task
ini diam sampai Anda menjalankannya sendiri. Trigger `standup` akan *menyebut* mereka di
laporan pagi — itu membaca, bukan mengerjakan.
