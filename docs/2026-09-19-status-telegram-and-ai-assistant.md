# Status Update — Telegram Bot Surface + AI Assistant Widget

**Tanggal:** 2026-09-19 · **Host:** `dev-kemenkes` / `31.97.67.241` (VPS **bersama** dengan `dev-support`, `monitoring`, dll)
**Disusun untuk:** Imam Nurokhi (owner) · **Sumber:** verifikasi langsung di host, bukan salinan dokumen lama

Dokumen ini menggabungkan dua jalur kerja yang berjalan paralel dan sekarang keduanya
menyentuh pengguna nyata: **surface Telegram** (kontrol harness + chat AI) dan
**AI Assistant widget** (di dua prototipe web). Setiap klaim di sini sudah dicek ulang
hari ini; yang belum terbukti ditandai eksplisit.

---

## Ringkasan Eksekutif

| Jalur | Kondisi | Celah utama |
|---|---|---|
| `@AgentNexoraBot` — kontrol harness | 🟢 Live, stabil | teks bebas diabaikan (memang desainnya) |
| `@AskNexAIBot` — chat AI penuh | 🟢 **Live hari ini** | tidak selamat dari reboot (belum systemd) |
| AI Assistant widget — accreditation | 🟢 Live (Fase 6) | belum ter-push ke git |
| AI Assistant widget — academy | 🟢 Live (first-access) | belum ter-push ke git |
| Feedback collector | 🟢 Live, data mengalir | — |
| Service-desk | ⚪ Sengaja tidak disentuh | keputusan owner |

Tiga hal yang perlu keputusan owner, diurutkan menurut dampak:

1. **Kredensial push GitHub (PAT).** Seluruh kode widget — Fase 0 sampai 6 — hidup di server
   tapi **tidak ada di git**. Fresh clone akan kehilangan semuanya. Ini utang terbesar.
2. **Unit systemd untuk `@AskNexAIBot`.** Tanpa itu, reboot VPS mematikan chat AI.
3. **Rotasi tiga kredensial** yang pernah lewat transkrip chat (§9 CLAUDE.md), masih tertunda.

---

# BAGIAN 1 — Surface Telegram

## 1.1 Dua bot, dua peran berbeda

Sekarang ada **dua** bot, dan perbedaannya penting untuk tidak tertukar.

| | `@AgentNexoraBot` | `@AskNexAIBot` |
|---|---|---|
| Peran | kontrol harness, deterministik | tanya-jawab bebas dengan AI |
| Mesin | `bin/lib/tgbot.py`, unit `ah-telegram` | sesi Claude Code di tmux `tgchannel` |
| Model AI | tidak ada di loop | Sonnet 5, langganan Team |
| Input | 39 slash command; teks polos **diabaikan** | bahasa bebas, dengan memori percakapan |
| Akses data | state harness lokal saja | file workspace + **semua MCP** + memori + skill |
| Sejak | sebelum 2026-09-17 | **2026-09-19** |

Keduanya jalan berdampingan tanpa saling ganggu. Itu bukan kebetulan — lihat §1.4.

## 1.2 `@AgentNexoraBot` — apa yang sudah bisa

39 command terdaftar, berjenjang tiga role (`viewer` → `operator` → `owner`).
Saat ini satu chat ter-pair: `6687943152` dengan role `owner`.

**Viewer** — `/status` `/agents` `/jobs` `/ops` `/brief` `/reporting` `/sources`
`/reminders` `/support` `/deploy` `/help`

**Operator** — `/kanban` `/tasks` `/task` `/triggers` `/engine` `/tail` `/digest`
`/weekly` `/daily` · kirim berkas ke HP: `/log` `/diff` `/report`

**Owner** — `/new` `/assign` `/ac` `/tick` `/note` `/close` `/wt` · eksekusi:
`/run` `/ask` `/stop` `/resume` `/trigger` · lain: `/push` `/doctor` `/quiet` `/grant`

**Notifikasi otomatis** (maks 6 event per poll, bisa dimatikan `/quiet`): run selesai/gagal
beserta cuplikan hasil, task yang semua acceptance criteria-nya lengkap, task mandek,
trigger gagal/telat, engine ditolak.

