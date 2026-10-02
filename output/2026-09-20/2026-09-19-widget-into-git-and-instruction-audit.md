# 2026-09-19 — Widget masuk git, lalu audit CLAUDE.md / AGENTS.md / memory

**Diminta owner:** (1) selesaikan sisa pekerjaan "masukkan pekerjaan widget ke git";
(2) setelah itu verifikasi dan perbarui `CLAUDE.md`, `AGENTS.md`, dan memory "supaya
next pengerjaan agent akan selalu terarah dan terstruktur, bukan menebak-nebak".

**Hasil:** dua pull request ter-merge ke `dev` lewat ketukan Approve owner, dan tiga
berkas instruksi diperbaiki — termasuk satu aturan di `AGENTS.md` yang sudah **salah**
dan akan menyesatkan setiap agent yang membacanya.

---

## 1. Pekerjaan widget kini ada di git

| Repo | PR | Berkas | Gate sebelum commit |
|---|---|---|---|
| `NexoraTechTeam/academy` | **#2**, merged | 20 | `./run-tests.sh` → 92 passed, 2 skipped |
| `NexoraTechTeam/accreditation` | **#1**, merged | 30 | 5 smoke widget GREEN + `test:vanilla-shell` GREEN |

Sebelum ini seluruh pohon widget (Fase 0–6) hanya hidup sebagai berkas lokal di pohon
publikasi: satu kali clone bersih akan kehilangan seluruh `widget/`, dan `refresh.sh`
akan menghapusnya tanpa jejak. Sekarang yang tayang bisa dibangun ulang dari git, dan
`refresh.sh` aman dijalankan lagi.

### Cara memindahkannya tanpa merusak yang tayang

Jebakan yang harus dihindari: **jangan commit dari `/opt/nexora-prototypes`.** Berkas
widget di sana *untracked*; begitu ia di-commit ke sebuah branch lalu branch-nya
ditukar, git akan menghapus berkas itu dari pohon kerja — artinya menghapus yang
sedang tayang. Karena itu:

1. Klon bersih di `projects/<app>`, disinkronkan ke `origin/dev`.
2. Salin keadaan pohon publikasi ke klon — untuk accreditation lewat
   `git diff HEAD` (menangkap modifikasi, rename, dan penghapusan sekaligus) ditambah
   salinan berkas untracked; untuk academy cukup salin `widget/` dan satu berkas tes.
3. **Buktikan salinannya**: sha256 atas seluruh berkas terkait di kedua pohon harus
   sama sebelum commit. Keduanya cocok persis — itulah yang menjamin yang di-commit
   adalah yang diuji.
4. Commit → `ghflow.push_branch` → PR ke `dev` → kartu approval ke Telegram.

Untuk accreditation, kelima smoke murni **diulang di dalam klon bersih** dan tetap
GREEN; `verify-vanilla-shell` butuh `node_modules` sehingga dijalankan di pohon
publikasi atas berkas yang sha256-identik. Mengatakannya begitu lebih jujur daripada
mengklaim seluruh gate berjalan di klon.

### Satu sisa yang sengaja tidak saya kerjakan

`/opt/nexora-prototypes/src/{academy,accreditation}` masih menampilkan berkas-berkas
itu sebagai kotor/untracked, karena commit dibuat dari klon. Setiap berkas sudah
diverifikasi **byte-identik dengan `origin/dev`** (20 dan 28 berkas dibandingkan satu
per satu), jadi tidak ada yang berisiko hilang. Merapikannya cukup dengan
`git reset --hard origin/dev` di sana — atau dibiarkan, karena `refresh.sh` melakukan
hal yang sama saat dijalankan. Classifier auto-mode menolak perintah itu sebagai
*Production Deploy*, dan pagarnya benar, jadi owner yang menjalankannya bila mau.

## 2. Audit berkas instruksi

Tiga berkas diperiksa terhadap kenyataan mesin, bukan terhadap ingatan.

### `AGENTS.md` — satu aturan yang sudah salah

Ini yang paling penting: `AGENTS.md` disuntik verbatim ke **setiap** agent run, jadi
satu kalimat basi di sini menyesatkan setiap pekerjaan berikutnya.

