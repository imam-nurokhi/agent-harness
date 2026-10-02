# Nexora AI Platform — Dokumentasi End-to-End

**Terakhir diperbarui:** 20 September 2026
**Cakupan:** AI Assistant widget · agents.nexoratech.co (accreditation, academy, Agent Harness, n8n) · integrasi Telegram
**Status keseluruhan:** seluruh permukaan hidup dan terverifikasi, dan seluruh kode widget kini ada di git. Empat hal masih menunggu keputusan owner (§9).

---

## 1. Ringkasan untuk pembaca cepat

Ada satu server, satu alamat, dan empat hal yang berjalan di belakangnya:

| Yang dilihat pengguna | Apa sebenarnya | Siapa yang memakai |
|---|---|---|
| `agents.nexoratech.co/accreditation/` | prototipe NexAccred + AI Assistant | manajemen, asesor |
| `agents.nexoratech.co/academy/` | prototipe DeAcademy + AI Assistant | manajemen, tim training |
| `agents.nexoratech.co/` | Agent Harness Command Center | owner |
| `agents.nexoratech.co/automation/` | n8n (otomasi) | owner |
| `@AskNexAIBot` di Telegram | asisten tanya-jawab, hanya membaca | pengguna non-teknis |
| `@AgentNexoraBot` di Telegram | kendali harness + pekerjaan development | owner |

Semua di balik autentikasi. Tidak ada satu pun permukaan yang terbuka ke publik:
seluruh jalur di atas menjawab **401** tanpa kredensial — diperiksa 19 Sep 2026.

Dua kalimat yang paling sering ditanyakan, dijawab di muka:

- **AI Assistant di dalam aplikasi tidak memakai model bahasa (LLM).** Ia mesin
  aturan yang dibangkitkan dari dokumentasi produk, berjalan di peramban. Karena
  itu ia tidak bisa mengarang — bila tidak tahu, ia bilang tidak tahu.
- **AI Assistant di Telegram (`@AskNexAIBot`) memang memakai model**, tetapi
  hanya bisa **membaca** dokumen produk dan merangkum. Ia tidak bisa mengubah
  apa pun, di mana pun.

---

## 2. AI Assistant widget — alur end-to-end

### 2.1 Bagaimana sebuah jawaban lahir

```
dokumentasi produk + struktur aplikasi
        │  (generator dijalankan saat pengembangan)
        ▼
knowledge.generated.js  +  knowledge.js (KB manual)
        │
        ▼
mesin pencocokan di peramban  ──► jawaban + sumbernya
        │                              │
        │ bila tak ada yang cocok      │
        ▼                              ▼
CLARIFICATION_NEEDED            dicatat ke collector
        │                              │
        └──────────► daftar celah ◄────┘
                     pengetahuan
```

Isi basis pengetahuannya hari ini:

| Aplikasi | Aturan hasil generate | KB manual | Total |
|---|---|---|---|
| DeAcademy | 84 | 13 | **97** |
| NexAccred | 48 | 26 | **74** |

Academy naik dari 43 menjadi 84 aturan pada 19 Sep 2026, setelah ditemukan bahwa
ia sama sekali tidak punya aturan per-modul (accreditation punya satu per layar),
dan kata "modul"/"fitur" tidak ada sebagai kata kunci di mana pun. Diukur dengan
baterai pertanyaan realistis: cakupan academy **63% → 100%**, accreditation
**92% → 100%**.

### 2.2 Yang membuatnya tidak bisa mengarang

Setiap jawaban menunjuk ke sumber di dalam basis pengetahuan. Tidak ada sumber,
tidak ada jawaban — yang muncul adalah pengakuan jujur bahwa pertanyaan itu belum
tercakup. Uji regresi `guidance.smoke.mjs` (44 kasus) memastikan **setiap** ajakan
yang ditawarkan widget memang terjawab dari sumber, sehingga celah yang baru
ditutup tidak berubah menjadi janji yang meleset.

### 2.3 Umpan balik: dari pertanyaan gagal menjadi daftar kerja

Pertanyaan yang tak terjawab tidak hilang. Widget mengirimkannya ke pengumpul
internal (`/widget-feedback/`), yang menyimpan satu berkas per aplikasi per hari,
hanya bisa ditambah, dan identitas penggunanya ditetapkan **oleh server** — apa
pun yang dikirim peramban tentang identitas tidak dipercaya.

Kondisi nyata per 19 Sep 2026:

| Aplikasi | Pertanyaan tercatat | Belum terjawab (celah KB) |
|---|---|---|
| NexAccred | 6 | 3 |
| DeAcademy | 6 | 4 |

Sejak 19 Sep 2026 **teks pertanyaannya ikut dicatat**, sehingga laporan
`ah feedback` menampilkan daftar pertanyaan sungguhan, bukan sekadar angka.
Ringkasannya dikirim otomatis ke Telegram setiap Jumat 07:30 WIB.

### 2.4 Kekhususan tiap aplikasi

**NexAccred** memiliki lapisan "kecerdasan penuh" (Fase 6): saran pertanyaan yang
menyesuaikan layar yang sedang dibuka, tur terpandu per area penilaian yang
menavigasikan pengguna ke layar yang tepat, dan gerbang yang menolak tanda tangan
persetujuan bila prasyaratnya belum lengkap — sambil menunjukkan apa yang kurang.
Sembilan area penilaian masing-masing terhubung ke rute layar sungguhan.

**DeAcademy** memakai widget yang sama lewat cangkang DOM biasa di dalam shadow
root-nya sendiri, karena aplikasinya satu berkas HTML tanpa React. Sejak 19 Sep
2026 asisten tampil **sejak halaman pertama**, termasuk sebelum pengguna masuk.
Dua fakta yang mahal dipelajari di sini: sinyal menu aktif academy ada pada
*inline style*, bukan pada nama kelas (yang tidak pernah berubah); dan permintaan
jaringan yang gagal dicatat ke konsol **oleh peramban** sebelum kode mana pun
melihatnya — yang pernah mengubah 92 pengujian menjadi 36 kegagalan. Karena itu
widget hanya mengirim data di lingkungan yang memang punya pengumpul.

---

## 3. agents.nexoratech.co — peta permukaan

Satu vhost, satu sertifikat, empat permukaan berbeda di baliknya.

| Jalur | Tujuan | Autentikasi |
|---|---|---|
| `/` | Command Center harness (port lokal 7777) | Basic Auth (`.agents.htpasswd`) |
| `/accreditation/`, `/academy/`, `/servicedesk/` | prototipe statis | Basic Auth (`.prototypes.htpasswd`) |
| `/automation/` | n8n (port lokal 5678) | Basic Auth + login n8n |
| `/widget-feedback/` | pengumpul umpan balik (port lokal 7788) | Basic Auth |

Tiga fakta operasional yang tidak boleh hilang:

- **Garis miring di akhir `proxy_pass` menentukan segalanya** untuk n8n. Versi 2.x
  menyajikan berkas dari akar server, jadi mempertahankan awalan `/automation/`
  membuat setiap berkas pendukung dijawab dengan halaman HTML — status 200, tetapi
  aplikasinya kosong.
- **Batas laju diukur, bukan ditaksir.** Satu kali muat dingin editor n8n adalah
  **797 permintaan**. Angka `50r/s` dengan lonjakan 1200 diturunkan dari situ;
  tebakan sebelumnya meleset lebih dari sepuluh kali lipat dan mengakibatkan
  gangguan.
- **Halaman kosong hampir tidak pernah disebabkan CSP.** Tiga kali CSP dicurigai,
  tiga kali ia tidak bersalah — penyebab sebenarnya berturut-turut adalah batas
  laju, salah awalan rute, dan batas jumlah koneksi.

### 3.1 Cara prototipe dipublikasikan

Sumbernya ada di dua repositori GitHub (`NexoraTechTeam/academy` dan
`NexoraTechTeam/accreditation`), dibangun, lalu disalin ke direktori yang disajikan
nginx. Untuk academy, widget disisipkan **saat publikasi** sebagai satu blok skrip
sebaris; berkas HTML di dalam git tidak pernah diubah, karena alur "klik dua kali
untuk membuka" harus tetap berjalan.

**Sejak 19 September 2026 seluruh pohon widget (Fase 0–6) sudah masuk git.** Dua
pull request ter-merge ke `dev` setelah disetujui owner: academy (20 berkas) dan
accreditation (30 berkas), masing-masing melewati gate penuh lebih dulu dan
diverifikasi byte-identik (sha256) dengan pohon yang diuji.

Artinya dua hal yang selama ini belum pernah benar bersamaan kini benar: yang
tayang bisa dibangun ulang dari git, dan skrip refresh aman dijalankan — sebelum
ini ia akan menghapus satu-satunya salinan pekerjaan widget.

