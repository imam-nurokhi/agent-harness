# Harness Upgrade — VPS, Claude-only, Interaktif

Dokumen hidup. Ini sumber kebenaran untuk pekerjaan pindah-ke-VPS: apa yang sudah
berubah, apa yang belum, dan bagaimana melanjutkannya.

- **Dimulai:** 2026-09-15
- **Baseline commit:** `4fce3fb` (branch `main`)
- **Status kerja:** Fase 1a (dikoreksi 2026-09-16 jadi Claude-didahulukan-dengan-fallback) +
  1c selesai · Fase 1b ditulis belum disambungkan · sisanya backlog
- **Belum ada commit.** Semua perubahan masih di working tree.
- **Log kronologis per sesi:** `agents/reports/harness-upgrade-progress.md`

---

## 1. Kenapa ini dikerjakan

Tiga hal berubah sekaligus, dan urutannya penting.

**Rumah pindah ke VPS `72.61.209.201`.** Sekarang yang menjaga trigger tetap menyala justru
`com.ah.awake.plist` — `caffeinate -dimsu` yang memaksa Mac melek. Laptop harus standby supaya
standup jam 07:00 jalan. Itu yang mau dihapus.

**Engine jadi Claude saja.** Team plan `imam.nurokhi@nexoratech.co`; codex dilepas karena akun
pribadi. (Sejak 2026-09-16 ini dilunakkan: Claude didahulukan, tapi engine yang ditolak akunnya
dilewati — lihat koreksi di §4.)

**Harness dibuat interaktif.** Agent bisa bertanya, bisa dijawab, bisa dilanjutkan
percakapannya. Saat ini setiap run sekali jalan dan tidak punya kanal balik.

Karena semua supervisi sekarang launchd (macOS-only), membangun fitur di atas launchd lalu
memindahkannya ke Linux adalah pekerjaan dua kali. Maka portabilitas dikerjakan lebih dulu.

### Keputusan yang sudah diambil

| Pertanyaan | Keputusan |
|---|---|
| Topologi | **VPS satu-satunya rumah harness.** Mac jadi klien (SSH + tunnel ke dash). |
| Engine | **Claude didahulukan, bukan satu-satunya.** Urutan diatur `AH_ENGINE_ORDER` (default `claude codex`); engine yang ditolak akunnya dilewati sampai ada run yang berhasil lagi. `AH_ENGINE` selalu menang. |
| Repo di VPS | **`projects/sandbox` dulu**, sisanya menyusul setelah terbukti stabil. |
| Otoritas approval | Tap ✅ di Telegram **sah** sampai push `dev`/`staging`. **Tidak pernah** untuk `main`/`master`/`production`/`prod`, merge, deploy, migration produksi, kredensial. |

### Prinsip yang tidak dilanggar

- Stdlib-only — tidak ada dependency Python baru.
- `~/Documents` off-limits, ditegakkan di kode (`assert_allowed_path`), bukan sekadar ditulis.
- Dash loopback-only; diakses lewat `ssh -L 7777:127.0.0.1:7777`, tidak pernah dibuka ke internet.
- Telegram long-polling — tidak ada port masuk sama sekali.
- `.env` chmod 600 sebagai satu-satunya tempat rahasia.

---

## 2. Keadaan harness sekarang

Ini yang sudah ada sebelum pekerjaan ini dimulai, supaya jelas apa yang **tidak** perlu dibangun:

- CLI `ah` — task, worktree, run, trigger, bot, protect, doctor, dash
- Command Center `dash.py` di `:7777`, loopback + token per-sesi, bisa dispatch agent
- 7 role-bound agent dengan persona bidak catur, satu worktree per task, claim locking
- Trigger berjadwal lewat launchd, dengan memori `MEMO:` antar-run
- **Telegram bot `@KaraImamiBot` sudah live** (`com.ah.telegram`) — pairing kode sekali-pakai,
  24 command, kanban, notifikasi push, mode senyap

Kontrol Telegram **bukan** hal yang perlu dibangun. Yang hilang adalah arah baliknya.

---

## 3. Temuan yang menentukan urutan kerja

