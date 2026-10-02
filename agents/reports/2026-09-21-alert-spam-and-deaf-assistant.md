# 2026-09-21 — Tiga alarm palsu, satu asisten tuli

**Diminta owner:** cari akar masalah dari notifikasi berulang di `@AgentNexoraBot`,
perbaiki dengan OODA + TDD; lalu (paralel) jelaskan apa yang terjadi di
`@AskNexAIBot` — gap, issue, atau bug?

**Hasil:** empat cacat berbeda, semuanya satu keluarga — **sistem melaporkan
keadaan yang tidak ia periksa**. Dua menghasilkan alarm yang tidak bisa
ditindaklanjuti, satu menyembunyikan penjadwal yang sebenarnya jalan, dan satu
membuat AI Assistant tampak online padahal tidak bisa mendengar sama sekali.

---

## 1. Observe — apa yang terlihat

Dari layar pertama (`@AgentNexoraBot`):

- `⚠️ Auto-resume gagal — task-018 tidak bisa dimulai: unknown role: lead |
  frontend | backend | qa | review | devops | docs` — **sembilan kali**, tiap jam
  dari 04:10 sampai 09:10.
- `⏰ Trigger sweep terlambat — jadwal weekly Sun 20:00 …`

Dari layar kedua (`@AskNexAIBot`):

- Asisten menjanjikan akan "langsung jalankan Playwright ke nexone.nexoratech.co"
  begitu kredensial NEXONE tersedia.
- Dua siklus 🔴/🟢 berturut-turut pukul 02:17 dan 02:18.
- Dua pesan owner (03:23 dan 17:49) **tidak dijawab sama sekali**.

## 2. Orient — akar masalah, satu per satu

### 2.1 Pesan errornya bukan daftar pilihan — itu memang nilainya

Bacaan pertama saya salah, dan itu perlu dicek sebelum diperbaiki: "unknown role:
lead | frontend | …" terbaca seperti sistem sedang menyebutkan peran yang valid.
Bukan. Itu **isi field `Role:`** pada task-018, karena `ah task new` menulis
*menu pilihan* ke dalam field, dan tidak ada apa pun yang membedakan template
yang belum diisi dari yang sudah.

Rantainya: task-018 punya worktree → `resume` menilainya "berhenti di tengah dan
bisa dilanjutkan" → `jobs.spawn` menolak peran yang mustahil → alarm. Satu jam
kemudian berkasnya masih sama, jadi hasilnya sama persis. Selamanya.

Task-018 itu saya sendiri yang membuatnya pada 2026-09-19 sebagai uji end-to-end
jalur GitHub, lalu tidak pernah saya isi maupun tutup. Itu pemicunya — tetapi
memperbaiki task-nya saja akan meninggalkan perangkapnya tetap terpasang untuk
task berikutnya.

### 2.2 Trigger yang tidak dipasang tidak mungkin terlambat

`sweep` adalah satu dari tiga trigger yang **sengaja tidak dipasang** owner
(CLAUDE.md §7) karena masing-masing memakai kuota engine. Memberi tahu seseorang
bahwa jadwal yang ia pilih untuk tidak dipasang "tidak jalan" bukan peringatan —
itu derau mingguan yang tidak bisa ditindaklanjuti.

### 2.3 …dan status "terpasang" itu sendiri salah

Di baliknya ada cacat yang lebih dalam, sekeluarga dengan bug penjadwal
2026-09-17: `state` menentukan "installed" dengan mencari **plist launchd**
(macOS). Di host Linux ini berkas itu tidak pernah ada, sehingga **setiap**
trigger terbaca tidak terpasang — termasuk `standup`, yang punya timer systemd
aktif dan baru berjalan pagi itu. Pemasangnya belajar soal systemd empat hari
lalu; pembaca statusnya tidak.

Lapisan ketiga: `sv_is_managed` memanggil `systemctl --user` tanpa
`XDG_RUNTIME_DIR`. Tanpa itu systemctl tidak menemukan bus user dan keluar
dengan kode non-nol — yang dibaca sebagai "tidak terpasang", bukan sebagai
"gagal memeriksa". CLAUDE.md §2 sudah memperingatkan manusia soal variabel ini;
kodenya sendiri belum.

### 2.4 AI Assistant hidup, tetapi tuli

Ini yang paling serius, dan jawabannya untuk pertanyaan "ada gap/issue/bug kah":
**ya, bug — dan pesan Anda memang tidak pernah sampai.**

Yang diperiksa semua orang mengatakan sehat: unit `active (running)`, sesi tmux
hidup, proses Claude Code hidup **31 jam**, dan notifikasi terakhir di chat
berwarna hijau. Semuanya benar, dan tidak satu pun menjawab pertanyaan yang tepat.

Pesan masuk dari Telegram hanya punya satu jalur: server MCP milik plugin channel
— sebuah proses `bun`. Proses itu **tidak ada**. Diverifikasi: cgroup layanan
hanya berisi server tmux, `pgrep -af bun` kosong sama sekali.

```
tmux hidup + claude hidup + plugin hidup  = bisa mendengar
tmux hidup + claude hidup + plugin HILANG = tampak online, sebenarnya tuli
```

