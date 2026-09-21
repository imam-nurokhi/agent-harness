# Sesi — perbaikan rate limit nginx `agents.nexoratech.co` (selesai & terverifikasi)

**Tanggal:** 2026-09-17
**Lanjutan dari:** `agents/reports/2026-09-17-cloud-ops-nginx-ratelimit-handoff.md`
**Plan induk:** `docs/nexora-cbqa-cloud-operations-plan.md`
**Status:** perubahan produksi sudah diterapkan dan diverifikasi; menunggu satu
gerbang penerimaan dari owner (hard-refresh browser).

---

## 0. Koreksi asumsi yang mengubah seluruh rencana

Handoff sebelumnya memperlakukan "local" dan "VPS" sebagai dua mesin dan
mencatat blocker *"SSH `root@31.97.67.241` ditolak"*. **Itu keliru.** Sesi ini
berjalan sebagai `root` **langsung di atas VPS itu sendiri**:

```
hostname            = dev-kemenkes
eth0                = 31.97.67.241
working directory   = /home/ahagent/AI-Workspace   (satu-satunya salinan)
```

Dibuktikan dengan menulis file penanda secara lokal lalu membacanya kembali
lewat sesi SSH ke `31.97.67.241` — isinya sama.

Konsekuensinya, tiga dari empat item tertunda hilang dengan sendirinya:

| Item tertunda | Status sebenarnya |
|---|---|
| Sync `.git` ke VPS | **Tidak berlaku.** Satu mesin, satu salinan. Lihat §5 — workspace ini memang belum punya git repo sama sekali. |
| Penyamaan `agents/.scope` | **Tidak berlaku.** File yang sama. Isinya `HOLD cbqa/*` + `HOLD nexora/*`, tidak diubah. |
| Restart `ah-dashboard` / `ah-telegram` | **Nyata, sudah dikerjakan.** Lihat §3. |
| Perbaikan `rate=` nginx | **Nyata, sudah dikerjakan.** Lihat §2. |

## 1. Akar masalah — dikonfirmasi ulang terhadap host

Konfigurasi live yang terbaca sebelum perubahan:

```
limit_req_zone $binary_remote_addr zone=agents_per_ip:10m rate=60r/m;
limit_req zone=agents_per_ip burst=200 nodelay;
```

`60r/m` = isi ulang 1 request/detik. `burst=200` hanya reservoir sekali pakai.
Satu page-load n8n menembak 40+ chunk paralel dan dashboard menarik `/api/state`
tiap beberapa detik, jadi pemakaian normal menguras reservoir dan nginx membalas
`429` — untuk `dash.js` (chip beku di `connecting…`, karena hanya `dash.js` yang
pernah mengganti teks literal di `bin/lib/dash.html:20`) dan untuk chunk aset
n8n (blank `/automation/`).

**Cacat kedua yang ditemukan sesi ini,** tidak ada di handoff: vhost live tidak
pernah meneruskan `Upgrade`/`Connection` ke n8n, jadi push channel editor tidak
bisa terbentuk meskipun rate limit sudah benar.

Reproduksi dari luar, tanpa credential (host membalas `401` untuk auth gagal dan
`429` untuk penolakan rate limit, jadi keduanya terbedakan):

| | wave 1 | wave 2 | wave 3 | wave 4 | total 429 |
|---|---|---|---|---|---|
| sebelum | 60×401 | 60×401 | 60×401 | 27×401 / **33×429** | **33 / 240** |
| sesudah | 60×401 | 60×401 | 60×401 | 60×401 | **0 / 240** |

## 2. Perubahan produksi

Urutan TDD: test `ops/nginx/tests/test_validate_vhost.py` sudah merah sejak sesi
sebelumnya; `validate_vhost.py` + kedua artefak ditulis sampai 8 test hijau,
**baru** menyentuh host.

Validator dijalankan terhadap **teks live** lebih dulu dan menandai tepat dua
masalah yang sama dengan yang disimpulkan dari luar:

```
FAIL: limit_req_zone sustained rate is below 5.0r/s; burst alone cannot carry a browser page load
FAIL: vhost does not forward Upgrade/Connection; the n8n editor push channel will fail
```

Dua file, masing-masing di-backup, `nginx -t`, lalu **reload** (bukan restart):

