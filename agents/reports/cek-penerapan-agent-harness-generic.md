# Agent Harness — Pindah ke VPS, Claude-only, Interaktif

## Context

Harness di `~/AI-Workspace` sudah matang: CLI `ah`, Command Center (`dash.py`, :7777, loopback +
token per-sesi), 7 role-bound agent, worktree isolation, claim locking, trigger launchd dengan
memori `MEMO:`, dan **Telegram bot `@KaraImamiBot` yang sudah live** (`com.ah.telegram`, PID aktif)
dengan pairing, 24 command, kanban, dan push notifikasi. Jadi ini bukan membangun kontrol Telegram —
itu sudah ada.

Tiga hal berubah sekaligus, dan urutannya penting:

1. **Rumah pindah ke VPS 72.61.209.201** supaya laptop tidak perlu standby. Saat ini yang menjaga
   trigger tetap menyala justru `com.ah.awake.plist` — `caffeinate -dimsu` yang memaksa Mac melek.
2. **Engine jadi Claude saja** (team plan `imam.nurokhi@nexoratech.co`); codex dilepas karena akun
   pribadi.
3. **Harness dibuat interaktif**: agent bisa bertanya, bisa dijawab, bisa dilanjutkan percakapannya.

Karena semua supervisi sekarang launchd (macOS-only), membangun 6 fase fitur di atas launchd lalu
memindahkannya ke Linux adalah pekerjaan dua kali. Maka portabilitas dikerjakan **lebih dulu**.

---

## Temuan yang harus ditangani sebelum apa pun

**A. Konflik token — bot akan terlihat rusak di VPS.** Telegram hanya mengizinkan satu proses
long-poll per token. Dua sumber konflik:
- `~/Library/LaunchAgents/com.ah.telegram.plist` masih ter-load di Mac. Kalau bot menyala di VPS
  tanpa ini di-unload, keduanya akan saling mencuri update.
- `~/Library/LaunchAgents/com.imamnurokhi.agent-kara.plist` (bot lama, `~/Documents`) memuat
  **token yang sama persis** dengan `~/AI-Workspace/.env`, dalam plaintext, mode 644 — dan
  crontab masih menjalankan `watchdog.sh` setiap 5 menit yang akan mencoba menghidupkannya.
  Saat ini selamat hanya karena agent-kara mati dengan exit 2.

**Tindakan:** rotasi token via @BotFather, taruh token baru **hanya** di `.env` VPS, unload +
hapus kedua plist di Mac, dan cabut baris watchdog agent-kara dari crontab. Ini prasyarat, bukan
opsi — dilakukan di awal Fase 2.

**B. Kegagalan menyamar sebagai sukses.** `jobs.refresh()` (`bin/lib/jobs.py:192-201`) menandai
setiap job yang prosesnya hilang sebagai `exit: "done"`, tanpa pernah membaca exit code.
`tgwatch.detect()` lalu mengirim ✅ untuk engine yang crash. Di VPS tanpa pengawasan, ini fatal.

**C. Trigger selalu memakai codex.** `trigger.sh` tidak pernah bercabang berdasarkan engine
(tidak seperti `ah run`) — ia memanggil `codex exec` secara hardcoded di dua tempat
(`trigger.sh:115-126` dan `134-139`). Dengan codex dilepas, **keempat trigger akan mati total**
di VPS sampai ini diganti.

**D. Independensi reviewer hilang.** Properti desain "reviewer pakai provider berbeda supaya tidak
menilai PR-nya sendiri" (`run.sh:6-12`, `jobs.py:40-47`) bersandar pada adanya dua vendor.
Claude-only menghapusnya. Mitigasi di Fase 1: pisahkan lewat **model + sesi bersih**, bukan vendor —
`review`/`qa` memakai model penalaran terkuat dalam sesi baru tanpa transkrip implementor, hanya
diberi diff dan acceptance criteria. Lebih lemah dari sebelumnya; saya sebutkan terang-terangan
supaya tidak disangka setara.