Enam hal ditemukan saat membaca kode. Empat sudah diperbaiki, dua jadi prasyarat VPS.

### A. Konflik token — bot akan terlihat rusak di VPS `belum ditangani`

Telegram hanya mengizinkan **satu proses long-poll per token**. Dua sumber konflik:

1. `~/Library/LaunchAgents/com.ah.telegram.plist` masih ter-load di Mac.
2. `~/Library/LaunchAgents/com.imamnurokhi.agent-kara.plist` (bot lama, di `~/Documents`)
   memuat **token yang sama persis** dengan `.env`, plaintext, mode 644 — dan crontab masih
   menjalankan `watchdog.sh` tiap 5 menit yang akan mencoba menghidupkannya. Saat ini selamat
   hanya karena agent-kara mati dengan exit 2.

**Tindakan:** rotasi token via @BotFather, token baru **hanya** di `.env` VPS, unload + hapus
kedua plist, cabut watchdog dari crontab. Prasyarat, bukan opsi. → task-032

### B. Kegagalan menyamar sebagai sukses `diperbaiki`

`jobs.refresh()` hanya memeriksa `os.kill(pid, 0)` dan menandai setiap job yang prosesnya
hilang sebagai `exit: "done"`. Exit code tidak pernah dibaca. Engine yang crash sampai ke
Telegram sebagai ✅. Di VPS tanpa pengawasan, ini fatal.

### C. Trigger selalu memakai codex `diperbaiki`

`trigger.sh` tidak pernah bercabang berdasarkan engine — ia memanggil `codex exec` hardcoded
di dua tempat. Dengan codex dilepas, **keempat trigger akan mati total** di VPS.

### D. Independensi reviewer hilang `sebagian`

"Reviewer pakai provider berbeda supaya tidak menilai PR-nya sendiri" bersandar pada adanya
dua vendor. Claude-only menghapusnya.

Penggantinya lebih lemah dan dicatat terang-terangan: pemisahan lewat **model**
(`AH_MODEL_REVIEW` vs `AH_MODEL_IMPL`) — sudah ada — dan lewat **konteks** (reviewer menerima
diff, bukan sesi implementor) — **belum**, menyusul di task-035.

### E. Bot membeku saat handler lambat `belum`

`tgbot._dispatch` memanggil handler sinkron di dalam poll loop. `/doctor` dengan timeout 60 s
menghentikan seluruh bot termasuk notifikasi. → task-031

### F. Bot mengabaikan `callback_query` `belum`

Hanya membaca `message`/`edited_message`, dan men-drop setiap pesan non-slash. Tanpa ini tidak
ada tombol inline dan tidak ada approval gate. → task-033

---

## 4. Yang sudah dikerjakan

Semua **lokal di Mac**. VPS belum disentuh.

### Fase 1c — Exit code yang benar ✅

Menulis test untuk ini menyingkap dua bug tambahan yang tidak terlihat dari membaca kode.

| Bug | Akibat |
|---|---|
| Exit code tidak pernah dibaca | Engine crash → ✅ di Telegram |
| Anak proses selesai jadi **zombie**; `os.kill(pid,0)` tetap sukses | Job selesai terlihat `running` **selamanya** di dash dan `/status` |
| Handle log tidak ditutup parent setelah `Popen` | Bocor 1 file descriptor per job di bot yang hidup terus |

**Perbaikan** — `bin/lib/jobs.py`:

- Engine dibungkus `/bin/sh -c '<cmd>; printf "%s" "$?" > <jid>.rc'` (quoting `shlex.quote`).
  Sidecar `.rc` di disk, bukan di memori, supaya tetap terbaca setelah supervisor me-restart bot.
- `refresh()` membaca `.rc`: `0` → `done`, selain itu → `failed` (+ simpan `code`).
  Wrapper mati tanpa menulis `.rc` (OOM, mesin mati) → `failed`, bukan sukses.
- `_reap()` membersihkan zombie sendiri sebelum memeriksa liveness.
- `stop()` tetap menang — `refresh()` keluar lebih awal kalau `finished` sudah diset.
- `_prune()` ikut menghapus `.rc`; `fh.close()` di `finally`.