**Timer yang mengirim ke Telegram** (5 unit aktif): sprint reminder harian Sen–Kam 07:00 WIB,
sprint+weekly Jum 07:00, feedback digest Jum 07:30, weekly report Jum 08:00, standup harian
07:00 — semuanya WIB (`Asia/Jakarta`), meski jam server UTC.

### Yang tidak berfungsi, dan alasannya

| Hal | Sebab |
|---|---|
| `/daily` | `SLACK_BOT_TOKEN` belum ada di `.env`. Bot menjawab "Slack belum tersambung", bukan error. |
| `/wt`, `/diff` | mengasumsikan `worktrees/` dan `projects/` yang tidak ada di host ini |
| `/sources` | jujur melaporkan GitHub/Slack/Notion/NEXONE semua belum tersambung |
| Reminder sprint | hanya **nudge** — timer tak punya Slack token, MCP, maupun browser, jadi tidak menulis apa pun ke NEXONE/Notion |

## 1.3 `@AskNexAIBot` — chat AI penuh (BARU)

### Kenapa bukan menambal bot lama

`bin/lib/tgbot.py:150` membuang setiap pesan tanpa awalan `/`. Kemampuan tanya-jawab
di bot lama hanyalah `/ask <role> <teks>`, yang secara struktur bukan percakapan:
tiap panggilan men-spawn `claude -p` baru (**tanpa memori**), balasannya cuma job id lalu
satu baris notifikasi, dan agent-nya berjalan di allowlist sempit tanpa MCP — jadi
Slack, Notion, NEXONE, dan internet semua di luar jangkauan.

Rencana awal adalah **membangun sendiri** penggantinya. Owner menolak rencana itu dan
meminta riset lebih dulu. Ternyata benar: Claude Code sudah punya fiturnya, namanya
**Channels** — plugin Telegram resmi yang mendorong pesan chat ke sesi Claude Code yang
sedang berjalan. Hasilnya jauh lebih kuat, dengan kuota yang sama, dan setup ~1 jam
alih-alih ~2 hari coding.

### Kondisi terpasang

```
Claude Code v2.1.278 · Sonnet 5 · Claude Team · ~/AI-Workspace
Channels: plugin:telegram@claude-plugins-official  (research preview)
Permission mode: manual
access.json: dmPolicy=allowlist, allowFrom=["6687943152"]
tmux: tgchannel (user ahagent)
```

Yang ikut terbawa ke chat: seluruh file workspace, `CLAUDE.md`, memori, skill, subagent,
**semua MCP connector** (Slack, Notion, Linear, GitHub, Context7), dan lampiran foto dari HP.

**Terbukti dua arah** hari ini: pesan masuk tercatat sebagai `← telegram · 6687943152: Hi`,
dan balasan sampai ke Telegram lewat tool `reply` plugin.

### Permission relay — kenapa ini penting

`CLAUDE.md` §4 mencatat bahwa headless agent tidak bisa disetujui: prompt izin di `claude -p`
tidak ada yang menjawab. Plugin ini mendeklarasikan `claude/channel/permission` dan
meneruskan prompt izin ke Telegram sebagai pesan dengan tombol Approve/Deny.

Artinya sesi yang disetir dari Telegram **bisa** disetujui, dan **tidak perlu**
`--dangerously-skip-permissions` di host bersama ini. Sisi sebaliknya: siapa pun di
allowlist bisa menyetujui tool call. Itu sebabnya `policy allowlist` bukan opsional.

### Cara mengoperasikan

```sh
sudo -u ahagent -H tmux attach -t tgchannel     # masuk
# keluar: Ctrl-b lalu d   (JANGAN exit / Ctrl-D / /exit — itu mematikan jembatan)
```

Menutup tab terminal aman; tmux otomatis detach.

## 1.4 Jebakan yang nyaris mematikan bot lama

`server.ts:33-44` plugin memuat `~/.claude/channels/telegram/.env`, **tetapi environment
asli menang** (`if (m && process.env[m[1]] === undefined)`).

Workspace `.env` sudah berisi `TELEGRAM_BOT_TOKEN` milik `@AgentNexoraBot`. Telegram hanya
mengizinkan **satu** consumer `getUpdates` per token. Jadi sesi channel yang mewarisi
variabel itu akan menjadi consumer kedua dan **kedua bot mati dengan HTTP 409 Conflict**.