Cara pemindahannya menyimpan satu pelajaran: pekerjaan **tidak** di-commit dari
pohon publikasi. Berkas widget di sana belum terlacak git, sehingga meng-commit-nya
lalu berpindah branch akan menghapusnya dari pohon kerja — yaitu menghapus yang
sedang tayang. Pemindahan dilakukan lewat klon terpisah, dengan pembuktian sha256
atas kedua pohon sebelum commit.

---

## 4. Agent Harness (AH) — dari permintaan menjadi perubahan

Harness adalah cara pekerjaan development dijalankan oleh agent, dengan jejak yang
bisa ditinjau di setiap langkah.

```
permintaan (Telegram / dashboard)
   → task            (agents/tasks/<id>.md)
   → worktree        (salinan repo yang terisolasi, satu per task)
   → agent berjalan  (izin sempit; tidak ada jaringan, tidak ada .env)
   → hasil ditinjau  (/diff, /report)
   → /push           → branch baru + Pull Request ke dev
   → tombol Approve  → merge
```

Izin agent sengaja sempit dan ditegakkan oleh berkas kebijakan, bukan oleh niat
baik: agent boleh membaca, mencari, menjalankan Python, serta `git add` dan
`git commit`; agent **tidak** boleh `git push`, memakai `gh`, mengubah remote,
membaca `.env` atau `.git/config`, memakai `curl`/`wget`, `sudo`, `docker`, atau
`systemctl`. Menambah pengalaman baru selalu lewat tes, tidak pernah lewat bendera
pintas — server ini dipakai bersama layanan lain.

Papan kendali:

- **Command Center** di `/` — daftar task, run berjalan, log.
- **Telegram** — 42 perintah, lihat §5.
- **Timer terjadwal** — sapuan task mandek tiap jam, standup harian 07:00 WIB,
  pengingat sprint (Sen–Kam dan Jumat), laporan mingguan Jumat 08:00 WIB, digest
  umpan balik widget Jumat 07:30 WIB.

### 4.1 Aturan GitHub yang berlaku sejak 19 Sep 2026

Aturan owner: **commit dan push ke branch baru; Pull Request hanya boleh menuju
`dev`; merge hanya setelah owner menyetujui lewat Telegram.** Tiga gerbang
menegakkannya, masing-masing diuji:

1. Agent hanya bisa mendorong ke branch `ah/<task>-<waktu>` yang baru. Nama branch
   dicetak oleh sistem, sehingga agent tidak dapat memilih `dev`.
2. Pull Request hanya boleh menargetkan `dev`. Ini daftar-izin, bukan
   daftar-larangan: branch terlindungi yang baru dibuat besok otomatis aman.
3. Merge menolak **sebelum menyentuh jaringan** bila tidak ada persetujuan
   tercatat, dan persetujuan itu terikat pada commit persis yang ditunjukkan ke
   owner. Pull Request yang berubah setelah disetujui harus disetujui ulang.

Sebagai pertahanan berlapis, kait `pre-push` di setiap repositori menolak dorongan
ke `main`, `master`, `production`, `prod`, dan kini juga `dev`.

### 4.2 Bukti end-to-end, dijalankan 19 Sep 2026

Alur lengkapnya dijalankan sungguhan, bukan disimulasikan: task dibuat → worktree
dibuat dari `NexoraTechTeam/academy` → satu berkas dokumentasi ditulis dan
di-commit oleh identitas mesin ("Nexora Agent Harness") → `/push` mendorongnya ke
branch `ah/task-018-…` dan membuka **Pull Request #1 ke `dev`** → percobaan merge
tanpa persetujuan **ditolak** dengan alasan yang benar → kartu persetujuan dengan
tombol dikirim ke Telegram owner.

---

## 5. Integrasi Telegram — dua bot, dua peran

Keduanya sengaja dipisah, dan perbedaannya bukan kosmetik.

### 5.1 `@AskNexAIBot` — AI Assistant untuk pengguna non-teknis

Menjembatani Telegram ke satu sesi Claude Code di server. Ditujukan bagi
manajemen dan asesor yang bertanya tentang NexAccred dan DeAcademy.

- **Hanya membaca.** Menjalankan perintah, menulis berkas, mengakses internet, dan
  seluruh konektor Slack/Notion/Linear/GitHub **ditolak**. Yang tersisa hanyalah
  membaca dokumen produk kedua aplikasi.
- **Tidak pernah menampilkan tombol izin.** Pengguna non-teknis tidak punya dasar
  untuk menilainya, jadi permukaannya dipersempit sampai tidak ada lagi yang bisa
  meminta izin.