| File | Perubahan |
|---|---|
| `/etc/nginx/conf.d/agents-rate-limit.conf` | `rate=60r/m` → `rate=10r/s`; tambah `map $http_upgrade $agents_connection_upgrade`. Nama zone **tidak diubah**. |
| `/etc/nginx/sites-available/agents.nexoratech.co` | tambah `proxy_set_header Upgrade` + `Connection` di `location ^~ /automation/`. Selain itu identik byte-per-byte dengan yang live. |

`diff` terhadap konfigurasi live hanya menunjukkan komentar + dua baris
`proxy_set_header` tersebut — tidak ada satu pun pengerasan yang dilonggarkan:
`auth_basic`, `limit_conn … 10`, `limit_req_status 429`, `server_tokens off`,
`client_max_body_size`, seluruh security header, dan `proxy_pass` tanpa trailing
slash semuanya dipertahankan.

**Tidak disentuh:** container n8n/PostgreSQL dan compose stack-nya, backup timer,
`ah-resume.timer`, seluruh vhost lain (`dev-kemenkes`, `dev-support`,
`monitoring`, …), file `.agents.htpasswd`, dan semua credential.

## 3. Restart service

`ah-dashboard` dan `ah-telegram` adalah **user unit** milik `ahagent`
(`~/.config/systemd/user/`, `Linger=yes`) — bukan system unit, itu sebabnya
`systemctl is-active` sebagai root melaporkan `inactive` dan menyesatkan.

Keduanya memang menjalankan kode lama: `ah-telegram` start 2026-09-16 19:54:54
sementara `bin/lib/tgbot.py`, `resumerun.py` dan `support.py` diubah 2026-09-17
02:01–02:05. Restart lewat manajer user yang benar:

```sh
sudo -u ahagent XDG_RUNTIME_DIR=/run/user/$(id -u ahagent) \
    systemctl --user restart ah-dashboard ah-telegram
```

Hasil: keduanya `active/running`, `NRestarts=0`, start 2026-09-17 11:41:00 UTC.

## 4. Verifikasi

| Gate | Hasil |
|---|---|
| `ops/nginx/tests` | 8 test OK |
| `ops/n8n/tests` | 10 test OK |
| `validate_vhost.py` vs artefak | OK |
| `ops/nginx/verify_rate_limit.sh` | **PASS: 0/240 rate-limited** |
| Loopback dashboard `127.0.0.1:7777/api/state`, `/dash.js` | 200, 200 |
| Loopback n8n `127.0.0.1:5678/automation/`, `/healthz` | 200, 200 |
| Aset yang dirujuk HTML n8n, resolve di bawah `/automation/` | 6/6 → 200 di loopback, 6/6 → 401 (auth, **bukan** 429) lewat proxy |
| `429` di `access.log` sejak reload 11:41 | **0** (33 yang ada semuanya dari probe pra-perbaikan pukul 11:39) |

Suite utama `tests/` (200 test) **tidak sepenuhnya deterministik** — lihat §5.

### Yang belum bisa diverifikasi dari sini

Fetch **terautentikasi** lewat proxy butuh password Basic Auth user `imam`, yang
tersimpan sebagai hash bcrypt dan tidak dapat dipulihkan. Rantai yang bisa
dibuktikan tanpa password sudah dibuktikan seluruhnya (routing prefix benar,
aset ada, tidak ada lagi 429). Sisanya adalah gerbang penerimaan owner.

## 5. Temuan terbuka (tidak dikerjakan, butuh keputusan owner)

1. **Workspace ini belum berada di bawah git sama sekali.** Tidak ada `.git`
   di `/home/ahagent/AI-Workspace` maupun di mana pun untuk workspace ini —
   jadi artefak `ops/nginx/` belum bisa di-commit dan belum ada change record
   ber-versi, padahal plan mensyaratkannya. Perlu keputusan owner apakah
   `git init` dijalankan di sini.
2. **`tests/test_resume_integration.py` flaky.** Dua test gagal di `tearDown`
   dengan `OSError: [Errno 39] Directory not empty: '.jobs'` pada sebagian run
   (3 run berturut: gagal, lulus, gagal). Race antara job latar dan
   `TemporaryDirectory.cleanup()`. **Sudah ada sebelum sesi ini** dan tidak
   berhubungan dengan nginx, tapi membuat suite tidak bisa dipakai sebagai gate.