**Test** — `tests/test_job_exit_status.py`, 4 kasus: exit nonzero → `failed` + `code`;
exit 0 → `done`; `stop()` → `stopped` bukan `failed`; `listing()` (yang dibaca dash dan
Telegram) setuju dengan exit code.

> Jebakan test: fake engine harus disisipkan ke `jobs.EXTRA_PATHS`, **bukan** ke `PATH` —
> `agent_env()` menaruh `~/.local/bin` di depan PATH warisan, jadi engine asli akan menang
> dan test benar-benar memanggil Claude.

### Fase 1a — Engine Claude-only ✅

- `common.sh` — `engine_for_role()` pindah ke sini dari `run.sh`, sekarang selalu `claude`
  kecuali `AH_ENGINE` di-set. Dua helper baru: `engine_exec()` (unattended) dan
  `engine_interactive()` (attended). **Satu tempat** yang tahu cara meluncurkan engine;
  sebelumnya tersebar di 5 titik.
- `run.sh` — `cmd_run` dan `cmd_recon` memakai helper; cabang `--skip-git-repo-check` hilang.
- `trigger.sh` — kedua `codex exec` jadi `engine_exec`, menghormati role trigger.
- `jobs.py` — `_engine_for()` default `claude`; `_model_for()` baru; `--model` diteruskan ke
  kedua engine; `model` disimpan di meta job.
- `doctor.sh` — `claude` + `git` wajib, `codex` opsional. Cek auth nyata lewat
  `_claude_authed()`: `ANTHROPIC_API_KEY` → Keychain (macOS) → `claudeAiOauth` di
  `~/.claude/.credentials.json` (Linux). Auth mati sekarang `fail`, bukan catatan.
- `.env.example` — `AH_ENGINE`, `AH_MODEL_IMPL`, `AH_MODEL_REVIEW`.

> `test_triggers.py` dan `test_trigger_memory.py` dulu nge-stub `codex()`. Kalau tidak diubah,
> keduanya tetap hijau sambil produksi sudah pakai claude. Stub diganti `claude()`.

#### Koreksi 2026-09-16 — "Claude saja" jadi "Claude didahulukan"

Fase 1a menyamakan **terpasang** dengan **boleh dipakai**. Keduanya berbeda. Bot dan dash
dijalankan launchd, dan launchd tidak meneruskan `CLAUDE_CONFIG_DIR`, jadi `claude` yang
dispawn membaca `~/.claude/.credentials.json` — akun tim `imam.nurokhi@nexoratech.co` yang
org-nya sudah mematikan Claude Code. Setiap run dari Command Center mati dalam ~1 detik
dengan `Your organization has disabled Claude subscription access for Claude Code`, dan
harness dengan tenang memilih engine yang sama lagi untuk job berikutnya. `ah doctor` tidak
menolong karena `_claude_authed()` hanya memeriksa kredensial **ada**; ada bukan berarti
berhak. Ceritanya lengkap di log kronologis, entri 2026-09-16.

Perbaikannya satu berkas baru, `bin/lib/engine.py` — satu-satunya implementasi "engine mana,
dan mana yang berhenti diizinkan", supaya CLI dan dash tidak pernah berbeda pendapat:

- Penolakan akun dikenali dari keluaran engine (pola `organization has disabled …`,
  `invalid api key`, `oauth token expired`, dan sejenisnya), lalu dicatat di
  `agents/.engine.json` (gitignored) beserta alasan dan waktunya. Pilihan berikutnya
  melewati engine itu. **Crash biasa tidak pernah memblokir engine** — kalau iya, satu
  prompt jelek bisa memindahkan semua run berikutnya ke vendor lain diam-diam.
- Run yang berhasil **menghapus** catatan itu. Jadi begitu admin menyalakan lagi aksesnya,
  harness pulih sendiri; tidak ada berkas yang harus diedit tangan.
- `AH_ENGINE_ORDER` (default `claude codex`) mengatur urutan preferensi. `AH_ENGINE` tetap
  mengalahkan segalanya, karena operator tidak boleh dibantah oleh cache. Kalau semua engine
  di urutan terblokir, `pick()` tetap mengembalikan satu yang nyata — menolak memilih berarti
  mengurung operator tanpa jalan pulang.
