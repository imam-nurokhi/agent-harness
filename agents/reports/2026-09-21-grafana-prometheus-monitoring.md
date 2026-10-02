# 2026-09-21 — Monitoring tersambung: Prometheus sekarang, Grafana menunggu satu token

**Diminta owner:** sambungkan Grafana (`monitoring.nexoratech.co/dashboards`)
untuk kebutuhan monitoring, reporting, development, dan kebutuhan berikutnya;
integrasikan juga ke telegrambot.

**Hasil:** `/monitor` hidup di `@AgentNexoraBot` dan sudah mengirim laporan
nyata. Sumber datanya **Prometheus**, bukan Grafana — dan itu keputusan sadar
yang membuat fiturnya bisa jalan hari ini juga, bukan menunggu kredensial.

---

## 1. Yang ternyata sudah ada di host ini

Seluruh stack observability berjalan di server yang sama, dan harness tidak
tahu apa-apa soal itu:

| Komponen | Port | Auth |
|---|---|---|
| Grafana 13.2.0 | 3000 | **perlu token** (`/api/search` → 401) |
| Prometheus | 9090 | terbuka |
| Loki | 3100 | terbuka (saat dicek: `Ingester not ready`) |

Isinya jauh lebih kaya dari dugaan: **32 target scrape, semuanya up** — 17 probe
HTTP blackbox, 12 node exporter, MikroTik SNMP + flow.

**Temuan yang paling layak dicatat:** `docs/nexora-cbqa-cloud-operations-plan.md`
item #5 menyebut uptime dan SSL "belum tercakup sama sekali". Keduanya
sebenarnya **sudah diukur sejak lama** — 17 probe uptime dan 11 sertifikat
dengan sisa hari — hanya tidak pernah dibaca siapa pun. Yang kurang bukan
monitoring-nya, melainkan jembatan ke tempat orang membaca.

## 2. Kenapa Prometheus, bukan Grafana

Grafana menyimpan dashboard dan aturan alert; Prometheus menyimpan **angkanya**.
Setiap dashboard di Grafana menggambar dari deret yang sama.

- Prometheus tidak butuh kredensial → fitur bisa dibangun dan diuji sekarang.
- Grafana butuh service-account token → kalau dipakai sebagai sumber utama,
  seluruh pekerjaan ini akan tertahan menunggu satu token.
- Prometheus **tidak punya satu pun aturan alert** (0 grup, 0 aturan). Jadi
  alerting memang hidup di Grafana, dan status alert baru terbaca setelah
  tokennya ada.

Karena itu Grafana dipakai hanya untuk yang hanya ia tahu — daftar dashboard dan
alert — lewat `GRAFANA_TOKEN` opsional, dan setiap fungsinya **turun kelas
dengan jujur** ("belum tersambung") alih-alih gagal.

Sepanjang pekerjaan ini tidak ada satu pun operasi tulis: tidak membuat aturan,
tidak membuat silence, tidak menyentuh dashboard. Stack monitoring milik vhost
yang dipakai bersama (CLAUDE.md §1); harness adalah pembaca di sana.

## 3. Yang dibangun

`bin/lib/metrics.py` — klien Prometheus tipis + fungsi bentukan murni, dan
perintah `/monitor` (level **viewer**, sama seperti `/ops`).

Hasil nyata pertama:

```
🟢 Monitoring — sehat
Situs: 17/17 up
SSL terdekat: https://auth.cbqaglobal.co.id — 31 hari
Disk tertinggi: audit-q.cbqaglobal.co.id 84.2%
RAM tertinggi: OneAlpha 64.4%
Target scrape: 32/32 up
```

Deterministik dan gratis: tidak memakai kuota engine dan tidak bisa mengarang
angka — alasan yang sama yang membuat `/weekly` dan `/daily` jadi kode harness,
bukan agent run.

### Keputusan desain yang diuji

| Perilaku | Kenapa |
|---|---|
| Prometheus tak terjangkau → "status tidak diketahui", bukan hijau | Monitor yang gagalnya berupa centang hijau lebih buruk daripada tidak ada monitor |
| Ambang sengaja pendiam: SSL 21 hari, disk 85%, RAM 90% | Workspace ini sudah dua kali membayar mahal karena alarm yang berbunyi tiap hari lalu diabaikan |
| Probe/target turun mengalahkan segalanya jadi "turun" | Satu kata yang bisa ditindaklanjuti sebelum membaca detail |
| Daftar dipotong 5 baris per kategori | Pesan harus muat di HP; ada tes yang menjaga <3800 karakter |

Tes: `tests/test_metrics.py` (23), ditulis mengikuti arah kegagalan — bukan
jalur bahagia. Satu cacat nyata tertangkap saat render data asli pertama kali:
label instance di Prometheus ini berupa prosa (`Server Production
audit-q… (148.230.96.117)`, `Server Development OneAlpha`), dan pemendek host
hanya mencocokkan literal "Server Production" sehingga host Development tidak
ikut dipendekkan. Diperbaiki dengan mencocokkan kata lingkungan sebagai kelas.

## 4. Yang dibutuhkan untuk bagian Grafana

Satu hal, dan hanya owner yang bisa membuatnya:

1. Buka `monitoring.nexoratech.co` → **Administration → Service accounts**
2. Buat service account (peran **Viewer** sudah cukup — harness hanya membaca)
3. **Add service account token**, salin nilainya
4. Tempel ke `/home/ahagent/AI-Workspace/.env` sebagai `GRAFANA_TOKEN=...`
   (langsung di server, jangan lewat chat — CLAUDE.md §9)

Setelah itu `/monitor` otomatis menambahkan jumlah dashboard dan alert aktif;
tidak ada yang perlu diubah di kode.

## 5. Gate

| Suite | Hasil |
|---|---|
| `tests` | **457** OK (dari 434; +23 metrics) |
| `ops/harness` · `nginx` · `n8n` · `feedback` | 11 · 20 · 10 · 29 OK |
| Nyata | `/monitor` terkirim ke Telegram owner, angka dari Prometheus hidup |

## 6. Berikutnya, kalau diinginkan

1. **Token Grafana** (§4) — membuka daftar dashboard dan status alert.
2. **Alert masuk ke Telegram.** Setelah token ada, alert Grafana bisa dibaca
   berkala dan dikirim **sekali per perubahan status**, memakai pola dedup yang
   sudah terbukti di `resumerun.should_announce` — bukan pengulangan tiap tick.
3. **Sisipkan ringkasan monitoring ke laporan 07:30** yang sudah berjalan,
   supaya kesehatan infrastruktur ikut terbaca bersama progres sprint.
4. **Loki** (`Ingester not ready` saat dicek) layak dilihat terpisah; kalau
   sehat, ia membuka pencarian log lintas host lewat harness.
