# Handoff — agents.nexoratech.co outage: root cause + rencana lanjutan

**Tanggal:** 2026-09-17
**Status:** diagnosis selesai & terbukti; **belum ada perubahan di VPS pada sesi ini**
**Lanjutan dari:** `agents/reports/2026-09-17-cloud-ops-continuation-progress.md`
**Plan induk:** `docs/nexora-cbqa-cloud-operations-plan.md`

---

## 1. Gejala yang dilaporkan owner

- `https://agents.nexoratech.co` — shell ter-render, tapi chip status beku di
  **"connecting…"**, tidak ada data yang masuk, `<nav>` kosong.
- `https://agents.nexoratech.co/automation/` — **blank page**.

## 2. Root cause (terbukti, bukan dugaan)

Agent sebelumnya sudah mendiagnosis rate limit nginx dan menaikkan
`burst=30` → `burst=200` pada vhost, lalu `nginx -t` + `systemctl reload nginx`.
Sesi itu terputus **sebelum verifikasi** — laporannya sendiri mencatat
"belum diverifikasi pasca-reload".

Verifikasi dilakukan sesi ini **dari luar, tanpa credential**. Host membalas
`401` untuk auth gagal dan `429` untuk penolakan rate limit, sehingga keduanya
dapat dibedakan tanpa Basic Auth. Empat gelombang berturut-turut, masing-masing
60 request paralel ke `/automation/assets/<unik>.js`:

| wave | hasil |
|---|---|
| 1 | 60 × 401 |
| 2 | 60 × 401 |
| 3 | 60 × 401 |
| 4 | 29 × 401, **31 × 429** |

**Akar masalahnya: burst dinaikkan, sustained rate tidak.**
`conf.d/agents-rate-limit.conf` masih `rate=60r/m` — satu request per detik.
`burst=200` hanya reservoir sekali pakai: habis setelah ~3 page-load, lalu isi
ulang 1 r/s. Satu kali buka editor n8n menembak 40+ chunk JS paralel, dan
dashboard menembak `dash.js` + `/api/state` tiap 4 detik, jadi pemakaian normal
menghabiskannya lagi dalam hitungan menit. Fix sebelumnya = tambal, bukan akar.

### Pemetaan gejala → penyebab (diverifikasi terhadap kode klien)

- `bin/lib/dash.html:20` mengirim teks literal `connecting…`. `bin/lib/dash.js`
  hanya menggantinya menjadi `live …` (dash.js:300) atau `disconnected`
  (dash.js:303). Jadi `connecting…` yang beku berarti **dash.js sendiri tidak
  pernah dieksekusi** — request script-nya yang ditolak (429), bukan
  `/api/state` yang gagal. Ini sekaligus menjelaskan `<nav>` kosong di screenshot.
- Editor n8n blank dengan mekanisme yang sama: chunk asset-nya ditolak 429.

## 3. Gap tata kelola yang ikut ditemukan

vhost `agents` dan zone rate-limit-nya **hanya ada di VPS**. Tidak ada satu pun
salinan di repo → tidak ada artefak yang bisa direview, tidak ada test, tidak ada
change record. Ini melanggar acceptance criteria plan sendiri: *"Tidak ada
layanan existing pada 31.97.67.241 yang berubah tanpa approval dan change record."*

## 4. Yang sudah dikerjakan sesi ini

| Item | Status |
|---|---|
| Probe 4-wave dari luar (bukti 429) | selesai |
| Pelacakan gejala ke `dash.js` / `dash.html` | selesai |
| `ops/nginx/tests/test_validate_vhost.py` | dibuat, **sengaja RED** (`ModuleNotFoundError: validate_vhost`) |
| Perubahan apa pun di VPS | **tidak ada** |

Test itu satu-satunya file yang dibuat. Ia mem-pin perilaku yang penting:
bentuk yang ter-deploy sekarang (`rate=60r/m` + `burst=200`) harus **ditolak**;
artefak yang di-commit harus **diterima**; `/automation/` harus mempertahankan
prefix path ke upstream; `Upgrade`/WebSocket, `auth_basic`, `limit_conn`, dan
security header tetap wajib — fix tidak boleh melonggarkan apa pun yang sudah
dikeraskan.

## 5. Rencana pengerjaan lanjutan

### Langkah 1 — artefak repo + validator (lokal, tanpa VPS)

Tulis, berurutan, sampai test hijau:

1. `ops/nginx/validate_vhost.py` — `validate(zone_text, vhost_text) -> list[str]`
   plus `sustained_rate_per_second()`. Gaya mengikuti `ops/n8n/validate_env.py`:
   fungsi murni, mengembalikan daftar string masalah, tanpa I/O.
   Konstanta: `RATE_TOO_LOW`, `NO_WEBSOCKET`, `NO_AUTH`, `NO_CONN_LIMIT`,
   `MISSING_HEADER`, `MIN_SUSTAINED_RPS`.
2. `ops/nginx/agents-rate-limit.conf` — sustained rate naik ke **`10r/s`**
   (600r/m). Nama zone dan `limit_conn_zone` **tidak diubah** supaya vhost tetap
   jalan. 10 r/s menyerap satu load editor penuh per detik tapi tetap menahan
   abuse terskrip; `limit_conn` tetap jadi penjaga konkurensi yang sebenarnya.