- **Gaya jawabnya diatur:** Bahasa Indonesia, ringkas untuk layar ponsel, tanpa
  istilah teknis, jujur bila dokumennya tidak memuat jawabannya, dan mengarahkan
  permintaan tindakan ke jalur yang benar.
- **Tahan mati.** Bila sesi berhenti — termasuk karena perintah `/exit` — layanan
  menghidupkannya kembali dalam ~10 detik, dan Telegram menerima pemberitahuan
  merah saat terputus lalu hijau saat kembali. Diam tidak pernah lagi disalahartikan
  sebagai "sedang berpikir".

Klaim "hanya membaca" itu diukur, bukan diasumsikan: sesi diminta menjalankan
perintah dan menulis berkas; jawabannya tidak ada alat semacam itu di sesi ini,
dan berkasnya memang tidak pernah ada.

### 5.2 `@AgentNexoraBot` — kendali harness dan pekerjaan development

42 perintah, dan **sejak 19 Sep 2026 teks biasa tanpa garis miring juga berfungsi**
sebagai permintaan development. Sebelumnya pesan semacam itu dibuang diam-diam —
tidak ditolak, tidak dicatat, hilang begitu saja.

| Kelompok | Contoh |
|---|---|
| Baca (viewer) | `/status`, `/ops`, `/brief`, `/reporting` |
| Data rinci (operator) | `/kanban`, `/tasks`, `/tail`, `/diff`, `/weekly`, `/daily` |
| Perubahan (owner) | `/run`, `/ask`, `/push`, `/pr`, `/prs`, `/merge`, `/grant` |

Alur persetujuan merge: `/merge <org/repo> <nomor>` menampilkan ringkasan Pull
Request — judul, jumlah berkas, baris bertambah/berkurang, dan commit-nya — dengan
dua tombol. Merge hanya terjadi pada ketukan **✅ Approve**, dan tombol itu
memeriksa ulang peran penekannya, karena sebuah pesan bisa ditekan siapa pun yang
ada di percakapan itu.

### 5.3 Pemisahan token yang wajib dijaga

Telegram hanya mengizinkan satu pembaca pesan per token. Karena itu tiap bot punya
tokennya sendiri, di berkas yang dibaca prosesnya masing-masing. Menyatukannya akan
membuat **kedua** bot gagal bersamaan. Sesi asisten juga sengaja tidak diberi
berkas konfigurasi harness sama sekali, karena berkas itu akan diam-diam
menurunkan kualitas langganan yang dipakainya.

---

## 6. n8n — otomasi, dengan rem tangan terpasang

n8n berjalan di `/automation/`, dan pada 19 Sep 2026 **belum ada satu pun alur
kerja aktif**. Itu keadaan yang disengaja, bukan pekerjaan yang tertinggal.

Yang sudah ada: akun owner, kontrol peran di permukaan Telegram, dan pencadangan
harian pukul 02:30 UTC.

Yang dilarang selama belum ada alur kerja yang disetujui: pengambilan data dari
GitHub/Slack/Notion/NEXONE, laporan atau tiket yang dihasilkan n8n, webhook
Telegram di dalam n8n (bot memegang satu-satunya hak baca pesan), serta seluruh
tindakan deploy, DNS, tagihan, shell, SSH, dan berkas. Penegakannya ada di
konfigurasi: simpul kode, eksekusi perintah, baca-tulis berkas, dan SSH
dikeluarkan dari instalasi; paket komunitas dimatikan; API publik dimatikan.

Protokol per alur kerja: satu per satu, data sintetis lebih dulu, satu kredensial
paling minimal per integrasi, diuji dari jalankan manual sampai pengiriman
notifikasi, lalu **persetujuan eksplisit owner** sebelum jadwal atau webhook
dinyalakan.

**Celah yang diketahui dan belum ditutup:** cadangan tersimpan tanpa enkripsi, dan
kunci enkripsi berada di direktori yang sama dengan data yang dilindunginya. Izin
berkasnya ketat (hanya root), jadi terkendali hari ini, tetapi rencananya
mensyaratkan cadangan terenkripsi, teruji pulih, dan tersimpan di luar server ini.
Pemulihan belum pernah diuji.

---

## 7. Keamanan dan kredensial