3. **Rotasi password root VPS** — pernah muncul di transkrip chat. Belum
   dirotasi; menunggu instruksi owner.
4. **`client_max_body_size 256k`** juga berlaku untuk `/automation/`. Import atau
   save workflow n8n yang besar akan gagal `413`. Bukan bagian dari outage yang
   dilaporkan, sengaja tidak diubah.
5. **CSP ketat** (`default-src 'self'`). Jika editor n8n masih ada bagian yang
   kosong setelah hard-refresh, periksa console browser untuk pelanggaran CSP
   **sebelum** menyentuh rate limit lagi.
6. Masih menggantung dari sesi sebelumnya: pembuatan akun owner n8n lewat UI,
   dan review `ops/n8n/workflow-templates/github-read-only-daily-status.json`
   dengan credential dedicated sebelum import.

## 6. Rollback

```sh
cp -p /etc/nginx/conf.d/agents-rate-limit.conf.bak-20260917T113952Z-rate \
      /etc/nginx/conf.d/agents-rate-limit.conf
cp -p /etc/nginx/sites-available/agents.nexoratech.co.bak-20260917T113952Z-ws \
      /etc/nginx/sites-available/agents.nexoratech.co
nginx -t && systemctl reload nginx
```

Backup sesi sebelumnya (`…bak-20260917-ratelimit`, `…bak-20260917-n8n`) tetap di
tempat sebagai anak tangga berikutnya. Rollback workspace penuh:
`/root/ah-workspace-backups/AI-Workspace-20260917T110041Z.tar.gz`.

## 7. Gerbang penerimaan

Owner melakukan **hard-refresh** pada:

1. `https://agents.nexoratech.co` — chip status harus terbaca `live …`, bukan
   `connecting…`, dan `<nav>` terisi.
2. `https://agents.nexoratech.co/automation/` — editor n8n ter-render.

Belum dinyatakan selesai hanya berdasar probe.

---

# Adendum — `/automation/` masih blank setelah perbaikan rate limit

**Waktu:** 2026-09-17 ~12:40 UTC, setelah owner melapor halaman masih putih.

## Koreksi terhadap verifikasi saya sendiri di §4

Di §4 saya mencatat *"6/6 aset yang dirujuk HTML n8n → 200 di loopback"* dan
menganggapnya lulus. **Itu salah.** Saya hanya memeriksa status code, tidak
memeriksa `Content-Type`. Semua aset itu memang membalas `200`, tapi isinya
`index.html`:

```
GET 127.0.0.1:5678/automation/assets/index-DbGpghR9.js  -> 200 text/html  56733 B
GET 127.0.0.1:5678/assets/index-DbGpghR9.js             -> 200 text/javascript  890935 B
```

## Akar masalah sebenarnya dari blank page

**n8n 2.39.6 menyajikan bundel-nya dari root server** (`/assets/`, `/static/`)
dan **tidak lagi** memasangnya di bawah `N8N_PATH`. `N8N_PATH=/automation/`
sekarang hanya menentukan prefix yang *dirujuk* oleh HTML. Karena vhost
meneruskan prefix apa adanya, setiap permintaan aset jatuh ke SPA catch-all dan
dibalas `index.html`; header `nosniff` lalu membuat browser menolak
mengeksekusinya. Hasilnya: halaman putih kosong, tanpa satu pun bundel jalan.

Ini **penyebab ketiga yang independen**, bukan sisa dari rate limit. Rate limit
(`429`) memang nyata dan sudah diperbaiki; ia menutupi cacat ini.

**Handoff sebelumnya menyatakan kebalikannya** — *"`proxy_pass` dengan trailing
slash akan memotong prefix `/automation/` dan mem-blank editor. Prefix wajib
utuh."* Klaim itu keliru untuk n8n 2.x, dan test yang saya tulis pagi ini ikut
mem-pin keyakinan salah tersebut. Test sudah dikoreksi berikut bukti
pengukurannya, supaya klaim itu tidak bisa kembali.

## Bukti sebelum menyentuh produksi

