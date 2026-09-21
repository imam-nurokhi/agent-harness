# 2026-09-19 — Dua bot, dua peran: AI Assistant read-only dan jalur PR ber-approval

**Diminta owner:** (1) bot mana yang dipakai AI Assistant untuk accreditation dan
academy, jadikan auto-mode tapi hanya untuk membaca berkas lalu merangkum, dengan
bahasa non-teknis untuk manajemen; (2) `@AgentNexoraBot` juga bisa tanya-jawab
bebas, bedanya bisa mengeksekusi pekerjaan development dan mengelola repo GitHub,
dengan aturan commit+push ke branch baru, PR hanya ke `dev`, merge hanya setelah
approval owner lewat Telegram; (3) PAT GitHub disimpan di `.env`; (4) `/exit`
harus terinfo ke Telegram dan unit memakai `Restart=always`.

**Hasil:** keempatnya terpasang dan terverifikasi. Blocker PAT yang sempat muncul
sudah dibuka owner pada hari yang sama (§6), dan seluruh rantai GitHub kemudian
dijalankan end-to-end sampai PR ter-merge lewat ketukan Approve owner (§9).
Satu hal tertahan di luar kendali kita: Notion kehabisan kuota blok (§10).

---

## 1. Koreksi premis: widget AI Assistant tidak memakai telegram bot

Pertanyaan "AI Assistant untuk accreditation dan academy pakai telegrambot yang
mana" punya dua jawaban, dan keduanya perlu dikatakan:

- **Widget di dalam aplikasinya tidak memakai bot apa pun, dan tidak memakai model
  bahasa sama sekali.** `src/widget/core/engine.js` mencocokkan pertanyaan dengan
  aturan yang di-generate (`knowledge.generated.js`); satu-satunya panggilan
  jaringan di seluruh widget adalah `collector.js` yang mengirim telemetri ke
  `/widget-feedback/`. Tidak ada jalur ke Telegram, dan tidak ada LLM — itu
  sebabnya `CLARIFICATION_NEEDED` menjadi daftar celah pengetahuan, bukan jawaban
  karangan. Keputusan "LLM sungguhan di balik widget" masih **ditunda owner**
  (CLAUDE.md §12).
- **Untuk tanya-jawab di Telegram, botnya adalah `@AskNexAIBot`** — sesi Claude
  Code yang dijembatani Channels. Itulah yang dikonfigurasi di laporan ini.

Satu-satunya keterkaitan lama antara widget dan Telegram adalah digest mingguan
`ah-feedback-digest.timer`, yang dikirim lewat `@AgentNexoraBot`.

## 2. `@AskNexAIBot` menjadi AI Assistant non-teknis, read-only, auto mode

| Bagian | Sebelum | Sesudah |
|---|---|---|
| Direktori kerja | `~/AI-Workspace` (CLAUDE.md teknis, isi ops) | `~/ask-nexai` (CLAUDE.md persona) |
| Permission mode | `manual` — setiap tool call jadi tombol Approve | `auto` — tidak pernah ada tombol |
| Izin | penuh (sesi ops) | `ops/channels/asknexai-settings.json` |
| Audiens | owner | manajemen/asesor non-teknis |

**Mengapa `auto` justru lebih aman di sini.** Pengguna non-teknis tidak punya dasar
untuk menilai tombol "Approve tool call", dan plugin channel dengan senang hati
merelainya ke chat mereka. Karena itu permukaannya dipersempit sampai tidak ada
yang bisa meminta izin: `deny` menang di semua mode, dan yang di-deny adalah
`Bash` (seluruhnya), `Write`, `Edit`, `WebFetch`, `WebSearch`, `Task`, seluruh
konektor Slack/Notion/Linear/GitHub/Context7, serta pembacaan `.env`, `~/.claude`,
`~/.ssh`, `/root`, `/etc`, `/var`, dan `~/AI-Workspace`. Yang tersisa: `Read`,
`Grep`, `Glob` di dua direktori yang di-`--add-dir`.