**E. Bot membeku saat handler lambat.** `tgbot._dispatch` memanggil handler sinkron di dalam poll
loop; `/doctor` dengan timeout 60 s menghentikan seluruh bot termasuk notifikasi.

**F. Bot mengabaikan `callback_query`** (`tgbot.py:107-144` hanya membaca `message`/`edited_message`)
dan men-drop setiap pesan non-slash.

**Prinsip yang dipertahankan:** stdlib-only (tanpa dependency Python baru), guard `~/Documents`,
dash loopback-only (diakses lewat SSH tunnel, tidak pernah dibuka ke internet), long-polling
(tanpa inbound port), `.env` chmod 600 sebagai satu-satunya tempat rahasia.

---

## Fase 1 — Portabilitas, Claude-only, keandalan

Dikerjakan dan diuji di Mac dulu, tapi ditulis portabel sejak awal.

### 1a. Engine: Claude saja
- `bin/lib/run.sh:6-12` dan `bin/lib/jobs.py:40-47` — `engine_for_role()` mengembalikan `claude`
  untuk semua role. `AH_ENGINE` tetap dihormati supaya codex bisa dipakai lagi di Mac bila perlu.
- Hapus percabangan khusus codex: `--skip-git-repo-check` dan `codex exec` di `run.sh:88-103`,
  `jobs.py:155-163`, `trigger.sh:115-139`, `run.sh:130` (`cmd_recon`).
- **Independensi reviewer** diganti: `AH_MODEL_REVIEW` / `AH_MODEL_IMPL` di `.env`, diteruskan
  sebagai `claude --model`. Kontrak `review`/`qa` diubah agar mereka menerima **diff + acceptance
  criteria saja**, bukan transkrip implementor — pemisahan lewat konteks, bukan lewat vendor.
- `ah doctor` (`bin/lib/doctor.sh`) memeriksa auth claude dan memberi peringatan jelas saat mati.

### 1b. Supervisor abstraction (launchd ↔ systemd)
- **`bin/lib/supervise.sh`** (baru) — satu antarmuka: `sv_install <label> <argv...>`,
  `sv_uninstall`, `sv_is_managed`, `sv_status`. Mendeteksi OS: macOS → plist launchd
  (persis yang sekarang), Linux → systemd **user unit** (`systemctl --user`, dengan
  `loginctl enable-linger` supaya hidup tanpa sesi login).
- `bot.sh:133-172` (`bot_install`/`bot_uninstall`) dan `trigger.sh:189-239`
  (`trg_install`/`trg_uninstall`) berhenti menulis plist sendiri dan memanggil `supervise.sh`.
- Penjadwalan: `_trg_calendar` (`trigger.sh:171-187`) sudah menerjemahkan `"weekly Mon 09:00"`
  → `StartCalendarInterval`. Tambahkan cabang kedua yang menerjemahkan format yang sama →
  `OnCalendar=` systemd timer. Satu parser, dua target.
- `state._launchd_installed()` (`state.py:394`) jadi `_supervisor_installed()` yang sadar OS,
  supaya tab **triggers** di Command Center dan `/triggers` di Telegram tetap jujur.
- `state._live_engine_procs()` (`state.py:282-308`) memakai `lsof -a -p <pid> -d cwd -Fn`.
  Di Linux baca `/proc/<pid>/cwd` — lebih cepat dan tanpa dependency. Tanpa ini, tab **floor**
  akan menunjukkan semua agent idle di VPS.

### 1c. Exit code yang benar
- `jobs.spawn()` membungkus perintah dengan `/bin/sh -c '<cmd>; printf "%s" "$?" > <jid>.rc'`
  (quoting `shlex.quote`). Sidecar `.rc` bertahan walau parent mati — penting karena supervisor
  me-restart bot.
- `refresh()` membaca `.rc`: `0` → `done`, selain itu → `failed` (+ simpan exit code).
  `stopped` tetap menang karena diset eksplisit oleh `stop()`.
