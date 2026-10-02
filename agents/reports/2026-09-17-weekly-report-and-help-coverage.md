# Sesi — `/help` lengkap, weekly report Jumat pagi, dan temuan scheduler

**Tanggal:** 2026-09-17
**Status:** terpasang dan berjalan; satu temuan besar menunggu keputusan owner
**Terkait:** `agents/reports/2026-09-17-cloud-ops-nginx-ratelimit-fix.md`

---

## 1. `/help` — 6 perintah yang tidak pernah tercantum

`/diff`, `/report`, `/log`, `/push`, `/engine`, `/resume` bisa di-dispatch dan
terdaftar di menu slash Telegram, **tetapi tidak pernah muncul di `/help`** —
satu-satunya referensi yang dibaca di dalam chat tidak cocok dengan permukaan
bot yang sebenarnya.

Diperbaiki, dan sekarang dipin oleh `tests/test_telegram_help_coverage.py`
(10 test) yang mengikat tiga daftar yang selama ini bisa berpencar:
tabel dispatch, menu slash, dan teks `/help`. Test gagal bila `/help` melewatkan
perintah yang ada, mengiklankan perintah yang tidak ada, atau bila menu slash
dan dispatch tidak lagi sama.

`/help` sekarang dikelompokkan menurut **role** — Viewer / Operator / Owner —
supaya pembaca tahu kenapa sebuah perintah ditolak, bukan menemukannya dengan
cara ditolak.

`/help` dan `/status` juga menutup dengan role chat yang bersangkutan. Baris
"cek role-mu dengan /status" semula janji kosong: `/status` tidak pernah
menampilkan role. Ditambahkan lewat `_role_banner()` di dispatcher, mengikuti
pola `_engine_banner()` yang sudah ada, memakai `tgcore.ROLE_LEVELS` sebagai
sumber tunggal urutan role.

## 2. Weekly report untuk meeting manajemen — `/weekly`

Owner meminta laporan mingguan Jumat pagi. Plan menyebut syaratnya:

> *"Daily/weekly report **deterministik** untuk direktur, manajemen, dan
> developer dari data yang sudah disetujui."*

Jadi ini **bukan** prompt agent. `bin/lib/weekly.py` menurunkan laporan dari
state harness: tidak memakai engine spend sama sekali (relevan — job
`101013-2ce5` gagal justru karena spend limit), tidak bisa mengarang task yang
selesai, dan input yang sama selalu menghasilkan teks yang sama.

Isi: selesai minggu ini · sedang berjalan · **mandek ≥3 hari** · antrian ·
run gagal · layanan yang perlu perhatian · engine yang ditolak.

`collect()` murni data dan `render()` murni presentasi, jadi angkanya bisa
diuji tanpa mem-parsing markup Telegram.

### Laporan mengakui kelemahan buktinya sendiri

Preview pertama menyatakan **20 task "selesai minggu ini"** — yaitu *seluruh*
task `reported` yang ada. Penyebabnya: tanggal selesai diturunkan dari `mtime`
berkas, dan seluruh `mtime` ter-refresh saat workspace disalin ke VPS.

Daripada memukau meeting manajemen dengan angka yang sebenarnya artefak rsync,
laporan menandainya sendiri bila ≥90% task `reported` jatuh dalam satu periode:

> ⚠️ 20 dari 20 task reported jatuh di periode ini. Tanggal selesai diturunkan
> dari `mtime` berkas, jadi angka itu kemungkinan artefak penyalinan workspace,
> bukan catatan delivery. Jangan dipakai di meeting tanpa dicek.

Daftar panjang juga dipotong pada 8 item + hitungan sisanya, karena Telegram
menolak pesan di atas 4096 karakter.

### Penjadwalan

`ah-weekly.timer` → **Jumat 08:00 Asia/Jakarta** (`OnCalendar=Fri 08:00
Asia/Jakarta`; systemd 255 mendukung timezone eksplisit — jam server UTC tapi
meeting-nya WIB). `Persistent=true` supaya tidak hilang bila server mati.

`weeklyrun.py` **menulis berkas dulu, baru mengirim**: kegagalan Telegram
berarti kehilangan notifikasi, bukan kehilangan laporan minggu itu. Berkasnya
`agents/reports/weekly-<tanggal>.md` dalam Markdown, bukan HTML Telegram.

Uji nyata: `Result=success`, berkas tertulis, terkirim ke chat owner.

## 3. Temuan: tidak ada satu pun trigger terjadwal di VPS ini

`agents/triggers.json` berisi empat trigger bertanda `enabled: true`:

| trigger | jadwal | status sebenarnya |
|---|---|---|
| `standup` | daily 07:00 | **tidak terpasang** |
| `health` | weekly Mon 09:00 | **tidak terpasang** |
| `drift` | weekly Fri 16:00 | **tidak terpasang** |
| `sweep` | weekly Sun 20:00 | **tidak terpasang** |