Chromium headless dipasang, lalu editor dimuat lewat **server block loopback
sementara** (`127.0.0.1:7996`, tanpa TLS, tanpa auth, tidak terjangkau dari
luar) yang memakai `proxy_pass …:5678/` **dan CSP produksi yang sama persis**:

```
#app children : 1
body text     : "Set up owner account / Email * / First Name * / ..."
RENDERED      : YES
CSP violations: 1  (import 'data:text/javascript,…' -- probe Vite, ditangkap Vite sendiri)
```

Kontrol: memuat n8n langsung di `127.0.0.1:5678/automation/` **tanpa nginx sama
sekali** → `RENDERED: NO (blank)`, 341 error `Failed to load module script:
… MIME type "text/html"`. Jadi blank page bukan ulah nginx, CSP, maupun auth.

**CSP produksi terbukti tidak bersalah** dan tidak dilonggarkan.

Blok staging sudah dihapus dan nginx di-reload; port 7996 tidak lagi listening.

## Perubahan produksi kedua

Backup: `agents.nexoratech.co.bak-20260917T124046Z-prefix`.

| Perubahan | Alasan |
|---|---|
| `proxy_pass http://127.0.0.1:5678;` → `…:5678/;` | memotong prefix `/automation/` sebelum upstream |
| tambah `location = /automation { return 301 …/automation/; }` | `^~ /automation/` tidak pernah cocok dengan URL tanpa trailing slash; tanpa ini URL itu jatuh ke upstream dashboard |

`nginx -t` lulus, `systemctl reload nginx` (graceful). Validator terhadap
konfigurasi live: OK. Probe rate limit diulang: **PASS 0/240**. Redirect
`/automation` → `/automation/` mengembalikan `301`.

## Test

`ops/nginx/tests/` naik dari 8 ke **10 test, semua hijau**:

- `test_automation_prefix_is_stripped_before_the_upstream` (menggantikan
  `test_automation_prefix_is_preserved_upstream` yang salah), memuat angka
  pengukurannya sebagai komentar;
- `test_a_vhost_that_keeps_the_prefix_is_rejected`;
- `test_bare_automation_redirects_to_the_trailing_slash_form`.

`verify_rate_limit.sh` kini juga memeriksa `Content-Type` aset bila diberi
credential — tanda-tangan blank page (`200 text/html` pada `.js`) akan
menggagalkannya:

```sh
AUTH=user:pass ./ops/nginx/verify_rate_limit.sh
```

## Status fungsi AH

Semua sehat, diperiksa lewat `127.0.0.1:7777/api/state` dan journal:

| | |
|---|---|
| `ah-dashboard`, `ah-telegram` | `active/running`, log bersih, `NRestarts=0` |
| `ah-resume.timer` | aktif, terakhir jalan 12:10 UTC, berikutnya 13:10 UTC |
| n8n automation | `ok` — loopback verified |
| backup harian | `ok` — systemd timer aktif |
| kapasitas disk | `ok` — 63 GB free, 33% terpakai |
| engine | `claude` terautentikasi; **`codex` tidak** (`codex_auth=false`, binary tidak ditemukan) |
| `gh` CLI | **tidak terpasang** |
| task | 29 total — 9 planned, 0 active, 20 reported |
| agents, triggers | 7 role termuat; 4 trigger aktif |

Dua job tercatat: satu `done`, satu `failed` (`101013-2ce5`, 16/09). Belum
ditelusuri — di luar cakupan sesi ini.

**Belum jalan (bukan kerusakan, memang belum dikerjakan):** akun owner n8n belum
dibuat — halaman yang ter-render adalah form "Set up owner account". Sampai itu
diisi, automation belum bisa dipakai.

## Yang masih belum bisa saya verifikasi sendiri

Fetch terautentikasi lewat produksi butuh password Basic Auth user `imam`
(bcrypt, tidak dapat dipulihkan). Rendering sudah dibuktikan pada blok staging
dengan direktif dan CSP identik, dan validator lulus terhadap konfigurasi live —
tapi bukti end-to-end lewat `https://agents.nexoratech.co/automation/` masih
menunggu password itu atau hard-refresh dari owner.

## Rollback adendum ini

```sh
cp -p /etc/nginx/sites-available/agents.nexoratech.co.bak-20260917T124046Z-prefix \
      /etc/nginx/sites-available/agents.nexoratech.co
nginx -t && systemctl reload nginx
```