Ketahuan dari membaca kode plugin, bukan dari insiden — 409 tidak pernah terjadi.

**Aturan yang lahir dari situ: sesi channel tidak boleh memuat workspace `.env` sama sekali.**
File itu hanya menyumbang dua variabel, dan keduanya justru merusak:

| Variabel | Kalau ikut terbawa |
|---|---|
| `TELEGRAM_BOT_TOKEN` | plugin polling bot yang salah → 409, dua bot mati |
| `CLAUDE_CODE_OAUTH_TOKEN` | **menimpa login Team** → sesi jalan sebagai "Claude API", bukan langganan |

Terukur hari ini:

| Environment | `authMethod` | Plan |
|---|---|---|
| `.env` di-source | `oauth_token` | tidak ada info |
| `.env` tidak di-source | `claude.ai` | **team**, NexoraTech |

Verifikasi **sebelum** menyalakan, bukan sesudah:

```sh
claude auth status | grep -E 'authMethod|subscriptionType'   # mau: claude.ai + team
```

## 1.5 Empat hal lain yang memakan waktu

1. **Token harness tidak cukup untuk sesi interaktif.** `ahagent` belum pernah menjalankan
   Claude Code interaktif, jadi muncul wizard onboarding lalu alur OAuth browser.
   `CLAUDE_CODE_OAUTH_TOKEN` hanya bisa memanggil model. Owner menyelesaikan login penuh.
   *Konsekuensi:* kredensial sesi ber-scope penuh milik akun owner kini ada di home `ahagent`
   pada VPS **bersama** — lebih luas dari sebelumnya, diterima secara sadar, layak ditinjau
   ulang saat audit akses. *Sisi baiknya:* itu satu-satunya penghalang **Remote Control**,
   yang kini tinggal butuh toggle Owner.
2. **Auto mode sempat menyala tanpa sengaja.** Prompt izin pertama menawarkan `1. Yes` dan
   `2. Yes, and switch to auto mode`; satu Enter nyasar memilih opsi 2, sehingga selama
   beberapa menit sesi menyetujui tool call-nya sendiri di host produksi. Diperbaiki dengan
   relaunch memakai flag `--permission-mode manual`, sekaligus menghilangkan keystroke
   penyebabnya.
3. **Socket tmux berbeda per user.** `tmux attach` sebagai `root` menjawab `no session`;
   sesinya milik `ahagent`.
4. **Toggle Channels Team dibuktikan secara negatif.** Notice startup menyebut nama plugin
   **tanpa baris warning di bawahnya**. Plugin yang ter-load bukan bukti: dengan toggle mati,
   MCP server tetap connect dan tool-nya tetap jalan, tapi **tidak ada pesan yang sampai**.

## 1.6 Yang ditolak permission classifier

Tiga aksi ditolak selama setup, semuanya keputusan izin, bukan bug:

| Aksi | Alasan | Penyelesaian |
|---|---|---|
| `claude plugin install …` | `Unauthorized Persistence` | dijalankan owner via `!` |
| menulis unit systemd | `Create Unsafe Agents` | didokumentasikan sebagai code block, **tidak** dipasang |
| menjalankan sesi | `Create Unsafe Agents` | diketik asisten, Enter ditekan owner (3× restart) |

**Akibatnya `@AskNexAIBot` belum reboot-safe.** Unit systemd-nya lengkap di
`ops/channels/README.md` — sengaja **tanpa** `EnvironmentFile`, dengan
`--permission-mode manual` di `ExecStart`.

---

# BAGIAN 2 — AI Assistant Widget

Urutan rollout per owner: **accreditation dulu, lalu academy. Service-desk ditunda.**
Plan induk: `docs/ai-assistant-widget-rollout-plan.md`.

## 2.1 Yang tayang sekarang

| App | URL | Ukuran | Terakhir publish |
|---|---|---|---|
| accreditation | `/var/www/prototypes/accreditation/index.html` | 395 KB | 2026-09-19 06:09 |
| academy | `/var/www/prototypes/academy/index.html` | 698 KB | 2026-09-19 06:09 |
| service-desk | `/var/www/prototypes/servicedesk/` | — | tidak disentuh |