- `engine_exec()` di `common.sh` mencoba **sekali** dengan engine berikutnya kalau yang
  pertama ditolak, supaya run yang menemukan masalahnya sendiri tetap selesai.
- `jobs.py` mencatat hasilnya di `refresh()`, dari ekor log job — tempat yang benar-benar
  melihat kegagalan, bukan tempat yang menebaknya.
- `ah engine` menampilkan engine terpilih, urutannya, override, dan apa yang ditolak;
  `ah engine clear <name>` memakainya lagi setelah akses dibetulkan.
- `ah doctor` tidak lagi bilang "claude logged in". Ia melaporkan dua fakta terpisah:
  kredensial ada, dan engine mana yang sebenarnya akan jalan — plus penolakan yang tercatat.
  Kredensial hilang jadi peringatan, bukan `fail`; yang bikin `fail` sekarang adalah engine
  terpilih yang tidak terpasang.

**Test** — `tests/test_engine_fallback.py`: pengenalan penolakan (termasuk kasus negatif
crash biasa), pemilihan engine (preferensi, blokir, override, urutan, semua terblokir,
state korup), dan jalur job penuh (run yang ditolak memblokir engine-nya, run berikutnya
pindah ke codex, crash tidak memblokir, run sukses menghapus blokir).

**Batasnya jujur:** penolakan baru diketahui **setelah** ada run yang gagal. Tidak ada
pemeriksaan awal, karena memeriksa berarti satu putaran engine penuh di setiap run.

### Pembersihan papan + backlog

9 task diarsipkan ke `archives/tasks/2026-09-15/` — dipindah, tidak dihapus:
task-018, 022–029.

**task-025 punya kerja belum di-commit.** Worktree repo SUPPORT di branch `agent/task-025`:
`M .github/workflows/deploy-dev.yml` (+8/−2) dan `?? deploy/DEV_ENVIRONMENT.md` (43 baris),
dipegang claim manual Benteng sejak 14 Sep. Isinya disimpan sebelum diarsipkan
(`task-025-uncommitted.patch`, salinan `DEV_ENVIRONMENT.md`, status worktree).
**Worktree dan claim-nya sengaja tidak disentuh** — claim yatim itu justru yang menahan agent
lain mengambil alih worktree berisi kerja belum selesai. Menghapusnya keputusan terpisah.

### Bug lain yang diperbaiki

**Id task dipakai ulang setelah diarsipkan.** `reserve_task_id` mengambil nomor bebas pertama,
jadi setelah task-018 diarsipkan task berikutnya akan jadi task-018 lagi — mewarisi
`agents/reports/task-018.*` dan nama worktree milik yang lama. Ditutup dengan
`_task_id_retired()`: id yang ada di `archives/` tidak pernah dibagikan lagi.

**Test gagal by-calendar.** `test_trigger_alerts.py` menanam `last_run="2026-09-14 07:01"`,
jadi lulus hanya pada hari ia ditulis. Sejak 15 Sep alert "terlambat" bocor ke assertion soal
alert kegagalan. Diganti `self.fresh()` yang menghitung waktu relatif. Diverifikasi gagal juga
tanpa perubahan ini (`git stash`) — pre-existing, bukan regresi.

### Fase 1b — ditulis, belum disambungkan ⚠️

`bin/lib/supervise.sh` sudah ada: `sv_platform`, `sv_install_daemon`, `sv_install_timer`,
`sv_uninstall`, `sv_is_managed`, `sv_pid`. macOS → plist launchd; Linux → systemd user unit
dengan `enable-linger` dan `Persistent=true` (supaya VPS yang mati jam 07:00 tetap menjalankan
standup saat hidup lagi). Satu parser jadwal, dua rendering — `_sv_schedule launchd|systemd`.

**Belum ada yang me-source-nya.** `bot.sh` dan `trigger.sh` masih menulis plist sendiri.
File ini belum mengubah perilaku apa pun. → task-030

---

## 5. Backlog — apa yang belum, urut prasyarat