---

# Adendum 2 — verifikasi end-to-end di browser produksi, dan dua cacat lagi

**Waktu:** 2026-09-17 ~12:50–13:00 UTC. Owner memberikan credential Basic Auth,
jadi seluruh rantai akhirnya bisa dibuktikan dari sisi saya.

## Adendum 1 belum cukup — dua cacat tambahan muncul

Memuat `https://agents.nexoratech.co/automation/` di chromium headless dengan
credential: **masih blank**, dengan `3202 × 429` dan `629 × 503`. Perbaikan
prefix sudah benar, tapi limitnya salah ukuran.

Sumbernya satu: **saya menurunkan angka dari estimasi handoff ("40+ chunk"),
bukan dari pengukuran.** Dengan limit dinaikkan sementara untuk mengukur, satu
cold load editor ternyata **797 request** (794 × 200) — lebih dari sepuluh kali
lipat estimasi itu.

### Cacat 4 — `limit_req` salah ukuran

`rate=10r/s` + `burst=200` tidak cukup untuk 797 request. Dinaikkan ke
`rate=50r/s` + `burst=1200`: reservoir menampung satu cold load utuh, refill
membawa satu cold load penuh tiap 16 detik.

### Cacat 5 — `limit_conn` bertabrakan dengan HTTP/2

Setelah 429 hilang, muncul `407 × 503`. Pada nginx 1.24 dengan HTTP/2,
`limit_conn` menghitung **setiap stream** sebagai satu koneksi, dan browser
membuka stream sebanyak `http2_max_concurrent_streams` mengizinkan (default 128).
Batas `10` — dan kemudian `64` — pasti tertabrak oleh page load biasa.

Terukur, satu editor load masing-masing:

| `limit_conn` | hasil |
|---|---|
| 10 | 629 × 503 |
| 64 | 407 × 503 |
| 256 | **0 × 503, editor render** |

Diperbaiki dengan memasang **keduanya sebagai satu keputusan**:
`http2_max_concurrent_streams 128` di-pin eksplisit (bukan warisan default), dan
`limit_conn agents_conn_per_ip 256` menjaga headroom 2×.

### Cacat 6 (kosmetik) — favicon dashboard

`img-src` jatuh ke `default-src 'self'`, memblokir favicon inline-SVG dashboard.
Ditambahkan `img-src 'self' data:` — satu-satunya pelonggaran CSP yang pernah
dilakukan. `script-src` tetap same-origin, `'unsafe-eval'` tetap tidak ada.

## Hasil akhir, diukur di produksi

```
https://agents.nexoratech.co/automation/
  RENDERED       : YES        ("Set up owner account")
  797 request    : 794x200, 3x401, 0x429, 0x503
  CSP violations : 1   (probe Vite `import 'data:text/javascript,…'`, ditangkap Vite)

https://agents.nexoratech.co/
  chip           : "live 12:57:43 PM"   (sebelumnya beku di "connecting…")
  nav            : terminal · floor 2 · tasks 29 · monitor · triggers 4 · activity
  CSP violations : 0        JS errors : 0
```

Tiga `401` itu wajar: challenge auth awal, satu aset sebelum credential
terpasang, dan `/automation/rest/login` — n8n memang membalas 401 selama akun
owner belum dibuat.

`AUTH=… ./ops/nginx/verify_rate_limit.sh` → **PASS**, 0/240 rate-limited, seluruh
aset dengan `Content-Type` sebenarnya.

Test `ops/nginx/`: **14 hijau**. Konfigurasi live identik byte-per-byte dengan
artefak repo. Validator terhadap live: OK.

## Penyebab job `failed` — terjawab

Dashboard menampilkan alasannya langsung pada job `101013-2ce5`:
*"You've hit your individual spend limit — ask your admin to raise it at
claude.ai/admin-settings/usage · your weekly limit resets 9am (UTC)."*
Bukan kerusakan harness.

## Pelajaran yang dipin ke test

1. **Ukur, jangan estimasi.** Tiga pass berturut-turut gagal karena angka limit
   diturunkan dari perkiraan. Angka 797 sekarang jadi konstanta
   `EDITOR_COLD_LOAD_REQUESTS` dengan `MIN_BURST` dan `MIN_SUSTAINED_RPS`
   diturunkan darinya.