Keduanya build standalone satu-berkas. Identifier ter-minify, tapi jejak widget terverifikasi
ada di kedua bundle (`collectorEnabled`, dan `rr-vanilla` di academy).

## 2.2 Accreditation — kecerdasan penuh (Fase 6)

- `src/widget/core/guidance.js` — modul murni: `screenSuggestions()`, `buildTour()`, `gateGuidance()`
- `AREA_GUIDE` di `app.config.js` — tiap **9 area review** dipetakan ke route layar nyata plus
  prompt yang **terjawab dari sumber**
- `ReadinessWidget.jsx` — chip saran kontekstual per layar, tur berpandu per area (navigasi
  digerakkan jawaban lewat prop `onNavigate`), dan gate yang memandu: tombol "buka layar" untuk
  area yang belum tercentang, dengan alasan penolakan **persis** string `signOff()`
- Gate `guidance.smoke.mjs`: **44/44**, setiap route nyata dan **setiap prompt ANSWERED_FROM_SOURCE**
  — inilah jaminan anti-mismatch

## 2.3 Academy — tampil sejak akses pertama

`academy/widget/main.js` tidak lagi membongkar widget di halaman landing pre-login; widget
mount sekali dan bertahan. Karena hidup di shadow root sendiri, DOM landing tetap
**0 `aside nav button`** sehingga 92-suite tidak berubah.

- Suite ter-inject: **94/94** (92 asli + 2 baru)
- Default `./run-tests.sh`: **92 passed + 2 skipped**

Dua fakta yang mahal dipelajari, keduanya kini terbukti oleh pengukuran:

1. **Academy tidak punya sinyal nav aktif berbasis class.** Setiap `aside nav button` punya
   `className` identik yang tidak pernah berubah, tanpa `aria-current`, tanpa `data-*`. Sinyal
   yang nyata adalah **inline style** (`background-color: transparent` = tidak aktif). Plan §5.1
   menyatakan sebaliknya dan **salah** — membaca class akan selalu melaporkan menu pertama, dan
   tidak ada test yang menangkapnya.
2. **Request collector yang gagal di-log ke console oleh BROWSER**, sebelum JS mana pun melihatnya
   — tidak ada try/catch yang bisa meredamnya. Menyuntik widget dengan POST ke collector yang
   tidak ada mengubah 92 test Playwright academy menjadi 36 gagal. Karena itu ada `collectorEnabled`:
   antre ke localStorage di mana pun, kirim hanya di tempat collector benar-benar ada.

## 2.4 Feedback collector

`ops/feedback/collector.py` — `ThreadingHTTPServer` stdlib berdiri sendiri di `127.0.0.1:7788`,
unit `ah-feedback`, dengan hardening sama seperti `ah-dashboard.service`. **Bukan** bagian dari
`bin/lib/dash.py`: dashboard itu control-plane yang men-spawn proses agent, sedangkan ini ingest
pasif dari browser dan harus tetap terpisah.

- NDJSON append-only, satu berkas per app per hari UTC, di `/var/lib/nexora-feedback/<app>/`
- `fsync()` per baris, `0640 ahagent:ahagent`
- `remote_user` dan `received_at` **di-assert server** — tidak pernah percaya kiriman klien
- nginx: satu blok aditif `location ^~ /widget-feedback/` (terverifikasi di baris 210 vhost),
  6 header dinyatakan ulang seluruhnya
- `healthz` hari ini: **200**

**Data nyata per 2026-09-19:**

| App | Pengguna | Pertanyaan | `CLARIFICATION_NEEDED` (gap KB) |
|---|---|---|---|
| academy | imam.nurokhi@ | 3 | 1 |
| academy | support@ | 3 | 3 |
| accreditation | imam.nurokhi@ | 6 | 3 |

Inti gunanya bukan jumlah pertanyaan, melainkan **daftar gap KB**. Sejak 2026-09-19 collector
juga merekam **teks pertanyaannya** (`MAX_RECORDED_TEXT=500`), sehingga `ah feedback` mencetak
backlog KB yang sebenarnya, bukan sekadar angka — persis yang sudah dijanjikan notice transparansi
widget. 4 + 3 pertanyaan lama tercatat tanpa teks karena perekaman teks baru dimulai hari itu.

## 2.5 Cakupan KB — diperbaiki di generator, bukan ditambal

