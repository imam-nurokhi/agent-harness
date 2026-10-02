# Analisa — agent berhenti di Slack, dan penyesuaian yang dilakukan

**Tanggal:** 2026-09-17
**Pemicu:** run lead agent diminta meringkas `#daily-updates` dan berhenti dengan
laporan blocker.

---

## 1. Laporan agent itu benar

Saya verifikasi sendiri tiap klaimnya, tidak menerimanya begitu saja:

| Klaim agent | Hasil verifikasi |
|---|---|
| `operations.py` hard-code Slack `not-configured` | **benar** — `bin/lib/operations.py:66` |
| Tidak ada credential Slack di workspace | **benar** — nol kecocokan di `.env` |
| Hanya artefak Slack adalah kontrak NEXONE/SUPPORT | **benar** |
| Tidak ada tool Slack untuk agent | **benar** — `mcpServers` tidak ada di settings harness |

Agent berhenti alih-alih mengarang isi channel. Itu perilaku yang benar dan
tidak perlu "diperbaiki".

## 2. Dua hal yang agent tidak bisa ketahui

**a. Sesi orkestrator punya akses Slack.** Agent menulis *"No Slack MCP/API tool
is available to me or any sub-agent"* — benar untuk dirinya, tapi
digeneralisasi terlalu jauh. Sesi Claude Code yang menjalankannya punya
konektor Slack, dan `#daily-updates` (`C0BPCCAQ8KC`) langsung terbaca.
Ringkasan minggu ini sudah dikirim ke Telegram dari situ.

**b. Rencananya tidak akan jalan apa adanya.** Agent mengusulkan *"Task 2: fetch
via Slack conversations.history API"* sebagai tugas agent. Tapi
`ops/harness/claude-settings.json` **menolak `curl` dan `wget`**. Agent itu akan
menabrak tembok kedua setelah tembok pertama dibuka.

## 3. Penyesuaian: ini bukan pekerjaan agent sama sekali

Rencana agent memerlukan tiga tugas dan dua engine run untuk membaca sebuah
channel dan meneruskannya. Itu bentuk yang salah. Sama seperti `/weekly`,
membaca Slack adalah **kapabilitas harness deterministik**:

- jalan di dalam proses bot, jadi **tidak ada gerbang izin** — persis yang
  menghentikan agent tadi;
- **nol engine spend**, relevan karena akun ini sudah kena spend limit;
- tidak bisa mengarang update yang tidak ditulis siapa pun.

### Yang dibangun

| Berkas | Isi |
|---|---|
| `bin/lib/slackread.py` | pembaca channel + renderer deterministik |
| `bin/lib/tgcmd.py` | perintah `/daily` (level operator) |
| `bin/lib/operations.py` | status Slack diturunkan, bukan hard-code |
| `tests/test_slack_daily.py` | **29 test** |
| `.env.example` | scope yang dibutuhkan dan cara memperolehnya |

Keputusan desain yang perlu dinyatakan terbuka: ia **mengelompokkan dan
mengatribusi, bukan memparafrase**. Laporan deterministik tidak bisa mengarang,
dan pembaca melihat persis siapa menulis apa. Kalau suatu saat perlu narasi
sungguhan, itu tugas agent **di atas** data ini — bukan mengubah modul ini.

Detail yang ikut ditangani:
- `users:read` adalah scope terpisah. Tanpa itu laporan tetap jalan, hanya
  menampilkan user id — kehilangan sebuah post karena namanya tidak tersedia
  jauh lebih buruk.
- Token dikirim di header `Authorization`, **tidak pernah di URL** — query string
  berakhir di log proxy. Dipin oleh test.
- Markup Slack (`<@U123|Nama>`, `<https://x|label>`) dirapikan, dan HTML
  di-escape supaya Telegram tidak menolak pesannya.
- Minggu dihitung dari **Senin**, bukan "7 hari ke belakang", agar sejajar
  dengan minggu kerja yang dibicarakan orang.

### `/ops` tidak lagi berbohong

`operations.py` menyatakan Slack `not-configured` tanpa syarat. Begitu token
dipasang, itu akan jadi klaim palsu. Sekarang statusnya diturunkan dari
konfigurasi, dan test memastikan **token tidak pernah muncul di permukaan**.

## 4. Sisa satu langkah — hanya Anda yang bisa

`SLACK_DAILY_CHANNEL_ID=C0BPCCAQ8KC` sudah saya isikan di `.env` (channel id
bukan rahasia — ada di permalink channel). Yang kurang tinggal:

```
SLACK_BOT_TOKEN=xoxb-…
```

Scope bot: `channels:history`, `channels:read`, dan `users:read` (opsional).
Bot harus di-invite ke channel. Lalu `systemctl --user restart ah-telegram`.

Sengaja **tidak** saya minta lewat chat: tiga credential sudah lewat transkrip
dan menunggu rotasi. Tempelkan langsung ke `.env` di server.

Sampai itu ada, `/daily` menjawab dengan instruksi setup, bukan traceback.

## 5. Isi channel minggu ini (14–17 Sep)

Dikirim ke Telegram. Ringkasnya:

- **Senin 14 Sep: tidak ada pesan sama sekali.**
- Rabu: Imam minta update — 2 dari 3 orang menjawab.
- Kamis: huddle, lalu daily closing; ketiganya melapor.
- **Keputusan:** API dikonsolidasi di satu host (`dev-apiv2.nexoratech.co`),
  dibedakan lewat path `/apis` — bukan per aplikasi. Rafif dapat tugas prototype
  Client Audit Monitoring Portal di OneConnect.
- **Menggantung:** pertanyaan Imam soal VPS untuk 5 domain dev tidak dijawab
  Rafli (pesan terakhir hanya *"pliii"*); pertanyaan Diky soal module drafting
  dokumen tidak pernah ditindaklanjuti; Rafli melapor 1 dari 3 hari.

## 6. Test

| suite | sebelum | sesudah |
|---|---|---|
| `tests/` | 266 | **291** |
| `ops/harness/tests` | 11 | 11 |
| `ops/nginx/tests` | 14 | 14 |
| `ops/n8n/tests` | 10 | 10 |

## 7. Rollback

Hapus `SLACK_BOT_TOKEN` dari `.env` dan restart `ah-telegram`: `/daily` kembali
melaporkan dirinya belum terkonfigurasi, `/ops` kembali `not-configured`, dan
tidak ada jalur lain yang terpengaruh.