| Yang tertulis | Kenyataan |
|---|---|
| "Push to `dev` or `staging`" | Salah sejak 19 Sep. Agent tidak boleh push sama sekali; `dev` kini branch terlindungi |
| "Pull before push" | Tidak berlaku — agent tidak menerbitkan apa pun |
| "`projects/` dan `worktrees/` belum ada di host ini" | Salah — keduanya ada sejak 19 Sep, berisi dua klon |
| Daftar izin tanpa `git add`/`git commit` | Kedua perintah itu kini diizinkan |

Diganti dengan satu bagian yang menjelaskan **bagaimana pekerjaan agent benar-benar
sampai ke produksi**: commit di worktree → owner `/push` → branch `ah/…` + PR ke `dev`
→ Approve di Telegram → merge. Ditambah dua hal yang dulu tidak tertulis: worktree
harus bersih (karena `/push` mengirim HEAD, jadi yang belum di-commit diam-diam absen
dari PR yang disetujui), dan `/opt/nexora-prototypes` adalah pohon publikasi yang
tidak boleh disentuh agent.

Berkasnya tumbuh 5155 → 6056 byte. Tambahan ~900 byte per run itu dibayar untuk
menghapus instruksi yang akan membuat agent mencoba hal yang pasti ditolak.

### `CLAUDE.md`

- §3: jumlah tes 305 → **381**, feedback 26 → 29; hasil benar academy dieja
  **92 passed + 2 skipped** (94/94 berarti sedang menguji build yang sudah disisipi).
  Flake `test_resume_integration` dinyatakan apa adanya: satu dari lima run gagal
  teardown pada 19 Sep — ulangi dulu sebelum menyelidiki.
- §4: peringatan lama "projects/ dan worktrees/ tidak ada" dihapus, diganti larangan
  bekerja di pohon publikasi plus resep sha256 di atas.
- §6: `git add`/`git commit` diizinkan, `gh`/`remote set-url`/`git config`/
  `**/.git/config` ditolak; ditambah penunjuk ke permukaan kedua yang lebih sempit
  (`asknexai-settings.json`) dengan catatan jangan disatukan.
- §10: daftar laporan dilengkapi, dan dokumen untuk pembaca luar dipisahkan ke `docs/`
  beserta alasan `bin/md2pdf.py` ada.
- §11: langkah Notion kini dimulai dengan "periksa kuota blok dulu".
- §12: status widget diperbarui ke "sudah ter-merge", berikut sisa pohon publikasi.
- §13–§14 (ditulis lebih awal hari ini) diperiksa ulang dan tetap akurat.

### Memory

- `project_ai_assistant_widget_rollout` — tiga klaim basi diperbaiki: "landing
  BLOCKED", "blocking constraint: no push credential", dan "Next: Fase 5". Ditambah
  update 19c berisi keadaan akhir dan metode salin-lalu-sha256.
- `github-connector-readonly` — ditulis ulang: kredensial tulis sekarang **ada**, dua
  token dirutekan per pemilik repo; konektor claude.ai sendiri tetap read-only.
- `notion-block-quota-exhausted` — baru; mencatat bahwa memperpendek dokumen tidak
  akan menolong, karena halaman satu blok pun ditolak.
- `telegram-two-bots` — baru; pemisahan peran kedua bot dan alasannya.
- `MEMORY.md` — tiga baris indeks disesuaikan.

## 3. Gate

| Suite | Hasil |
|---|---|
| `tests` | 381 OK |
| `ops/harness` · `nginx` · `n8n` · `feedback` | 11 · 20 · 10 · 29 OK |
| academy `./run-tests.sh` | 92 passed, 2 skipped |
| accreditation `test:widget` + `test:vanilla-shell` | GREEN |

## 4. Berikutnya

1. Rapikan pohon publikasi bila diinginkan (§1), atau biarkan `refresh.sh` yang
   melakukannya.
2. Kuota Notion — dokumentasi platform sudah siap terbit satu panggilan.
3. Rotasi tiga kredensial lama masih tertunda.