Seorang reviewer bertanya "Ada menu/modul apa saja?" dan mendapat `CLARIFICATION_NEEDED`.
Data collector menunjukkan **7 tak terjawab vs 1 terjawab**. Dua sebab struktural: academy
tidak menghasilkan **rule per-modul** (accreditation punya satu per layar), dan kata
"modul"/"fitur" tidak ada di keyword mana pun.

Diperbaiki di **generator** (`widget/gen-knowledge.mjs`, `scripts/gen-knowledge.mjs`), bukan di
hasilnya — academy 43 → 84 rule. Diukur dengan baterai pertanyaan realistis:
**academy 63% → 100%**, **accreditation 92% → 100%**, dengan smoke regresi tetap hijau sehingga
gap yang tertutup tidak berubah menjadi mismatch.

LLM sungguhan di balik widget tetap **ditunda atas keputusan owner**. Kalau kelak disetujui,
gunakan proxy **same-origin `/widget-ai/`** — tidak perlu ubah CSP, karena keberatan CSP di plan
hanya berlaku bila model dipanggil dari browser.

## 2.6 Utang terbesar: tidak ada kredensial push git

**Tidak ada jalan untuk push apa pun ke git dari sesi ini.** Connector GitHub claude.ai di sini
**read-only**: autentikasi sebagai owner dan bisa membaca, tapi `create_branch` /
`create_or_update_file` mengembalikan `403 Resource not accessible by integration`. Tidak ada
`gh` auth, `.netrc`, kunci SSH, maupun entri di `.env`.

Konsekuensinya, satu-satunya jalur rilis adalah **publish manual**: `build:standalone` lalu salin
ke `/var/www/prototypes/<app>/`, melewati `refresh.sh` yang biasanya `git pull`. Itu
memunculkan kembali cacat "live ≠ apa yang bisa direproduksi git" yang dulu diperbaiki Fase 0.

Pengaman yang dijalankan: setiap publish manual **menyimpan snapshot** tree live lebih dulu ke
`/var/backups/<app>/`, karena `publish()` milik `refresh.sh` menghapus tree sebelumnya tanpa
menyisakan cadangan. Terverifikasi hari ini — 6 arsip accreditation, 4 arsip academy, masing-masing
bertanda fase.

⚠️ **Jangan jalankan `refresh.sh` untuk kedua app ini** sampai tree ter-push: skrip itu
`git reset --hard` ke `origin/dev` dan akan menghapus seluruh kerja yang belum ter-commit.
Ini mencakup seluruh direktori `widget/` academy, yang hanya ada sebagai berkas lokal
untracked — selamat dari `refresh.sh` (reset tidak menyentuh untracked) tapi **tidak** selamat
dari fresh clone.

## 2.7 Kendala e2e yang bersifat lingkungan

Backend e2e `nexaccred-react` (`roles` / `readiness-visibility`) **tidak bisa dijalankan di sini**.
API-nya IPv4-only (`127.0.0.1:3001`) sementara browser me-resolve `localhost` ke IPv6; mengarahkan
ke `127.0.0.1` justru memicu CORS API (hanya `localhost:5173` yang diizinkan) → login tidak pernah
selesai → semua test navigasi timeout. Murni lingkungan, bukan regresi.

Verifikasi widget karenanya lewat `test:widget` + `test:vanilla-shell` + probe headless terhadap
**standalone PRE-LOGIN** yang sudah tayang (FAB dan engine keduanya client-side).

---

# BAGIAN 3 — Gerbang mutu & kesehatan sistem

## 3.1 Test suite

```
tests/                  305
ops/harness/tests/       11
ops/nginx/tests/         20
ops/n8n/tests/           10
ops/feedback/tests/      29
```

Plus gerbang milik repo prototipe: `npm run test:widget` + `npm run test:vanilla-shell`
(accreditation), dan `./run-tests.sh` 92 Playwright (academy) — wajib **92/92**, dan byte yang
dipublish harus sha256-match dengan yang diuji.

## 3.2 Layanan hari ini

| Unit | Status |
|---|---|
| `ah-telegram` | 🟢 active — **0** error 409 sepanjang setup channel |
| `ah-dashboard` | 🟢 active (`127.0.0.1:7777`) |
| `ah-feedback` | 🟢 active, `healthz` 200 |
| timer `ah-*` | 5 terpasang |
| tmux `tgchannel` | 🟢 running, **tidak** reboot-safe |