`systemctl --user list-timers --all` hanya menampilkan `ah-resume.timer` (dan
sekarang `ah-weekly.timer`). Field `last_run` berisi tanggal, tapi itu dari
mesin lain atau dari run manual — **bukan** dari jadwal di server ini.

Artinya "daily update list" yang diharapkan owner memang belum pernah berjalan
otomatis di sini, dan `/triggers` menampilkannya sebagai aktif sehingga
menyesatkan.

Sengaja **belum** saya pasang: keempatnya menjalankan agent Claude, dan akun
ini sudah kena spend limit. Memasang empat jadwal berulang tanpa persetujuan
berarti membakar kuota tanpa diminta. Butuh keputusan owner.

## 4. Test

| suite | sebelum | sesudah |
|---|---|---|
| `tests/` | 200 | **237** |
| `ops/nginx/tests` | — | 14 |
| `ops/n8n/tests` | 10 | 10 |

Berkas baru: `tests/test_telegram_help_coverage.py` (10),
`tests/test_weekly_report.py` (22), `tests/test_weekly_runner.py` (5).

## 5. Rekomendasi lanjutan untuk kebutuhan tech lead

Pembagiannya mengikuti **di mana datanya berada**, bukan selera tooling:

- **Data harness (task, sprint, run)** → trigger harness. n8n **tidak bisa**
  menjangkaunya: dashboard hanya bind `127.0.0.1:7777` dan n8n ada di Docker.
- **Layanan eksternal (GitHub, dll.)** → workflow n8n. Ini juga yang plan
  maksud: *"Workflow cloud mengumpulkan status dan mengirim notifikasi, bukan
  menjalankan agent dengan credential produksi."*

Urutan yang saya sarankan:

1. **Pasang trigger `standup`** (daily update list) — begitu owner setuju soal
   konsumsi engine.
2. **Sprint planning Senin pagi** — belum ada sama sekali; harness tidak punya
   konsep sprint/iterasi, hanya status. Perlu keputusan apakah menambah field
   sprint pada task.
3. **Alert task mandek** sebagai notifikasi harian, bukan hanya bagian dari
   laporan Jumat. `tgwatch.detect()` sekarang hanya menangkap run selesai,
   kriteria lengkap, trigger, dan engine — tidak ada deteksi task diam.
4. **GitHub daily status** di n8n — template sudah direview dan menunggu di
   `ops/n8n/workflow-templates/`. Terhenti pada token fine-grained read-only
   dan nama owner/repo dari owner.

## 6. Rollback

```sh
systemctl --user disable --now ah-weekly.timer
rm ~/.config/systemd/user/ah-weekly.{service,timer}
systemctl --user daemon-reload
```

Perubahan kode ada di `bin/lib/{weekly.py,weeklyrun.py,tgcmd.py,tgcore.py,tgbot.py}`.

---

# Adendum — agent otomatis tidak pernah bisa memakai tool sama sekali

**Waktu:** 2026-09-17 sore. Owner melaporkan pesan dari Command Center
"nyangkut", lalu menyimpulkan "sudah bisa, agak delay".

## Koreksi

Job-nya memang **selesai** (`exit: done`, `code: 0`, 181 detik) — jadi bukan
menggantung. Tapi tugasnya **tidak dikerjakan**. Log job `135157-520a`:

> every `python3` invocation (including a plain `print('hello')` sanity check)
> was blocked by this session's permission gate … **No message was sent.**

Yang masuk ke Telegram saat itu adalah notifikasi "run selesai" dari `tgwatch`,
bukan pesan dari agent.

## Akar masalah

Harness menjalankan agent dengan `claude -p` — headless, **tanpa deklarasi izin
apa pun**. Tidak ada manusia yang bisa menyetujui prompt, jadi setiap tool call
ditolak. Riwayat job membuktikannya:

| job | butuh tool? | hasil |
|---|---|---|
| `075832-d6db` "Reply with exactly one line" | tidak | done, benar |
| `135157-520a` kirim Telegram | ya | done, **blocked**, 181 s |

Ini berarti **keempat trigger terjadwal akan gagal dengan cara yang sama** —
membakar kuota tiap pagi tanpa hasil.

## Perbaikan (opsi "allowlist eksplisit" dipilih owner)

`ops/harness/claude-settings.json`: allowlist sempit, deny menang atas allow.
Boleh: `Read`, `Grep`, `Glob`, `Task`, dan verb shell read-only termasuk
`python3` serta `git status|log|diff|show`. Ditolak: `.env` (tempat token bot
dan OAuth), `~/.ssh`, `/root`, `/etc/nginx`, edit di `/etc`, dan `sudo`, `curl`,
`ssh`, `docker`, `systemctl`, `rm -rf`, `git push`, `npm`, `pip`.