3. `ops/nginx/agents.nexoratech.co.conf` — vhost hasil review: TLS, `auth_basic`,
   `limit_req … burst=200 nodelay`, `limit_conn`, security header yang sudah ada,
   `location /` → `127.0.0.1:7777`, `location /automation/` → `127.0.0.1:5678`
   dengan prefix dipertahankan dan `Upgrade`/`Connection` diteruskan.
4. `ops/nginx/README.md` — isi file, prosedur deploy, rollback, dan catatan tegas
   bahwa perubahan ini satu-satunya yang menyentuh host produksi bersama ini.

**Catatan penting:** `proxy_pass http://127.0.0.1:5678/;` (dengan trailing slash)
akan **memotong** prefix `/automation/` dan mem-blank editor, karena n8n jalan
dengan `N8N_PATH=/automation/` (lihat `ops/n8n/.env.example`). Prefix wajib utuh.

Gate hijau: `python3 -m unittest discover -s ops/nginx/tests`, ditambah suite
`tests/` (200) dan `ops/n8n/tests` (10) yang tetap lulus.

### Langkah 2 — skrip probe eksternal

`ops/nginx/verify_rate_limit.sh` — menjalankan probe 4-wave di atas terhadap host
publik dan gagal bila muncul `429`. Tidak butuh Basic Auth, jadi aman di-rerun
dan aman diserahkan ke owner. Sekarang skrip ini adalah bukti bahwa konfigurasi
ter-deploy masih rusak; setelah perbaikan ia harus balik semua-`401`.

### Langkah 3 — perubahan di VPS (satu file, di-backup, reload bukan restart)

Read-only dulu, lalu tepat satu edit:

1. Snapshot `conf.d/agents-rate-limit.conf` dan vhost yang live; diff terhadap
   artefak repo dan rekonsiliasi drift **sebelum** mengubah apa pun. Salinan di
   repo masih rekonstruksi sampai langkah ini mengonfirmasinya.
2. Jalankan `validate_vhost.py` terhadap teks yang live untuk memastikan ia
   menandai akar masalah yang sama dengan yang disimpulkan dari luar.
3. Backup ke `…conf.bak-<timestamp>-rate`, ubah **hanya** nilai `rate=` di
   `agents-rate-limit.conf`, `nginx -t`, `systemctl reload nginx` (graceful — tanpa
   restart, tanpa menyentuh vhost lain).
4. Bila ternyata vhost live memotong prefix `/automation/`, perbaiki di pass yang
   sama; kalau tidak, file vhost tidak disentuh.

**Tidak disentuh sama sekali:** container n8n/PostgreSQL dan compose stack-nya,
backup timer, service `ah-dashboard` / `ah-telegram` / `ah-resume.timer`, seluruh
vhost lain (`dev-kemenkes`, `dev-support`, `monitoring`, …), dan semua credential.

### Langkah 4 — verifikasi (semua wajib lulus sebelum dinyatakan selesai)

1. `ops/nginx/verify_rate_limit.sh` → 240/240 `401`, nol `429`.
2. Loopback di VPS: `127.0.0.1:7777/api/state` → 200 JSON,
   `127.0.0.1:5678/healthz` → 200.
3. Fetch terautentikasi lewat proxy untuk `/dash.js` dan HTML root editor n8n →
   200, dan path asset yang dirujuk HTML itu resolve di bawah `/automation/`.
   Ini tes langsung untuk blank page.
4. `grep 429 /var/log/nginx/access.log` pada jendela probe → tidak ada setelah reload.
5. Owner hard-refresh kedua URL dan mengonfirmasi chip terbaca `live …` dan
   editor n8n ter-render. **Ini gerbang penerimaannya** — tidak dinyatakan selesai
   hanya berdasar probe.
6. Suite lokal hijau; working tree bersih.

### Langkah 5 — pencatatan

- Commit artefak `ops/nginx/` + test (`fix(ops): …`) dengan trailer co-author
  sesuai aturan workspace. **Tanpa push** — repo tidak punya remote, dan push
  hanya ke `dev`/`staging` dengan persetujuan owner.
- Update `docs/nexora-cbqa-cloud-operations-plan.md` (verification record) dan
  tulis laporan sesi baru di `agents/reports/` yang menyatakan perilaku hasil
  sebenarnya, perintah rollback, dan item yang masih menggantung.

## 6. Rollback

```sh
cp -p /etc/nginx/conf.d/agents-rate-limit.conf.bak-<timestamp>-rate \
      /etc/nginx/conf.d/agents-rate-limit.conf
nginx -t && systemctl reload nginx
```

Backup vhost dari sesi sebelumnya
(`/etc/nginx/sites-available/agents.nexoratech.co.bak-20260917-ratelimit`) tetap
di tempat sebagai anak tangga kedua.

## 7. Blocker

SSH `root@31.97.67.241` ditolak (`publickey,password`) — tidak ada key maupun
entry di `~/.ssh/config`. Butuh password root **atau**, lebih baik, pemasangan
SSH key sekali supaya sesi berikutnya tidak perlu credential lewat transkrip.

Langkah 1, 2, dan separuh lokal langkah 4 bisa jalan tanpa akses itu.

## 8. Masih menggantung dari sesi sebelumnya (di luar cakupan sesi ini)

1. Rotasi password root VPS (pernah muncul di chat) dan credential bootstrap
   Basic Auth dashboard.
2. Pembuatan akun owner n8n lewat UI.
3. Review `ops/n8n/workflow-templates/github-read-only-daily-status.json` dengan
   credential dedicated sebelum import/aktivasi.