- `tgwatch.detect()` memakai `🛑` + exit code untuk `failed`, dan `_outcome()` memprioritaskan
  baris `Not done / blocked`. `dash.js` mendapat state visual `failed`.

### 1d. Bot tidak lagi membeku, dan punya level izin
- `tgbot.py` — eksekusi handler pindah ke `concurrent.futures.ThreadPoolExecutor(4)`;
  `_notify()` jalan di thread sendiri dengan cadence sendiri.
- `agents/.telegram/config.json` dapat `roles: {chat_id: level}`, level
  `viewer | operator | owner`. Chat yang sudah ter-pair diperlakukan `owner` (kompatibel mundur).
  Handler diberi tag level minimum; `_dispatch` menolak sebelum memanggil.
  - `viewer` — status, kanban, tasks, jobs, tail, digest, triggers, doctor
  - `operator` — + run, ask, trigger, stop, task mutation
  - `owner` — + approval push/commit, `/pair`, ubah level chat lain

---

## Fase 2 — Bring-up VPS (sandbox saja)

**Langkah pertama adalah survei, bukan instalasi.** SSH ke `72.61.209.201`, catat: distro, RAM/disk,
apakah `node`, `python3`, `git`, `claude` sudah ada, dan apakah `systemctl --user` tersedia.
Hasil survei ditulis ke `agents/reports/vps-recon.md` sebelum ada yang diubah.

1. **Rotasi token & bersihkan Mac** (temuan A) — @BotFather rotate; unload+hapus
   `com.ah.telegram.plist` dan `com.imamnurokhi.agent-kara.plist`; cabut baris watchdog agent-kara
   dari crontab; `com.ah.awake.plist` (caffeinate) di-unload karena tidak lagi ada gunanya.
2. **User non-root `ah`** dengan `loginctl enable-linger`. Harness tidak pernah jalan sebagai root.
3. **Toolchain**: node LTS, python3, git, ripgrep; `claude` CLI global.
4. **Auth Claude team plan** — login interaktif sekali lewat SSH. Kredensial tidak pernah masuk
   git. `ah doctor` diperluas dengan cek auth, dan **trigger `auth` baru** yang mengirim peringatan
   Telegram saat auth mati — karena di VPS tidak ada yang melihat prompt login.
5. **Clone harness** ke `~/AI-Workspace` di VPS. `.env` baru (chmod 600): token hasil rotasi,
   `TELEGRAM_ALLOWED_CHATS`, `AH_MODEL_*`.
6. **Hanya `projects/sandbox`** yang di-clone. `agents/.scope` di VPS dimulai dengan
   `HOLD cbqa/*` dan `HOLD nexora/*` — `assert_execution_allowed` (`common.sh:34-55`) sudah
   menegakkan ini, jadi repo klien tidak bisa disentuh bahkan bila ter-clone tak sengaja.
7. **Pasang bot + trigger lewat `supervise.sh`**; `ah bot pair` dari VPS, pairing ulang dari HP.
8. **Dash tetap loopback.** Diakses dari Mac lewat `ssh -L 7777:127.0.0.1:7777`. Tidak ada
   reverse proxy, tidak ada port publik. Firewall: hanya 22 masuk.
9. **Hardening**: SSH key-only, root login mati, fail2ban, unattended-upgrades, disk usage alert.
10. **Mac jadi klien.** `~/AI-Workspace` di Mac tetap ada untuk kerja manual, tapi bot dan
    trigger tidak pernah dipasang di sana lagi. Dicatat di README supaya tidak terpasang ulang
    tanpa sengaja.

**Definisi selesai Fase 2:** Mac dimatikan, lalu dari HP `/status`, `/kanban`, dan
`/ask lead ringkas status` semuanya berhasil, dan trigger `standup` menyala esok paginya.

---

## Fase 3 — Approval gate (agent bertanya, Anda menjawab dari HP)

Protokol berbasis file, jadi bekerja untuk engine apa pun dan tidak butuh port terbuka.