`Restart=always` tidak pernah menolong karena proses utama unit adalah tmux, dan
tmux tidak mati. Notifikasi hijau saya sendiri ikut menyesatkan: ia menyala saat
unit *start*, bukan saat bridge benar-benar tersambung. Itu jebakan "status 200
bukan verifikasi" (CLAUDE.md §4) dalam kostum baru — dan kali ini saya yang
memasangnya.

Adapun dua siklus 🔴/🟢 pukul 02:17–02:18: itu **restart saya sendiri** saat
mengkonfigurasi asisten (19:17–19:18 UTC = 02:17–02:18 WIB). Bukan
ketidakstabilan; jurnal tidak mencatat satu pun restart setelahnya.

### 2.5 Asisten menjanjikan yang mustahil, dan meminta kredensial

Asisten menulis akan "langsung jalankan Playwright ke nexone.nexoratech.co". Ia
tidak bisa dan tidak akan pernah bisa: tidak punya Bash, jaringan, maupun
peramban — dan itu memang desainnya. Menjanjikannya membuat owner menunggu
sesuatu yang tidak akan datang, dan lebih buruk, mengarah pada penyerahan
kredensial NEXONE untuk kemampuan yang tidak ada. CLAUDE.md §9 mencatat tiga
kredensial yang sudah bocor persis lewat jalan seperti ini.

## 3. Act — perbaikan, TDD, merah dulu

Tes ditulis lebih dulu dan semuanya gagal dengan pesan yang sama seperti di layar
owner, lalu perbaikannya menghijaukan mereka.

| Lapisan | Perbaikan | Tes |
|---|---|---|
| Field template | `state._field` mengembalikan `""` untuk menu (`a \| b`) dan `<placeholder>` | `test_unconfigured_task.py` (14) |
| Pemilihan resume | `resume.unstartable_reason()`; task tanpa peran sah **bukan** kandidat, dan muncul di `resume.unconfigured()` dengan alasannya | idem |
| Alarm berulang | `resumerun.should_announce()` — kegagalan identik diumumkan **sekali**, perubahan berbicara lagi | idem |
| Trigger tak terpasang | `tgwatch` melewati alarm terlambat bila `installed` false | `test_trigger_installed_detection.py` (8) |
| Deteksi terpasang | `state._trigger_installed()` memeriksa timer systemd **dan** plist launchd, menghormati `XDG_CONFIG_HOME` | idem |
| Bus systemd | `_sv_user_bus` mengisi `XDG_RUNTIME_DIR` bila kosong | `test_supervise_user_bus.py` (4) |
| Bridge tuli | `bin/channel_health.py` — status `healthy/deaf/down` dari proses nyata, `--repair` merestart, timer tiap 10 menit | `test_channel_health.py` (10) |

Satu tes lama ikut diubah dengan sengaja:
`test_trigger_that_never_fired_is_reported_overdue_once` kini memasang trigger
lebih dulu, karena aturannya berubah — trigger yang tidak dipasang tidak lagi
dianggap terlambat. Fixture-nya juga diisolasi dengan `XDG_CONFIG_HOME` sendiri,
supaya hasilnya tidak bergantung pada unit yang kebetulan ada di host.

### Yang juga dibereskan di mesin

- **task-018 diisi jujur dan ditutup**: peran `docs`, empat kriteria tercentang,
  report berisi commit `b45eee2` dan PR #1 yang ter-merge. Statusnya kini
  `review`, bukan pekerjaan mandek. Sapuan manual menjawab `idle` — tanpa alarm.
- **Bridge diperbaiki**: `channel_health.py --repair` mendeteksi `deaf` lalu
  merestart; proses plugin hidup kembali dan status menjadi `healthy`.
- **Penjaga dipasang**: `ah-channel-health.timer` tiap 10 menit. Sepuluh menit
  dipilih karena masih di dalam masa simpan ~24 jam update Telegram, sehingga
  pesan yang terlewat saat tuli masih terkirim setelah restart, bukan hilang.
- **Persona asisten diperketat**: dilarang menjanjikan tindakan di masa depan,
  dilarang meminta kredensial dengan cara apa pun, dan diminta menyarankan
  rotasi bila pengguna terlanjur mengirimkannya.
- **`ah trigger list`** kini menampilkan `standup = yes` — klaim CLAUDE.md §7
  akhirnya bisa diverifikasi, bukan sekadar dipercaya.

## 4. Gate

| Suite | Hasil |
|---|---|
| `tests` | **417** OK (dari 403; +36 tes baru di sesi ini) |
| `ops/harness` · `nginx` · `n8n` · `feedback` | 11 · 20 · 10 · 29 OK |
| Bridge | `channel_health.py` → `healthy` |
| Sapuan resume manual | `idle`, tanpa notifikasi |

## 5. Yang tersisa

- Pesan owner pukul **03:23** kemungkinan besar sudah lewat masa simpan Telegram
  dan hilang; yang **17:49** seharusnya terkirim setelah restart. Layak dikirim
  ulang bila belum terjawab.
- Tiga trigger (`health`, `drift`, `sweep`) tetap tidak dipasang sesuai keputusan
  owner. Sekarang mereka diam, bukan memperingatkan setiap minggu.