## 3.3 Catatan keamanan yang masih terbuka

1. **Tiga kredensial menunggu rotasi** (§9 CLAUDE.md, ditunda owner 2026-09-17): password root VPS,
   Basic Auth `agents.nexoratech.co` user `imam`, dan password akun owner n8n.
2. **Backup n8n tidak terenkripsi.** `/var/backups/nexora-operations/<stamp>/` menyimpan
   `database.dump`, `n8n-data.tar.gz`, dan `stack.env` polos — dan `stack.env` berisi
   `N8N_ENCRYPTION_KEY` serta `POSTGRES_PASSWORD`, jadi kuncinya duduk di sebelah data yang
   dilindunginya. Permission `0600` root-only menahan risikonya hari ini, tapi plan menuntut
   backup terenkripsi dan teruji-restore. **Restore belum pernah diuji.**
3. **Blast radius `@AskNexAIBot`.** Pengirim di allowlist menyetir sesi dengan akses baca-tulis
   penuh ke VPS produksi ini plus Slack/Notion/Linear/GitHub lewat MCP. Jauh melampaui
   `@AgentNexoraBot`, memang begitu desainnya.
4. **Residensi transkrip.** Selama sesi channel tersambung, transkrip disimpan di server Anthropic
   untuk sinkronisasi antar-perangkat. Eksekusi dan akses filesystem tetap lokal.
5. **`SLACK_BOT_TOKEN` masih kosong**, sehingga `/daily` mati dan timer sprint tidak bisa membaca
   Slack tanpa pendampingan.

---

# BAGIAN 4 — Langkah berikutnya, menurut dampak

| # | Tindakan | Siapa | Kenapa sekarang |
|---|---|---|---|
| 1 | Tambahkan **PAT GitHub** ke `.env` | owner | seluruh kode widget Fase 0–6 hilang pada fresh clone |
| 2 | Putuskan **unit systemd** `@AskNexAIBot` | owner | tanpa itu chat AI mati saat reboot |
| 3 | Pakai chat AI beberapa hari, amati **permission relay** | owner | kalau terlalu berisik, persempit lewat allowlist settings — **jangan** pindah ke auto mode |
| 4 | Tambahkan `SLACK_BOT_TOKEN` | owner | menghidupkan `/daily` dan otomasi sprint |
| 5 | **Rotasi tiga kredensial** §9 | owner | tertunda sejak 2026-09-17 |
| 6 | **Uji restore** backup n8n + enkripsi | — | belum pernah diuji sama sekali |
| 7 | Pertimbangkan **Remote Control** | owner | tinggal satu toggle; kontrol dari app Claude di HP |

Catatan model: sesi channel memakai **Sonnet 5**. Naikkan ke Opus dengan `/model opus` hanya bila
jawabannya terasa kurang — Sonnet default yang lebih hemat untuk pertanyaan operasional.

---

## Rujukan dokumen

**Telegram / Channels**
- `ops/channels/README.md` — runbook, unit systemd, seksi "The workspace `.env` is poison here"
- `agents/reports/2026-09-19-telegram-channel-claude-code-chat.md` — 11 seksi, rollback per item

**AI Assistant widget**
- `docs/ai-assistant-widget-rollout-plan.md` — plan induk
- `docs/widget-readiness-ai-assistant.md` — dokumen sitasi widget (direkonstruksi 2026-09-18)
- `agents/reports/2026-09-18-ai-assistant-widget-fase0-fase1.md` … `-fase4-academy.md`
- `agents/reports/2026-09-19-widget-fase6-academy-firstaccess-collector.md`

**Operasional**
- `agents/reports/2026-09-17-cloud-ops-nginx-ratelimit-fix.md` — outage dan kelima penyebabnya
- `agents/reports/2026-09-18-sprint2-3-reconciliation-nexone-notion.md` — preseden alur sprint report
- `CLAUDE.md` — peta operasional workspace

**Eksternal**
- <https://code.claude.com/docs/en/channels>
- <https://code.claude.com/docs/en/remote-control>
- <https://github.com/anthropics/claude-plugins-official/tree/main/external_plugins/telegram>