- **`bin/lib/gate.py`** (baru) — `ask(question, options, kind, job_id, timeout)` menulis
  `agents/.gates/<gid>.json` lalu polling sampai dijawab atau timeout.
  `answer(gid, choice, by_chat)` mencatat keputusan **dan siapa yang memutuskan** (jejak audit).
  `pending()` dikonsumsi tgwatch dan dash.
- **`bin/lib/gate.sh` + `bin/ah`** — subcommand yang dipanggil agent:
  ```
  ah ask "Boleh saya commit 3 file ini dan push ke dev?" --kind push --options ya,tidak --timeout 900
  ```
  stdout = jawaban; exit `0` dijawab, `2` timeout (agent wajib berhenti dan melapor blocked).
- **`tgcore.py`** — `send(..., markup=None)`, `kb(rows)`, `answer_callback()`, `edit_text()`.
- **`tgbot.py`** — cabang `callback_query`: parse `gate:<gid>:<choice>` (≤64 byte), cek level izin,
  `gate.answer()`, lalu `editMessageText` supaya tombol hilang dan pesan menunjukkan siapa
  memutuskan apa. Callback dari chat tak berizin ditolak dan dicatat.
- **`tgwatch.py`** — `_gate_events(w)` sebagai produser event baru di `detect()`, di-mirror di
  `prime()` supaya gate lama tidak dibanjirkan saat pertama jalan.
- **`dash.py` + `dash.js`** — `gates` masuk `/api/state`; panel gate dengan tombol yang sama
  memanggil `POST /api/gate/answer` (pakai `X-AH-Token` yang sudah ada). HP dan Command Center
  adalah dua pintu ke gate yang sama.

**Perubahan kebijakan** — `AGENTS.md` dan `agents/roles/_common.md`:
- Persetujuan lewat gate **sah** sebagai "explicit human approval" untuk commit,
  `git push` ke `dev`/`staging`, dan install dependency.
- **Tidak pernah** sah untuk push ke `main`/`master`/`production`/`prod`, merge, deploy,
  migration produksi, atau perubahan kredensial. Batas ini dikunci di `gate.py` sebagai
  daftar-tolak: gate dengan `kind` terlarang **ditolak saat dibuat**, bukan saat dijawab — jadi
  tidak bergantung pada agent yang jujur. Pre-push hook (`ah protect`) tetap lapisan kedua.
- Timeout = berhenti dan lapor blocked, bukan lanjut tanpa izin.

Setelah ini, trigger boleh berhenti read-only: agent terjadwal akhirnya punya kanal untuk bertanya.

---

## Fase 4 — Percakapan dua arah + tombol inline

Claude mendukung resume (terverifikasi di mesin ini, claude 2.1.272): `--session-id <uuid>` di
depan, lalu `claude -p --resume <uuid> "<prompt>"`.

- **`jobs.py`** — `spawn()` membuat UUID dan menyimpannya di meta.
  `followup(jid, text)` baru: resume, **append ke log yang sama** (`open(log,"ab")`), naikkan
  `turns`, reset `finished`/`exit`. `/tail` tetap satu transkrip utuh dan Command Center tidak
  perlu tahu apa-apa.
- **Balas = lanjut ngobrol.** Saat `tgwatch` mengirim notifikasi "run selesai", simpan
  `message_id -> job_id` di `watch.json`. Di `_dispatch`, pesan yang merupakan *reply* ke
  notifikasi itu dan bukan command → `jobs.followup()`. `/reply <job-id> <teks>` sebagai jalur
  eksplisit.
- **Pesan bebas tanpa slash** (bukan reply) → dikirim ke role `lead`. `lead` adalah role
  perencanaan read-only, jadi murah dan aman. `/chat off` mematikannya.
- **Tombol inline** (memanfaatkan `callback_query` dari Fase 3):
  `/kanban` → `▶ Run` · `👁 Detail` per kartu; `/jobs` → `📄 Tail` · `🛑 Stop` · `💬 Reply`;
  `/task` → `▶ Run` · `✅ Tick` · `🌿 Worktree`; `/triggers` → `▶ Run now`.