Ditolak juga opsi bypass: host ini dipakai bersama `dev-kemenkes`,
`dev-support`, dan `monitoring`.

### Empat bug ditemukan saat mengerjakannya

1. **Deny `Write(path)` adalah konfigurasi mati.** CLI memberi tahu langsung:
   hanya `Edit(path)` yang dicocokkan oleh pemeriksaan izin file. Dihapus,
   dipin oleh test.
2. **Perbaikan pertama mengenai jalur yang salah.** `common.sh` melayani
   `ah run`, tapi **`jobs.py` membangun argv-nya sendiri** dan itulah jalur
   yang dipakai dashboard dan Telegram. Sekarang keduanya membawa `--settings`,
   dan test gagal bila salah satu melepasnya.
3. **`ah trigger install` hanya untuk macOS** — menulis plist launchd tanpa
   syarat, jadi di Linux ia membuat `~/Library/LaunchAgents` dan tidak
   menjadwalkan apa pun. `ah trigger list` juga membaca status dari path plist
   itu, sehingga selalu melapor "no". Sekarang lewat `sv_install_timer` /
   `sv_uninstall` / `sv_is_managed`.
4. **`_sv_unit_dir` menambahkan `/.config/` dua kali** — unit ditulis ke
   `~/.config/.config/systemd/user`, direktori yang tidak pernah dibaca systemd.
   Ini melengkapi penjelasan kenapa tidak ada trigger yang pernah terjadwal.

Ditambah satu cacat desain: **unit systemd yang dihasilkan tidak membawa
`.env`**, jadi agent terjadwal akan menjawab *"Not logged in — Please run
/login"*. Sekarang unit membawa `EnvironmentFile=-<workspace>/.env` dan
`AH_WORKSPACE`.

### Verifikasi

Instruksi yang sama, yang gagal dua kali, kini:

```
Message sent successfully.  ok: true, message_id: 69
elapsed: 59 s
```

Lebih cepat justru karena agent tidak lagi melawan gerbang izin
(181 s → 117 s → **59 s**).

## Trigger standup terpasang

```
com.ah.trigger.standup.timer   OnCalendar=*-*-* 07:00:00 Asia/Jakarta
```

**Zona waktu di-pin.** launchd membaca jadwal dalam waktu lokal mesin, sementara
`OnCalendar` polos memakai jam server — yang di sini UTC. Entri `triggers.json`
yang sama berarti 07:00 WIB di Mac tapi 14:00 WIB di VPS. Default sekarang
`Asia/Jakarta`, bisa ditimpa lewat `AH_SCHEDULE_TZ`.

Dicek: tidak ada catch-up yang terpicu saat instalasi, jadi nol kuota terpakai.

Tiga trigger lain (`health`, `drift`, `sweep`) sengaja **belum** dipasang —
menunggu keputusan owner soal konsumsi engine.

## Alert task mandek

`tgwatch` sebelumnya hanya bereaksi pada **kemajuan** — run selesai, kriteria
lengkap. Tidak ada yang bereaksi pada **ketiadaan** kemajuan, jadi task yang
mandek Senin baru terlihat di laporan Jumat.

`_stuck_task_events()`: task `active`/`review` yang tidak tersentuh ≥3 hari,
diberitahukan sekali sehari (bukan tiap poll 25 detik), dan dilupakan begitu
task bergerak lagi supaya stall kedua langsung berbunyi. Deterministik, nol
engine spend.

## Suite tidak lagi flaky

`test_resume_integration` gagal di `tearDown` (`OSError: Directory not empty:
'.jobs'`) pada sekitar separuh run, sehingga suite tidak bisa dipakai sebagai
gate. Sebabnya `jobs.spawn` memakai `start_new_session=True`, jadi proses anak
hidup lebih lama dari badan test dan masih menulis saat direktori dihapus.
`tearDown` kini menunggu tiap job punya `.rc` **atau** pid-nya hilang.

Tiga run berturut-turut hijau. Ongkosnya waktu suite naik 14s → 40s karena
teardown benar-benar menunggu, bukan membatalkan cleanup di tengah.

## Test

| suite | sebelum | sesudah |
|---|---|---|
| `tests/` | 237 | **266** |
| `ops/harness/tests` | — | **11** |
| `ops/nginx/tests` | 14 | 14 |
| `ops/n8n/tests` | 10 | 10 |

## Rollback

```sh
systemctl --user disable --now com.ah.trigger.standup.timer
rm ~/.config/systemd/user/com.ah.trigger.standup.{service,timer}
systemctl --user daemon-reload
```

Untuk mengembalikan perilaku izin lama, hapus `ops/harness/claude-settings.json`
— kedua jalur spawn melewatkan `--settings` bila berkasnya tidak ada.
