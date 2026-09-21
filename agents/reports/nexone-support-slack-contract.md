# Kontrak sinkronisasi SUPPORT ↔ NEXONE ↔ Slack

**Keputusan scope dari Imam, 2026-09-13.** Dokumen ini mengikat task-011 (NEXONE) dan
task-012 (SUPPORT). Semua path relatif terhadap repo masing-masing di
`~/AI-Workspace/projects/nexora/`.

## Skenario target

1. Ticket dibuat di SUPPORT → otomatis membuat task di NEXONE → otomatis muncul di Slack.
2. Setiap perubahan di NEXONE → memperbarui ticket terkait di SUPPORT.
3. Slack bisa mengelola task NEXONE.

**Implikasi yang dinyatakan eksplisit** (menjawab pertanyaan terbuka Codex): task yang lahir
di NEXONE atau dari Slack `/task new` **tidak** otomatis menjadi ticket SUPPORT. Hanya task
yang punya tautan ke ticket SUPPORT yang ikut arus balik. Arah "buat" tetap satu pintu:
SUPPORT → NEXONE.

## Status sekarang terhadap skenario

| Skenario | Sudah ada di `dev` | Yang kurang |
|---|---|---|
| 1a. create task | `enqueueTicketCreated` dipanggil saat ticket dibuat (`app/api/tickets/route.ts:101`), outbox + retry/backoff (`lib/nexone/sync.ts:55,89`) | tidak ada yang menguras outbox — baru jalan kalau admin POST manual atau cron eksternal (`app/api/integrations/nexone/sync/route.ts:6`) |
| 1b. info ke Slack | dispatcher + thread-aware message (`Backend/internal/slack/dispatcher.go`) | dispatcher **membuang** aktivitas task non-sprint (`dispatcher.go` `processActivity`), dan task dari SUPPORT masuk Backlog, bukan sprint → tidak pernah sampai Slack |
| 2. NEXONE → SUPPORT | pull menerapkan perubahan kolom/status untuk task yang sudah tertaut (`lib/nexone/sync.ts:227,252`); echo suppression via `lastPushedAt` / `lastSeenRemoteUpdatedAt` (`prisma/schema.prisma` `TicketExternalLink`) | hanya kolom/status yang diterapkan; field lain diabaikan; tidak ada sinyal perubahan dari NEXONE (`GET .../tasks` hanya menerima `page,limit,q` — tanpa `updated_since`/cursor); kolom tak ter-map diam-diam inert (`sync.ts:277`); task terhapus tidak direkonsiliasi |
| 3. Slack manage task | selesai: `/task list|show|done|move|assign`, modal `/task new`, shortcut thread, RBAC, HMAC (commit `9665865`…`ac2d6c4`) | verifikasi manual live di `dev`; semua test masih mocked |

Ringkas: skenario 3 selesai, skenario 1 setengah, skenario 2 seperempat.

## Pekerjaan yang dibutuhkan

### NEXONE (task-011)

**N1 — tandai asal task.** `InternalTask` tidak punya kolom referensi eksternal
(`Backend/internal/models/models.go` `InternalTask`), sehingga tidak ada cara mengenali
"task ini dari ticket SUPPORT". Tambah `ExternalSource` + `ExternalRef` (+ index unik
gabungan) dan terima keduanya sebagai field opsional di endpoint create.
*Alternatif tanpa migrasi:* whitelist project/board di dispatcher — lebih murah tapi berisik
dan tidak bisa dipakai untuk korelasi. **Rekomendasi: pakai kolom.**
AC: create task dengan `external_source=support`, `external_ref=<ticketId>` tersimpan dan
terbaca di response list/show.

**N2 — dispatcher mengirim aktivitas task bertaut SUPPORT.** Ubah `processActivity` agar
mengirim ketika task sprint-linked **atau** `external_source != ""`. Reuse thread sudah ada
lewat `ensureThread`, jadi update berikutnya masuk thread yang sama gratis.
AC: satu ticket SUPPORT baru → satu pesan root di Slack; perubahan berikutnya jadi balasan
di thread yang sama, bukan pesan baru.

**N3 — sinyal perubahan keluar.** Tambah `updated_since` + cursor stabil pada
`GET /internal-projects/:id/tasks`. Ini paling murah karena SUPPORT sudah polling; webhook
outbox bisa menyusul kalau latensi polling terasa.
AC: SUPPORT bisa mengambil semua perubahan tanpa memindai seluruh board, idempoten, dan
aman diulang.

**N4 — normalisasi envelope.** `list` membungkus `{data,total,page,limit}`, sedangkan
`create/update/move` mengembalikan objek telanjang. Samakan, atau sediakan adapter di
SUPPORT. Severity MEDIUM, tapi harus diputuskan sebelum SUPPORT menulis `updateTask`.

### SUPPORT (task-012)

**S1 — scheduler.** Tanpa ini "otomatis" tidak pernah terjadi. Dua langkah:
kuras outbox segera setelah ticket dibuat (fire-and-forget, jangan blokir response), dan
pasang cron eksternal ke `scripts/nexone-sync.mts` sebagai jaring pengaman.
AC: ticket baru muncul di board NEXONE < 60 detik tanpa klik manual; kegagalan pulih di tick
berikutnya.

**S2 — inbound menerapkan semua field yang di-map.** Perluas `pullNexoneChanges` dari
kolom-saja ke title, description, priority, status, assignee sesuai `lib/nexone/mapping.ts`.
Tangani kolom tak ter-map secara eksplisit (log + biarkan, jangan diam) dan putuskan
perilaku untuk task terhapus.
AC: ubah judul + prioritas + kolom di NEXONE → ticket SUPPORT ikut berubah dalam satu pass.

**S3 — outbound update.** `lib/nexone/client.ts` hanya punya `getProject`, `createTask`,
`listTasks`. Tambah `updateTask`/`moveTask` dan enqueue saat ticket berubah. Skenario Imam
tidak menyebut arah ini secara eksplisit, tetapi tanpanya kedua sistem berpisah begitu ada
yang menyunting di SUPPORT. **Minimal: status.** Endpoint NEXONE-nya sudah tersedia dan
sekarang menganggur.

**S4 — proteksi loop, dengan test.** Fondasinya sudah ada; yang belum ada buktinya.
AC: `/task move` di Slack → kolom NEXONE berubah → ticket SUPPORT ter-update → SUPPORT
**tidak** mendorong balik ke NEXONE. Ditutup regression test, bukan pengamatan manual.

## Urutan yang disarankan

N1 → N2 (skenario 1 utuh) → N3 + S2 (skenario 2) → S1 (menjadikannya otomatis) → S3/S4 →
N4 kalau `updateTask` jadi dibangun. Skenario 3 tidak butuh kode baru, hanya verifikasi.

## Prasyarat di luar kode

- `SLACK_BOT_TOKEN`, `SLACK_CHANNEL_ID`, `SLACK_SIGNING_SECRET` terpasang di stack `dev`
  (CI sudah diplumbing lewat commit `676cdd1`).
- Akun service NEXONE untuk SUPPORT, plus id project dan id kolom Backlog yang dipakai.
- Semua test HTTP di kedua sisi masih mocked. Kontrak ini belum pernah diuji terhadap API
  NEXONE yang hidup — itu risiko terbesar yang tersisa, dan tidak bisa ditutup oleh unit test.
