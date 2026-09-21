# Panduan review: perubahan Slack ↔ NEXONE ↔ SUPPORT (14 Sep 2026)

Dua commit sudah mendarat di `dev`. Dokumen ini untuk kamu pakai saat mereview.

- NEXONE  `1e8708d..c762e41` → github.com/Nexora-Tech-Team/NEXONE
- SUPPORT `94351c5..085c650` → github.com/Nexora-Tech-Team/SUPPORT

Semua lolos sebelum push: NEXONE `go build` + `go vet` + `go test ./...`;
SUPPORT 185 test + lint + production build. Push lewat guard: pull-before-push
jalan dulu, `dev` diizinkan, `main` akan ditolak.

---

## Urutan review yang saya sarankan — dari yang paling berisiko

### 1. Migrasi kolom (RISIKO TERTINGGI — cek ini dulu)

`Backend/internal/models/models.go` — `InternalTask` dapat dua kolom baru:
`ExternalSource`, `ExternalRef`, plus **unique index gabungan**.

NEXONE pakai GORM `AutoMigrate`, jadi kolom ini akan dibuat otomatis saat
backend start. Yang perlu kamu pastikan:

- [ ] Jalankan dulu di staging, bukan langsung production
- [ ] Tabel `internal_tasks` besar? `ADD COLUMN` + index unik bisa mengunci tabel
- [ ] Kedua kolom nullable — task lama tidak terpengaruh, tapi pastikan sendiri
- [ ] Index unik menolak dua task dengan (source, ref) sama. Kalau ada data lama
      yang kebetulan bentrok, migrasi gagal. Cek: tidak akan ada, karena kolom
      ini baru — tapi verifikasi kalau kamu pernah punya kolom serupa

Rollback: drop dua kolom itu. Tidak ada data lama yang ditulis ulang.

### 2. Perubahan perilaku Slack (paling terlihat user)

`Backend/internal/slack/dispatcher.go` — **ini perubahan perilaku, bukan fitur baru.**

Sebelum pekerjaan ini: hanya task sprint-linked yang dikirim ke Slack.
Agent sebelumnya mengubahnya jadi **kirim semua** task activity — itu varian
yang kontrak sebut berisik dan tidak direkomendasikan. Saya persempit jadi:
kirim kalau **sprint-linked ATAU external_source terisi**.

Yang perlu kamu cek sendiri:

- [ ] Channel Slack kamu TIDAK banjir setelah deploy. Kalau banjir, berarti
      ada task yang tidak kamu duga punya external_source
- [ ] Task internal biasa (tanpa sprint, tanpa link SUPPORT) tetap TIDAK muncul
- [ ] Task sprint tetap muncul seperti sebelumnya — ini yang paling mungkin
      regresi tanpa disadari

Test yang menjamin ini: `Backend/internal/slack/dispatcher_test.go` —
tiga kasus (linked kirim + reply ke thread yang sama, unlinked skip tapi tetap
di-stamp, sprint tetap kirim).

### 3. Endpoint list task dapat parameter baru

`GET /internal-projects/:id/tasks` sekarang menerima `updated_since` (RFC3339)
dan `cursor`, mengembalikan `next_cursor`.

- [ ] Tanpa parameter, perilakunya harus persis sama seperti sebelumnya —
      frontend Kanban tidak boleh berubah sama sekali
- [ ] `updated_since` batas bawahnya inklusif (>=), jadi baris yang ditulis di
      detik yang sama tidak terlewat. Pemanggil de-dup pakai id

### 4. SUPPORT: ticket kini terdorong otomatis

`lib/nexone/index.ts` → `scheduleNexoneSync()`, dipanggil di
`app/api/tickets/route.ts` setelah ticket dibuat.

- [ ] Response create ticket TIDAK melambat — push jalan setelah response dikirim
- [ ] NEXONE mati → ticket tetap terbuat normal, error hanya masuk log
- [ ] Kegagalan ditelan sengaja; cron pass berikutnya yang jadi jaring pengaman

### 5. SUPPORT: inbound kini menerapkan priority

`lib/nexone/sync.ts` — dulu hanya kolom/status, sekarang status + priority,
masing-masing dapat audit row sendiri.

- [ ] Ubah priority di NEXONE → ticket SUPPORT ikut berubah
- [ ] Kolom/priority yang tidak ter-map sekarang muncul di log sebagai WARN,
      bukan diam. Kalau log kamu ramai WARN, berarti ada mapping yang kurang

---

## Tiga hal yang SENGAJA belum saya kerjakan

Saya lebih baik bilang ini daripada kamu menemukannya sendiri nanti.

**1. SUPPORT belum memakai `updated_since`.** Sisi server NEXONE sudah siap,
tapi `lib/nexone/client.ts` masih `listTasks()` tanpa watermark — saya
verifikasi: 0 kemunculan `updated_since`/`next_cursor` di client SUPPORT.
Artinya skenario 2 jalan, tapi masih memindai seluruh board tiap pass.
Belum jadi masalah di volume sekarang; akan jadi masalah kalau board membesar.

**2. Title, description, assignee TIDAK disinkronkan dari NEXONE ke SUPPORT.**
Kontrak menyebut lima field; saya kirim dua (status, priority). Alasannya:
`mapping.ts` tidak punya mapping inbound untuk tiga sisanya, dan menerapkannya
mentah-mentah akan MERUSAK data — judul NEXONE berisi prefix ref ticket,
description punya footer URL, dan tidak ada pemetaan identitas user antara
kedua sistem. Ini butuh keputusan mapping dulu, bukan kode dulu.

**3. Belum pernah diuji ke API NEXONE yang hidup.** Semua test HTTP di kedua
sisi masih mock. Kontrak sudah menyebut ini "risiko terbesar yang tersisa" dan
itu masih benar. Test hijau TIDAK membuktikan integrasinya jalan end-to-end.

---

## Yang saya perbaiki tapi bukan bagian dari scope

`app/api/tickets/[id]/route.ts` — pekerjaan S3 dari agent sebelumnya memakai
`db.$transaction` dengan array campuran, yang tidak bisa di-type TypeScript.
**SUPPORT tidak bisa di-build sama sekali.** Saya ganti ke bentuk interaktif.
Efek sampingnya bagus: baris outbox dan update ticket sekarang commit bersama,
jadi push tidak pernah diantrikan untuk tulisan yang ternyata rollback.

---

## Perintah verifikasi

    # NEXONE
    cd ~/projects/internal/NEXONE/Backend
    go build ./... && go vet ./... && go test ./...

    # SUPPORT
    cd ~/projects/internal/SUPPORT
    npm test && npm run lint && npm run build

    # Lihat persis apa yang berubah
    git -C ~/projects/internal/NEXONE  log -1 -p c762e41
    git -C ~/projects/internal/SUPPORT log -1 -p 085c650

## Prasyarat sebelum ini benar-benar jalan di dev

- `SLACK_BOT_TOKEN`, `SLACK_CHANNEL_ID`, `SLACK_SIGNING_SECRET` di stack dev
- Akun service NEXONE untuk SUPPORT, plus project id dan column id Backlog
- Tanpa itu, fitur nonaktif tanpa error (konsisten dengan konvensi SMTP/WhatsApp)