Kedelapan fase sudah jadi task di papan (`http://127.0.0.1:7777`, kolom TO DO).
Belum ada worktree yang dibuat. Sudah ada percobaan run pada task-030 lewat Command Center
pada 15 Sep, dan semuanya gagal — bukan karena task-nya, tapi karena engine ditolak; lihat
Koreksi 2026-09-16 di §4. Kedelapannya masih **diam** sampai dijalankan sendiri.

| Task | Fase | Role | Prasyarat | Inti |
|---|---|---|---|---|
| task-030 | 1b | devops | — | Sambungkan `supervise.sh` ke `bot.sh` + `trigger.sh`; `state.py` sadar-OS (`/proc/<pid>/cwd` di Linux) |
| task-031 | 1d | backend | — | Thread pool di `tgbot`; level izin `viewer\|operator\|owner`; ikon `failed` di Telegram + dash |
| task-032 | 2 | devops | 030 | Bring-up VPS: survei read-only dulu, rotasi token, user non-root, auth Claude, sandbox saja, hardening |
| task-033 | 3 | backend | 031 | Approval gate: `ah ask`, `gate.py`, `callback_query`, panel di dash, ubah `AGENTS.md` |
| task-034 | 4 | backend | 033 | `jobs.followup()` + resume sesi; balas notifikasi = lanjut ngobrol; tombol inline |
| task-035 | 5 | backend | 034 | Pipeline antar-role; sekalian menutup utang pemisahan konteks reviewer (temuan D) |
| task-036 | 6 | devops | — | Trigger `when`: `command`, `branch_behind`, `worktree_stale` |
| task-037 | 7 | backend | — | `send_document`: `/diff`, `/report`, `/log` + guard `.env`/kunci/20 MB |

Jalur kritis: **030 → 032** (VPS hidup), lalu **031 → 033 → 034** (interaktif).
036 dan 037 berdiri sendiri, bisa disisipkan kapan saja.

### Definisi selesai untuk task-032

Mac **dimatikan**, lalu dari HP `/status`, `/kanban`, dan `/ask lead ringkas status` berhasil,
dan trigger `standup` menyala esok paginya.

---

## 6. Apa yang berubah untuk pemakaian sehari-hari

**Engine default sekarang `claude`, bukan `codex`.** `ah run` dan keempat trigger memakai Claude.
Balik ke codex di Mac:

```bash
AH_ENGINE=codex ah run backend task-030
```

**Kalau Claude ditolak, harness pindah sendiri ke codex** dan mencatatnya. Lihat keadaannya,
atau pakai lagi setelah aksesnya dibetulkan:

```bash
ah engine                # terpilih, urutan, override, dan yang ditolak
ah engine clear claude   # boleh dipilih lagi
```

Di Mac, sesi interaktif punya `CLAUDE_CONFIG_DIR` yang benar sedangkan proses launchd tidak,
jadi `claude` bisa jalan di terminal Anda dan tetap ditolak di harness. `ah engine` melaporkan
apa yang dilihat harness, bukan apa yang dilihat shell Anda.

**Bot Telegram yang live masih memakai kode lama.** Proses Python (launchd) sudah memuat
`jobs.py` ke memori saat start. Perbaikan exit-code baru aktif setelah:

```bash
ah bot uninstall && ah bot install
```

Belum dilakukan — merestart layanan yang sedang jalan butuh persetujuan.

**Belum ada commit.** Semua di working tree, gampang dibatalkan.

---

## 7. Berkas yang disentuh

| Diubah | Isi |
|---|---|
| `bin/lib/jobs.py` | exit code, zombie, fd leak, engine, model |
| `bin/lib/common.sh` | `engine_for_role`, `engine_exec`, `engine_interactive`, `model_for_role`, `ARCHIVES_DIR`; sejak 16 Sep `engine_note_result`, retry sekali ke engine berikutnya, `cmd_engine` |
| `bin/ah` | perintah `ah engine` |
| `.gitignore` | `agents/.engine.json` |
| `bin/lib/run.sh` | pakai helper engine; cabang codex hilang |
| `bin/lib/trigger.sh` | dua `codex exec` → `engine_exec` |
| `bin/lib/doctor.sh` | `_claude_authed()`; claude+git wajib, codex opsional; sejak 16 Sep melaporkan kredensial dan engine-terpilih terpisah, plus penolakan yang tercatat |
| `bin/lib/task.sh` | `_task_id_retired()` — id arsip tidak dipakai ulang |
| `.env.example` | `AH_ENGINE`, `AH_MODEL_IMPL`, `AH_MODEL_REVIEW` |
| `tests/test_trigger_alerts.py` | `fresh()` menggantikan tanggal absolut |
| `tests/test_triggers.py`, `test_trigger_memory.py` | stub `codex()` → `claude()` |

