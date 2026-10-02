# 2026-09-21 — Laporan sprint terjadwal: kenapa bukan routine cloud

**Diminta owner:** jadwalkan laporan ringkas sprint dari NEXONE + Slack, setiap
hari kerja pukul 07.30 WIB, dikirim ke telegrambot. Permintaan datang lewat
`/schedule`, yang membuat **routine cloud**.

**Hasil:** dijadwalkan, berjalan, dan sudah terkirim sekali sebagai bukti —
tetapi **sebagai timer di server ini, bukan routine cloud**, karena routine
cloud secara struktural tidak bisa mengerjakannya. Bagian Slack sengaja
dikecualikan dan dinyatakan terbuka di dalam pesannya sendiri.

---

## 1. Kenapa routine cloud bukan alatnya

Routine `/schedule` berjalan di infrastruktur Anthropic, dengan checkout git
sendiri dan tanpa akses apa pun ke host ini. Tugas yang diminta membutuhkan tiga
hal, dan routine cloud hanya punya satu:

| Kebutuhan | Tersedia di cloud? |
|---|---|
| Kredensial NEXONE (`NEXONE_EMAIL`/`NEXONE_PASSWORD`) | **Tidak** — hanya ada di `.env` server |
| Token bot Telegram untuk mengirim hasilnya | **Tidak** — sama, hanya di `.env` server |
| Akses Slack | Ya, lewat konektor MCP |

Satu-satunya cara memberi routine cloud dua hal pertama adalah menaruh kredensial
ke dalam konfigurasi routine. Itu memindahkan rahasia ke tempat baru yang bisa
dibaca ulang, persis kebiasaan yang membuat tiga kredensial di CLAUDE.md §9
sekarang menunggu rotasi. Tidak dilakukan.

Jadi routine cloud bisa membaca Slack tetapi **tidak punya tempat untuk
mengirimkan hasilnya**, dan tidak bisa membaca sumber utamanya. Data dan jalur
pengirimannya sama-sama ada di server ini, jadi jadwalnya juga di sini.

## 2. Yang dibangun

`bin/sprint_report.py` + `ah-sprint-report.timer`:

- **OnCalendar `Mon..Fri 07:30 Asia/Jakarta`**, `Persistent=true`. Zona waktu
  dipatok karena jam server UTC — tanpa itu "07:30" jadi 14:30 WIB (CLAUDE.md §7).
  `Persistent` berarti hari kerja yang terlewat karena reboot tetap dikirim,
  bukan dilewati diam-diam.
- **Membaca NEXONE lewat Playwright**, menyetir form login sungguhan, sesuai
  preferensi owner (memory `nexone-ui-automation-playwright`). Token NEXONE ada
  di `sessionStorage`, jadi klien HTTP terpisah justru memaksa jalur API
  hasil rekayasa-balik yang diminta dihindari.
- **Read-only by construction**: tidak ada satu pun POST/PUT/PATCH/DELETE.
- **Memilih sprint berdasarkan status dan tanggal**, bukan nama. Mengganti nama
  sprint tidak akan mematahkan laporan.
- **Gagal dengan berisik**: bila NEXONE tidak bisa dibaca, owner dikirimi pesan
  kegagalan dan unit keluar non-nol. Laporan terjadwal yang gagal diam-diam
  adalah pola kegagalan yang berulang kali dipelajari workspace ini.

### Playwright untuk service user

Browser Playwright yang dipakai manual ada di `/root/.cache/ms-playwright`, dan
`/root` ber-mode `700` — tidak terbaca oleh `ahagent`. Karena itu dibuat venv
user-scoped di `/home/ahagent/.venvs/nexone` beserta chromium-nya sendiri.
Terkurung di home service user, bukan perubahan host-wide — pola yang sama
dipakai saat memasang Bun untuk channel plugin.

`PrivateTmp` sengaja **tidak** dipasang di unit ini: chromium butuh `/tmp` yang
bisa dibagi dengan proses anaknya.

## 3. Bagian Slack: terbuka, dan dikatakan terbuka

`SLACK_BOT_TOKEN` tidak ada di `.env` (CLAUDE.md §11 sudah mencatatnya). Tanpa
token itu, **proses tak berpengawas tidak bisa membaca kanal Slack sama sekali** —
konektor MCP hanya hidup di sesi orkestrator, bukan di timer.

Yang tidak dilakukan: diam-diam mengirim laporan NEXONE saja seolah itulah yang
diminta. Pesannya menutup diri sendiri dengan catatan bahwa bagian Slack belum
termasuk dan menyebut persis variabel yang dibutuhkan. Begitu token itu ada di
`.env`, catatan itu hilang sendiri dan bagian Slack tinggal ditambahkan —
`build_message()` sudah menerima `has_slack_token` dan tesnya sudah ada.

## 4. Verifikasi

| Yang diperiksa | Hasil |
|---|---|
| Tes unit `sprint_report` | 17 lulus (pemilihan sprint, tugas terbuka, escaping HTML, batas panjang pesan) |
| Suite penuh | **434** lulus |
| Dry-run sebagai `ahagent` | laporan nyata tercetak, data Sprint 3 = 13/17 · 37/64 · 76% |
| Jalan sungguhan lewat systemd | `status=0/SUCCESS`, pesan terkirim ke Telegram |
| Jadwal berikutnya | `Tue 2026-09-22 00:30 UTC` = Selasa 07:30 WIB |

Catatan data: saat dry-run, Sprint 3 sudah bergerak dari 70% (laporan manual
beberapa jam sebelumnya) menjadi 76% — bukti kecil bahwa laporannya memang
membaca keadaan terkini, bukan salinan.

## 5. Yang tersisa

1. **Tambahkan `SLACK_BOT_TOKEN` ke `.env`** bila bagian Slack ingin ikut. Setelah
   itu cukup beri tahu saya; tidak perlu mengubah jadwal.
2. Tiga timer pengingat lama (`ah-sprint-daily`, `ah-sprint-weekly`) masih
   mengirim *reminder* pukul 07:00. Sekarang ada laporan sungguhan pukul 07:30,
   jadi layak diputuskan apakah pengingatnya masih perlu atau justru jadi derau.