| Aspek | Keadaan |
|---|---|
| Seluruh permukaan web | di balik Basic Auth; diperiksa 401 tanpa kredensial |
| Rahasia | hanya di `.env` server (`0600`), tidak pernah lewat percakapan |
| Agent | tidak bisa membaca `.env`, `.git/config`, `~/.ssh`, `/root` |
| Token GitHub | tidak pernah ditulis ke `.git/config`; URL berkredensial disusun di memori dan disensor dari seluruh keluaran |
| Pemisahan tugas | asisten hanya membaca; harness bisa mengubah tetapi tidak bisa menerbitkan; hanya owner yang bisa merge |

**Menunggu rotasi** (ditunda owner sejak 17 Sep 2026): kata sandi root VPS, Basic
Auth `agents.nexoratech.co` untuk pengguna `imam`, dan kata sandi akun owner n8n —
ketiganya pernah melewati transkrip percakapan.

Satu hal baru yang perlu masuk tinjauan akses berikutnya: kredensial login penuh
akun claude.ai kini tersimpan di direktori rumah pengguna layanan pada server yang
dipakai bersama. Ini diterima secara sadar pada 19 Sep 2026 karena dibutuhkan oleh
sesi asisten, dan cakupannya lebih luas daripada token sebelumnya.

---

## 8. Cara memverifikasi semuanya masih sehat

| Yang diperiksa | Perintah | Hasil yang benar |
|---|---|---|
| Layanan | `systemctl --user is-active ah-telegram ah-channel-telegram ah-dashboard ah-feedback` | empat baris `active` |
| Pengujian harness | `python3 -m unittest discover -s tests` | **381** lulus |
| Kebijakan izin agent | `python3 -m unittest discover -s ops/harness/tests` | 11 lulus |
| nginx / n8n / pengumpul | tiga suite di `ops/` | 20 / 10 / 29 lulus |
| Permukaan web | `curl -o /dev/null -w "%{http_code}" https://agents.nexoratech.co/...` | `401` tanpa kredensial |
| Celah pengetahuan widget | `ah feedback` | daftar pertanyaan yang belum terjawab |

Satu peringatan yang berulang kali terbukti mahal: **status 200 bukan
verifikasi.** Berkas pendukung n8n pernah menjawab 200 sambil sebenarnya
mengirimkan halaman HTML, dan pemeriksaan berbasis status menyatakan semuanya
sehat sementara seluruh aplikasi rusak. Periksa jenis isi, ukuran, dan apa yang
benar-benar terjadi di peramban.

---

## 9. Status per 20 September 2026 dan yang berikutnya

**Selesai dan terverifikasi**

- AI Assistant widget hidup di kedua aplikasi, cakupan pertanyaan 100% pada
  baterai uji, dengan pencatat celah pengetahuan yang berjalan.
- Asisten Telegram non-teknis hidup, hanya-baca, tahan mati, dan memberi kabar
  saat terputus maupun kembali.
- Alur GitHub lengkap: branch baru → Pull Request ke `dev` → merge lewat tombol
  persetujuan; dijalankan end-to-end pada repositori sungguhan.
- Kredensial GitHub untuk menulis terpasang dan terverifikasi per pemilik
  repositori.
- **Seluruh pekerjaan widget sudah masuk git** (§3.1), sehingga yang tayang bisa
  dibangun ulang dan skrip refresh aman dijalankan kembali.

**Menunggu keputusan atau tindakan owner**

1. **Rotasi tiga kredensial** yang pernah melewati percakapan (§7).
2. **Cadangan n8n terenkripsi dan teruji pulih**, serta disimpan di luar server ini.
3. **Alur kerja n8n pertama**, bila memang diinginkan — protokolnya sudah siap.
4. **Model bahasa sungguhan di balik widget dalam aplikasi** masih ditunda. Bila
   suatu saat disetujui, jalurnya sudah dirancang agar tidak memerlukan pelonggaran
   kebijakan keamanan peramban.

Satu sisa kecil yang bukan keputusan, hanya kerapian: pohon publikasi di server
masih menampilkan berkas widget sebagai belum-terlacak, karena commit dibuat dari
klon terpisah. Setiap berkas sudah diverifikasi identik dengan yang ada di git,
jadi tidak ada yang berisiko; ia rapi sendiri saat skrip refresh dijalankan.

---

### Catatan penyusunan

Dokumen ini disusun dari keadaan sistem yang berjalan pada 19-20 September 2026:
konfigurasi nginx, berkas unit layanan, keluaran pengujian, data pengumpul umpan
balik, dan hasil pemeriksaan langsung terhadap GitHub. Angka yang disebut di sini
dihitung dari berkas yang ada, bukan dikutip dari dokumen sebelumnya.