| Baru | Isi |
|---|---|
| `bin/lib/supervise.sh` | abstraksi launchd ↔ systemd (**belum disambungkan**) |
| `bin/lib/engine.py` | pemilihan engine + catatan penolakan (`agents/.engine.json`) |
| `tests/test_job_exit_status.py` | 4 kasus exit status |
| `tests/test_engine_fallback.py` | pengenalan penolakan, pemilihan engine, fallback di jalur job |
| `archives/tasks/2026-09-15/` | 9 task + patch kerja task-025 |
| `agents/tasks/task-030..037.md` | backlog fase |

**Total:** 208 tambahan, 50 hapusan di 10 berkas, plus 2 berkas baru — angka per 15 Sep,
sebelum pekerjaan engine-health 16 Sep. Hitung ulang dengan `git diff --stat` kalau butuh
angka sekarang.

---

## 8. Verifikasi

```bash
cd ~/AI-Workspace
python3 -m unittest discover -s tests -p "test_*.py"   # 52 test, hijau
for f in bin/lib/*.sh; do bash -n "$f" || echo "SYNTAX: $f"; done
./bin/ah doctor
```

Keadaan per 15 Sep: **52/52 hijau**, syntax bersih. Sejak 16 Sep ada
`tests/test_engine_fallback.py`, jadi jumlahnya bertambah — jalankan sendiri untuk angka
sekarang.

`ah doctor` tidak lagi menjanjikan "claude logged in". Yang harus dibaca adalah baris
`runs will use: <engine>` dan daftar penolakan di bawahnya; itu yang benar-benar menentukan
apakah sebuah run bisa jalan.

Untuk task-030 dan seterusnya, test suite harus hijau di **macOS dan Linux** — itu inti
portabilitasnya.

---

## 9. Risiko yang dicatat

- **Kode di mesin pihak ketiga.** task-032 hanya membawa `sandbox`. Membawa repo cbqa/nexora
  adalah keputusan sadar pemilik, bukan langkah teknis yang diambil sendiri oleh agent.
- **Reviewer tidak lagi beda vendor** (temuan D). Kalau pemisahan model + konteks tidak cukup,
  alternatifnya menyisakan codex khusus `review`/`qa` di Mac dan menjalankan review manual.
- **Auth Claude bisa kedaluwarsa** di VPS tanpa ada yang melihat. Ditangani trigger `auth` +
  peringatan Telegram, tapi pemulihannya tetap manual lewat SSH. Fallback engine menahan
  dampaknya, tidak menghapusnya: penolakan baru diketahui setelah satu run gagal, dan di VPS
  yang hanya punya Claude tidak ada engine berikutnya untuk dipakai.
- **Proses yang dijalankan supervisor mewarisi environment supervisor, bukan environment
  Anda.** launchd tidak meneruskan `CLAUDE_CONFIG_DIR`; itu yang membuat seluruh run
  Command Center gagal pada 16 Sep sementara `claude` di terminal baik-baik saja. Setiap
  variabel yang dibutuhkan engine harus ditulis eksplisit di `.env` atau di unit-nya.
- **VPS satu titik kegagalan.** Bila mati, tidak ada fallback ke Mac karena bot hanya boleh satu.

## 10. Di luar cakupan

- Webhook Telegram — butuh tunnel + secret stabil; long-polling tidak butuh port masuk sama sekali.
- Mengganti stdlib dengan `python-telegram-bot`.
- Membuka dash ke internet.
- Mengizinkan agent menyentuh production atau `main`/`master` lewat jalur apa pun.