**Diukur, bukan diasumsikan.** Dengan `--permission-mode auto` dan settings itu,
sesi diminta menjalankan `echo HALO` dan menulis `/tmp/bukti.txt`. Jawabannya:
"There's no Bash/PowerShell or file-write tool available to me in this session",
dan `/tmp/bukti.txt` tidak pernah ada. Deny memang mengalahkan auto.

Persona-nya di `~/ask-nexai/CLAUDE.md`: Bahasa Indonesia, 3–6 kalimat, tanpa nama
berkas/kode/istilah teknis, jujur bila dokumennya tidak memuat jawabannya, dan
mengarahkan permintaan tindakan ke `@AgentNexoraBot`. Sumbernya dokumen produk
nyata (PRD, proses bisnis, RBAC, data model, plus `knowledge.generated.js` kedua
aplikasi). Uji coba dengan pertanyaan gaya manajemen ("aplikasi ini untuk apa,
siapa yang memakai") menghasilkan jawaban yang benar sesuai RBAC dan berakhir
dengan tawaran pertanyaan lanjutan — tanpa satu pun istilah teknis.

### Jebakan yang muncul saat memindahkan direktori kerja

Direktori kerja baru memicu dialog **"Do you trust this folder?"**, dan sesi
berhenti di situ: unit `active`, tmux hidup, Telegram diam. Diperbaiki lewat
config (`~/.claude.json`, entri proyek `hasTrustDialogAccepted`), bukan dengan
mengetik ke pane. Pelajaran umumnya: setiap ganti `WorkingDirectory` untuk sesi
Claude Code yang tak berpengawas, pre-trust dulu direktorinya.

## 3. `/exit` kini berbunyi, dan unit memakai `Restart=always`

`Restart=on-failure` tidak menangkap `/exit`: sesi keluar dengan status 0, jadi
systemd menganggapnya selesai dengan baik dan tidak menghidupkan ulang. Sekarang:

- `Restart=always` + `RestartSec=10`, dengan `StartLimitIntervalSec=300` /
  `StartLimitBurst=5` supaya konfigurasi rusak tidak berubah menjadi loop yang
  membanjiri Telegram.
- `bin/channel_notify.py` dipanggil dari `ExecStartPost` (🟢 online) dan
  `ExecStopPost` (🔴 terputus, menyebut `/exit`, crash, dan restart). Ia membaca
  token dari `~/.claude/channels/telegram/.env` — **bukan** `tgcore.py`, yang
  bicara untuk bot yang lain — dan penerimanya persis allowlist channel.
- Terbukti: restart menghasilkan `channel_notify: down -> 6687943152: sent` lalu
  `up -> … sent` di jurnal, dan kedua pesan sampai di chat owner.

Tes: `tests/test_channel_notify.py` (8).

## 4. `@AgentNexoraBot`: teks biasa kini menjadi pekerjaan

`tgbot.py:150` dulu membuang setiap pesan tanpa `/` — tidak ditolak, tidak
dicatat, hilang begitu saja. Sekarang teks biasa (khusus role **owner**) masuk ke
`bin/lib/tgchat.py`: role opsional di kata pertama (`backend perbaiki login`),
konteks 4 giliran terakhir per chat diputar ulang supaya pertanyaan lanjutan
nyambung, lalu `jobs.spawn()` seperti `/ask`.

Yang **tidak** berubah: izin agent. Prompt-nya juga menyatakan eksplisit bahwa
agent tidak boleh push/PR/merge dan harus menyerahkannya ke `/push` milik owner.

## 5. Jalur GitHub: branch baru → PR ke `dev` → merge hanya lewat tombol

`bin/lib/ghflow.py` adalah satu-satunya tempat aturan ini ditulis:

1. **Push hanya ke branch `ah/<task>-<stamp>` yang baru.** Nama dicetak oleh
   harness, jadi agent tidak bisa memilih `dev`.
2. **PR hanya boleh menargetkan `dev`** — allowlist, bukan blocklist, sehingga
   branch terlindungi yang baru besok tetap aman tanpa ubah kode.
3. **Merge butuh approval yang tercatat dari tombol Telegram.** `merge()` menolak
   sebelum menyentuh jaringan bila tidak ada berkas approval, dan approval terikat
   pada **head SHA** yang ditampilkan ke owner — PR yang berubah setelah
   di-approve harus di-approve ulang.

Permukaan chat-nya (`bin/lib/tggh.py`): `/push <task> <org/repo> [judul]` (push +
buka PR sekaligus), `/pr`, `/prs`, `/merge` (menampilkan ringkasan PR + tombol
✅/✖️). Tombolnya memeriksa ulang role penekannya — sebuah tombol hidup di dalam
pesan, dan pesan bisa ditekan siapa pun yang ada di chat itu.

Perubahan aturan yang menyertainya:

- `pushgate.py` **tidak lagi** bisa push ke `dev`/`staging`. Modul dan tesnya
  ditulis ulang; file tes yang dulu menegaskan `validate_target("dev")` diizinkan
  kini menegaskan sebaliknya, sengaja.
- `pushgate.plan()` menolak worktree yang masih kotor: push mengirim HEAD, jadi
  perubahan yang belum di-commit akan diam-diam absen dari PR yang di-approve.
- `protect.sh` menambahkan `dev` ke `PROTECTED_BRANCHES`, dan hook pre-push
  terpasang di kedua klon baru.
- `ops/harness/claude-settings.json`: `git add`/`git commit` **diizinkan** (agent
  mencatat pekerjaannya sendiri), sementara `git push`, `gh`, `git remote set-url`,
  `git config`, dan pembacaan `**/.git/config` **ditolak**. Commit itu lokal;
  menerbitkan tidak.
- `~/.gitconfig` dibuat dengan identitas mesin "Nexora Agent Harness" — tanpa itu
  `git commit` agent gagal, dan gagalnya akan tampak sebagai push HEAD lama.

Tes: `tests/test_ghflow.py` (30), `tests/test_push_gate.py` (12),
`tests/test_telegram_freeform_and_merge.py` (18).

## 6. ~~Blocker: PAT tidak bisa menulis~~ — dibuka owner, lalu diverifikasi

**Diselesaikan hari yang sama.** Owner memperbarui PAT lama dan menambahkan satu
token organisasi (`GITHUB_ORGS_PAT`). Pembagiannya ternyata tegas, dan diukur:

| Token | Bisa menulis di | Ditolak di |
|---|---|---|
| `GITHUB_PAT` | `Nexora-Tech-Team/*` (akun personal) | repo organisasi → 403 |
| `GITHUB_ORGS_PAT` | `NexoraTechTeam/*` (organisasi) | — |

`ghflow.token(repo)` kini merutekan berdasarkan pemilik repo: override
`GITHUB_PAT_<OWNER>` → `GITHUB_ORGS_PAT` untuk pemilik yang terdaftar sebagai
organisasi → `GITHUB_PAT`. Mengirim token yang salah menghasilkan
`403 "Resource not accessible by personal access token"`, yang terbaca seperti
token rusak padahal hanya salah alamat — karena itu perutean ini diuji
(`tests/test_ghflow.py`, 33 tes).

**Dua cara memeriksa izin tulis tanpa menulis apa pun**, keduanya dipakai di sini:
`git push --dry-run`, dan `POST /pulls` dengan head yang tidak ada (422 berarti
izin ada, 403 berarti tidak). Keduanya tidak meninggalkan jejak di repo.

### Catatan lama (dipertahankan karena jebakannya berulang)

`GITHUB_PAT` ada di `.env` dan **berfungsi untuk membaca** — `ghflow.list_prs`
mengembalikan `ok` untuk `NexoraTechTeam/academy` dan `…/accreditation`, dan 27
repo terlihat dari kedua organisasi. Tetapi push sungguhan ditolak GitHub:

```
remote: Permission to NexoraTechTeam/academy.git denied to Nexora-Tech-Team.
fatal: … The requested URL returned error: 403
```

Sebabnya: tokennya **fine-grained** (`github_pat_…`, 93 karakter) dan izinnya
kurang. Endpoint `collaborators/…/permission` menjawab "Resource not accessible by
personal access token" — tanda klasik cakupan yang belum diberikan. Blok
`permissions` pada `GET /repos/...` yang menampilkan `push: true` itu **peran
akun**, bukan cakupan token; ini persis jebakan "200 bukan verifikasi" di
CLAUDE.md §4.

Yang dibutuhkan pada token:

- **Contents: Read and write** (untuk push)
- **Pull requests: Read and write** (untuk membuka dan merge PR)
- **Metadata: Read** (wajib)

Dan satu hal struktural: sebuah fine-grained PAT hanya melayani **satu resource
owner**, sedangkan targetnya dua (`Nexora-Tech-Team` akun personal,
`NexoraTechTeam` organisasi). Jadi kemungkinan besar perlu **dua token**, atau satu
classic PAT ber-scope `repo`. Kode sudah disiapkan untuk keduanya:
`ghflow.token(repo)` memilih `GITHUB_PAT_<ORG>` bila ada, dan jatuh ke
`GITHUB_PAT` bila tidak.

Sampai itu dibereskan, `/push`, `/pr`, dan `/merge` akan menjawab dengan pesan
403 dari GitHub, bukan diam.

## 7. Yang berubah di host

| Perubahan | Lokasi | Rollback |
|---|---|---|
| Persona assistant | `/home/ahagent/ask-nexai/CLAUDE.md` | hapus direktori |
| Izin assistant | `ops/channels/asknexai-settings.json` | hapus berkas |
| Unit di-rewrite | `~/.config/systemd/user/ah-channel-telegram.service` | kembalikan `WorkingDirectory`, `--permission-mode manual`, `Restart=on-failure` |
| Trust direktori baru | `~/.claude.json` (entri `ask-nexai`) | hapus entri; cadangan `~/.claude.json.bak-*` |
| Notifikasi naik/turun | `bin/channel_notify.py` | hapus `ExecStartPost`/`ExecStopPost` |
| Tanya-jawab bebas | `bin/lib/tgchat.py`, `tgbot.py` | kembalikan guard `text.startswith("/")` |
| Jalur GitHub | `bin/lib/ghflow.py`, `tggh.py`, `pushgate.py`, `tgcmd.py`, `tgcore.py`, `tgbot.py` | hapus modul baru, kembalikan `pushgate.py` versi dev/staging |
| Izin agent | `ops/harness/claude-settings.json` | cabut `git add`/`git commit` |
| Identitas commit | `/home/ahagent/.gitconfig` | hapus berkas |
| `dev` jadi branch terlindungi | `bin/lib/protect.sh` + hook di 2 klon | `ah protect uninstall` |
| Klon repo | `projects/academy`, `projects/accreditation` | hapus direktori |

Klon awalnya menanamkan token di `.git/config` (efek samping `git clone` dengan
URL berkredensial); remote-nya langsung ditulis ulang ke URL polos dan diperiksa —
tidak ada berkas di `projects/` yang memuat token. `ghflow` menyusun URL
berkredensial di memori saat push, lalu menyensornya dari setiap keluaran.

## 8. Gate

| Suite | Hasil |
|---|---|
| `tests` | **366** OK (dari 305: +8 notify, +30 ghflow, +18 freeform/merge, +5 pushgate) |
| `ops/harness/tests` | 11 OK |
| `ops/nginx/tests` | 20 OK |
| `ops/n8n/tests` | 10 OK |
| `ops/feedback/tests` | 29 OK |

Verifikasi hidup: `ah-telegram` aktif tanpa traceback, menu slash berisi **42**
perintah termasuk `/pr`, `/prs`, `/merge`; `ah-channel-telegram` aktif dengan
`auto mode on` dan header `Claude Team`; notifikasi 🔴/🟢 sampai ke chat owner.

## 9. Uji end-to-end sungguhan — selesai, termasuk ketukan manusianya

Dijalankan pada repo produksi `NexoraTechTeam/academy`, bukan simulasi:

1. `ah task new` → **task-018**; `ah wt add` → worktree dari branch `dev`.
2. Satu berkas dokumentasi ditulis, lalu di-commit **b45eee2** atas nama identitas
   mesin "Nexora Agent Harness".
3. `tggh.cmd_push('task-018 NexoraTechTeam/academy …')` → branch
   **`ah/task-018-20260919-201033`** ter-push, dan **PR #1 → `dev`** terbuka.
4. `ghflow.merge()` dipanggil **tanpa** approval → ditolak:
   *"belum ada approval dari Telegram untuk PR ini"*, tanpa satu pun permintaan ke
   GitHub.
5. Kartu approval dikirim ke Telegram owner; owner menekan **✅ Approve**; bot
   menjalankan merge lewat `handle_callback`. **PR #1 = MERGED.**

Artinya seluruh rantai — termasuk gerbang manusia yang menjadi inti aturan ini —
sudah terbukti bekerja, bukan hanya lolos unit test.

## 10. Dokumentasi platform: terkirim ke Telegram, tertahan di Notion

Dua berkas disusun dan dikirim ke Telegram owner (`output/2026-09-19/`):

- `Nexora-Platform-E2E-2026-09-19.md` — dokumen end-to-end 9 bagian: widget AI
  Assistant, `agents.nexoratech.co` (accreditation, academy, harness, n8n),
  integrasi Telegram, keamanan, cara verifikasi, status.
- `Ringkasan-Platform-AI-Nexora-2026-09-19.pdf` — ringkasan eksekutif 3 halaman
  untuk pembaca non-teknis.

**PDF dibuat tanpa dependensi baru.** Host ini tidak punya pandoc, weasyprint,
reportlab, bahkan modul `markdown` sekalipun, dan ia dipakai bersama vhost lain —
memasang toolchain untuk satu ringkasan berkala lebih mahal daripada menulisnya.
`bin/md2pdf.py` menulis PDF 1.4 langsung (Helvetica/Courier bawaan, WinAnsi,
tabel lebar huruf asli, transliterasi untuk glyph di luar WinAnsi seperti panah
dan emoji). Tesnya (`tests/test_md2pdf.py`, 12) memeriksa hal yang benar-benar
rusak diam-diam: **setiap offset di tabel xref harus menunjuk ke objeknya**, dan
markup inline tidak boleh tercetak mentah — cacat nyata yang tertangkap:
`` **cabang `dev`** `` sempat mencetak backtick karena alternasi bold menang duluan.

**Notion tertahan di luar kendali kita.** `notion-create-pages` menjawab
*"Your workspace has used all of its free blocks"*. Diuji ulang dengan halaman
satu blok — ditolak juga, jadi ini batas kuota workspace, bukan soal ukuran
dokumen. Isi halaman sudah disiapkan lengkap di
`output/2026-09-19/notion-ready-doc-hub.md`; begitu kuota tersedia, tinggal satu
panggilan ke data source Doc Hub dengan `Kategori=["Guideline Docs and Reports"]`,
`Sumber="Manual"`, lalu tautannya dipasang di bagian **Reports** pada "Guideline,
Manual Book, Reports Docs". Owner sudah diberi tahu lewat Telegram.

## 11. Berikutnya

1. **Naikkan kuota Notion** (atau kosongkan blok lama), lalu terbitkan halaman
   yang sudah disiapkan — satu panggilan.
2. **Masukkan pekerjaan widget ke git.** Kredensial tulis kini terbukti bekerja,
   jadi hambatan terakhir untuk "yang tayang = yang ada di git" sudah hilang.
3. Bila `@AskNexAIBot` akan dibuka untuk pengguna non-developer, tambahkan chat
   mereka ke `~/.claude/channels/telegram/access.json` — dan ingat batasnya:
   siapa pun di allowlist berbicara dengan sesi yang sama.
4. Rotasi tiga kredensial lama (§7) masih tertunda.