- Handler sekarang boleh mengembalikan `str` **atau** `(str, markup)`; `_dispatch` menangani
  keduanya, jadi 24 handler yang ada tidak perlu disentuh.

---

## Fase 5 — Pipeline antar-role

- Task file dapat field opsional `- **Pipeline:** backend, review, qa`; `jobs.spawn(..., chain=[...])`
  menyimpannya di meta.
- **`bin/lib/pipeline.py`** (baru) — `tick()`: job yang baru selesai dengan `exit == done` dan
  masih punya sisa chain → spawn role berikutnya dengan blok `## Report` sebelumnya sebagai
  konteks. Job `failed` menghentikan chain dan mengirim satu notifikasi.
- Dipanggil dari loop tgbot dan dari `GET /api/state`. Karena di VPS bot selalu hidup, pipeline
  selalu maju.
- Telegram: `/pipeline task-007 backend review qa`.
- Role `review`/`qa` tetap menerima diff + acceptance criteria saja (lihat 1a) — pemisahan
  konteks tidak boleh bocor lewat chain.

---

## Fase 6 — Trigger berbasis event

`agents/triggers.json` dapat blok opsional `when`:
```json
"when": { "type": "command", "run": "...", "min_interval": "2h" }
```
- Tipe `command` (exit 0 = kondisi terpenuhi), plus bawaan `branch_behind` dan `worktree_stale`
  yang memakai `state.worktrees()` / `state._git()` yang sudah ada.
- **`bin/lib/trigwatch.py`** (baru) — dievaluasi dari loop tgbot, menghormati `min_interval`,
  mencatat penyalaan lewat `trigmem.py` yang sudah ada sehingga `ah trigger memo` dan deteksi
  "terlambat" tetap bekerja tanpa perubahan.
- Trigger berjadwal tidak berubah; `when` adalah tambahan.

---

## Fase 7 — Artefak ke Telegram

- **`tgcore.send_document(chat_id, path, caption)`** — encoder multipart/form-data manual
  (~30 baris, stdlib).
- `/diff <task-id>` (diff worktree), `/report <task-id>`, `/log <job-id>` (saat `/tail` terpotong
  di 2800 karakter).
- **Guard wajib, diuji bukan hanya ditulis:** tolak path di luar workspace, tolak
  `.env`/`*.pem`/`*.key`/`*.p12`, batas 20 MB.

---

## File yang disentuh

| Baru | Diubah |
|---|---|
| `bin/lib/supervise.sh` | `bin/lib/jobs.py` — engine, exit code, session, followup |
| `bin/lib/gate.py`, `gate.sh` | `bin/lib/run.sh` — claude-only, hapus cabang codex |
| `bin/lib/pipeline.py` | `bin/lib/trigger.sh` — claude, supervisor, kalender systemd |
| `bin/lib/trigwatch.py` | `bin/lib/tgbot.py` — callback, thread pool, reply, izin |
| `tests/test_job_exit_status.py` | `bin/lib/tgcore.py` — markup, kb, document |
| `tests/test_gate.py` | `bin/lib/tgwatch.py` — gate & failed events, msg map |
| `tests/test_pipeline.py` | `bin/lib/state.py` — `/proc` cwd, supervisor-aware |
| `tests/test_supervise.py` | `bin/lib/tgcmd.py`, `dash.py`, `dash.js`, `doctor.sh`, `bot.sh` |
| `agents/reports/vps-recon.md` | `bin/ah`, `README.md`, `.env.example` |
| | `AGENTS.md`, `agents/roles/_common.md` — kebijakan approval + kontrak reviewer |

Dipakai ulang, bukan ditulis ulang: `state.py` (snapshot/tasks/worktrees/triggers),
`trigmem.py` (memori & deteksi terlambat), `jobs._contract()` (kontrak identik CLI vs UI),
`tgcore.send()` (pemecah 3800 karakter + fallback plain text), `common.sh:assert_allowed_path`
+ `assert_execution_allowed`, `claim.sh` (locking), `_trg_calendar` (parser jadwal),
`AH_WORKSPACE` override (isolasi test).