2. **Status code bukan verifikasi.** `200` dengan `Content-Type: text/html` pada
   `.js` adalah tanda-tangan blank page. Sekarang diperiksa oleh probe.
3. **Blank page ≠ CSP.** Tiga kali berturut-turut CSP jadi tersangka dan tiga
   kali tidak bersalah. Komentar di vhost melarang melonggarkannya hanya karena
   halaman terlihat kosong.

## Backup (urut waktu)

```
conf.d/agents-rate-limit.conf.bak-20260917T113952Z-rate
conf.d/agents-rate-limit.conf.bak-20260917T125451Z-sized
sites-available/agents.nexoratech.co.bak-20260917T113952Z-ws
sites-available/agents.nexoratech.co.bak-20260917T124046Z-prefix
sites-available/agents.nexoratech.co.bak-20260917T125451Z-sized
sites-available/agents.nexoratech.co.bak-20260917T125619Z-conn
sites-available/agents.nexoratech.co.bak-20260917T125725Z-csp
```

## Wajib ditindaklanjuti owner

1. **Rotasi credential Basic Auth `imam`** — dikirim lewat chat atas permintaan
   saya, jadi kini ada di transkrip. Sama statusnya dengan password root.
2. **Buat akun owner n8n** di `https://agents.nexoratech.co/automation/` —
   halaman sudah render dan menunggu diisi.
3. Chromium headless (165 MB) terpasang di `/root/.cache/ms-playwright` untuk
   verifikasi ini. Dibiarkan terpasang supaya regresi berikutnya bisa dicek
   dengan cara yang sama; hapus bila tidak diinginkan.

---

# Adendum 3 — akun owner n8n dibuat, rantai penuh terverifikasi

**Waktu:** 2026-09-17 ~13:20 UTC. Owner mendaftarkan akun n8n.

## Verifikasi

Login lewat REST melalui nginx:

```
POST https://agents.nexoratech.co/automation/rest/login  -> 200
  role=global:owner  isOwner=true  email=imam.nurokhi@nexoratech.co
  set-cookie: n8n-auth=…; Path=/; HttpOnly; Secure; SameSite=Lax
GET  /automation/rest/workflows -> 200 application/json
GET  /automation/rest/settings  -> 200 application/json
```

Lalu di chromium headless, login lewat form dan buka kanvas workflow baru:

```
POST /rest/login   -> 200
url after login    : /automation/assistant
canvas url         : /automation/workflow/QaK7iI90iGlyqYcq?new=true
canvas text        : Personal / My workflow · Publish · Editor · Executions ·
                     Evaluations · Add first step… · Logs
page errors        : none
1716 request       : 1705x200, 9x401, 0x429, 0x503
```

**Push channel WebSocket tersambung** — dua `101 Switching Protocols` ke
`wss://agents.nexoratech.co/automation/rest/push?pushRef=…`. Ini bukti produksi
untuk perbaikan header `Upgrade`/`Connection` di Adendum 1; sebelumnya vhost
tidak pernah meneruskannya sama sekali.

1716 request dalam satu sesi (login + kanvas) juga menegaskan ukuran limit yang
baru memadai: dua kali lipat cold load 797, tetap nol `429` dan nol `503`.

## Kebersihan

Draft workflow yang dibuat probe tidak pernah tersimpan —
`GET /rest/workflows` mengembalikan **0 workflow**. Tidak ada sisa.

## Catatan

`createdAt` akun adalah `2026-09-16T19:25:38Z`, jadi akun owner sebenarnya sudah
pernah dibuat sehari sebelumnya; form "Set up owner account" yang terlihat pada
Adendum 2 adalah karena pendaftaran saat itu belum pernah selesai dari browser
yang bisa memuat aset. `settings.userActivated` masih `false`.

## Wajib dirotasi (bertambah satu)

1. Password root VPS.
2. Credential Basic Auth `imam`.
3. **Password akun n8n `imam.nurokhi@nexoratech.co`** — dikirim lewat chat,
   sekarang ada di transkrip.

Ketiganya pernah melewati transkrip percakapan dan harus diganti.