---

## Verifikasi

Test suite yang ada memakai `AH_WORKSPACE` untuk isolasi — pola yang sama untuk test baru.

```bash
python3 -m pytest tests/ -q     # 5 suite lama + 4 baru, harus hijau di macOS DAN Linux
```

End-to-end yang benar-benar dijalankan, bukan diasumsikan:

1. **Exit code** — paksa satu job gagal; pastikan dash dan Telegram menampilkan `🛑 failed`, bukan `✅`.
2. **Claude-only** — `ah run review <task>` dan keempat trigger berjalan tanpa codex terpasang
   di PATH sama sekali.
3. **Supervisor** — `ah bot install` dan `ah trigger install standup` menghasilkan unit yang benar
   di kedua OS; `ah bot status` melaporkan keadaan sebenarnya.
4. **VPS tanpa laptop** — **Mac dimatikan**, lalu dari HP: `/status`, `/kanban`,
   `/ask lead ringkas status`. Trigger `standup` menyala esok paginya dan memo-nya tercatat.
5. **Satu bot saja** — setelah rotasi token, pastikan tidak ada long-poller kedua: `/status`
   dibalas satu kali, bukan hilang bergantian.
6. **Gate** — `ah ask "test" --kind question --options ya,tidak` di VPS; tombol muncul di HP,
   tap Ya, perintah mengembalikan `ya` exit 0. Ulangi `--kind push` dari chat `viewer` → ditolak.
   Ulangi `--kind deploy` → ditolak **saat pembuatan**.
7. **Follow-up** — `/ask lead ringkas status`, balas notifikasinya dengan instruksi lanjutan;
   `/tail` menunjukkan satu transkrip dua giliran dengan konteks terbawa.
8. **Tombol** — `/kanban`, tap `▶ Run`, job muncul di dash.
9. **Pipeline** — task sandbox `Pipeline: backend, review`; `review` menyala sendiri setelah
   `backend` sukses, dan **tidak** menyala saat `backend` gagal.
10. **Trigger event** — `when.type=command` yang pasti exit 0: menyala sekali, lalu `min_interval` dihormati.
11. **Artefak** — `/diff` pada worktree kotor; lalu sengaja coba kirim `.env` → harus ditolak.
12. **Regresi bot** — `/doctor` (lambat) lalu segera `/status`; `/status` balas tanpa menunggu.

Semua uji di `projects/sandbox`. Tidak ada percobaan terhadap repo `cbqa`/`nexora`.

---

## Risiko yang saya catat

- **Kode di mesin pihak ketiga.** Fase 2 hanya membawa `sandbox`. Sebelum repo cbqa/nexora
  menyusul, itu keputusan sadar Anda — bukan langkah teknis yang saya ambil sendiri.
- **Reviewer tidak lagi beda vendor** (temuan D). Pemisahan model + konteks lebih lemah dari
  sebelumnya. Kalau ini tidak diterima, alternatifnya menyisakan codex khusus untuk `review`/`qa`
  di Mac dan menjalankan review sebagai langkah manual.
- **Auth Claude bisa kedaluwarsa** di VPS tanpa ada yang melihat. Ditangani trigger `auth` +
  peringatan Telegram, tapi pemulihannya tetap manual lewat SSH.
- **VPS satu titik kegagalan.** Bila mati, tidak ada fallback ke Mac karena bot hanya boleh satu.

## Di luar cakupan

- Webhook Telegram (butuh tunnel + secret stabil; long-polling tidak butuh port masuk sama sekali).
- Mengganti stdlib dengan `python-telegram-bot`.
- Membuka dash ke internet — akses hanya lewat SSH tunnel.
- Mengizinkan agent menyentuh production atau `main`/`master` lewat jalur apa pun.
