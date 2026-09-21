# Rekonsiliasi Sprint 2 & 3 — NEXONE + Notion + weekly report

**Tanggal:** 2026-09-18
**PIC:** Imam (owner) · dikerjakan oleh sesi Claude Code (orchestrator)
**Pemicu:** permintaan owner — analisa file rekonsiliasi (Sprint-2-3-Task-Reconciliation-16-Sep-2026.html)
+ update Slack 2 minggu terakhir → rekonsiliasi ke NEXONE (Sprint 2 status + Sprint 3 baru)
→ weekly report ke Notion → notifikasi Telegram.

## Sumber data
- Slack `#daily-updates` (C0BPCCAQ8KC) & `#developments` (C0C027W19DE), ~3–18 Sep 2026,
  dibaca lewat konektor Slack sesi (bukan harness; `SLACK_BOT_TOKEN` belum dipasang).
- File rekonsiliasi HTML kiriman owner + MoM 15 Sep.
- Status live NEXONE.

## NEXONE — cara kerja
Browser extension tidak tersambung di sesi ini. Awalnya dipetakan lewat REST `/api/v1`
(hasil baca bundle SPA) untuk **read-only discovery**. Semua **write** akhirnya dilakukan
lewat **live UI pakai Playwright headless** (Node `playwright@1.63.0` dari
`/opt/nexora-prototypes/.../node_modules`, chromium-1243) — sesuai preferensi owner.
Login: user account owner. Token app disimpan di `sessionStorage` (bukan cookie), jadi tiap
script login ulang. Verifikasi tiap tulisan lewat GET API (read-back).

### Yang dibuat/diubah di NEXONE (bisa di-rollback)
Sprint model: `category` task = penanda sprint; kolom = status Kanban per-project.

**Sprint 2 (id=2, tidak dibuat baru — hanya ditambah task):** 30 → **36 task**.
- Dibuat baru + di-link ke Sprint 2:
  - P2 Audit Platform: task **428** "Pengembangan Module Document Request" (Done, cat "Sprint 2", Diky)
  - P2: task **429** "Pengembangan Module Task" (Done, Diky)
  - P2: task **430** "Pengembangan Module Document Approvals" (Development/On-Progress, Diky)
  - P12 NexOne: task **431** "Integrasi Slack–NEXONE–SUPPORT (two-way sync)" (Development, Imam)
- Task lama (sudah ada) hanya di-link ke Sprint 2, tanpa ubah status:
  - P1 CRM **#425** "Ganti Tom Select ke react-select" (deploy_to_production)
  - P1 CRM **#426** "Perbaikan bug create data di Company Detail" (deploy_to_production)

**Sprint 3 (id=3, DIBUAT BARU):** active, 2026-09-15 → 2026-09-26. Goal = 3 item OneAlpha-v2.
- Task final di **P26 "OneAlpha - Superapp"** (Development, cat "Sprint 3", Imam) + di-link ke Sprint 3:
  - **437** "Research & setup EverGauzy sebagai referensi rebuild OneAlpha"
  - **439** "Setup repository OneAlpha-v2"
  - **440** "Setup kebutuhan DevOps OneAlpha-v2"
- *Koreksi 2026-09-18 (permintaan owner):* awalnya dibuat di P3 (id 432/433/434). Karena NEXONE
  tidak punya fitur pindah-project via UI, task dibuat ulang di P26, di-link ulang ke Sprint 3,
  lalu 432/433/434 dihapus dari P3 (via trash icon UI). Delete task **tidak** mem-cascade link
  sprint → 3 SprintTask yatim (id 64/65/66) dibersihkan via `DELETE /internal-projects/sprints/3/tasks/{432,433,434}`.
  Untuk ke depan: **unlink dari sprint dulu, baru delete task**, atau langsung buat di project yang benar.

**Sprint 1:** TIDAK diubah (instruksi owner).

### Rollback NEXONE
Hapus task 428,429,430 (P2), 431 (P12), 437,439,440 (P26); unlink #425,#426 dari Sprint 2;
hapus Sprint 3 (id=3). Tidak ada data lama yang diubah kecuali penambahan link sprint.

### Keputusan penempatan
- Modul Diky ditaruh di P2 Audit Platform (project tempat Diky aktif + rumah kategori "Sprint 2").
- Integrasi ditaruh di P12 NexOne (sudah ada "Integration to Slack").
- Sprint 3 OneAlpha-v2 + EverGauzy → **P26 "OneAlpha - Superapp"** (final, sesuai arahan owner
  2026-09-18; P26 dibuat owner bersama project OneAlpha-v2 lain: KMS 21, Accreditation 22,
  Service Desk 23, Academy 24, Asset Management 25).

## Notion
Page **"Nexora September Sprint-2 Report"** dibuat di database **Doc Hub**
(collection 3cee4d6d-1d64-80b8-9ee2-000b45368095), pola sama dgn "Nexora August Sprint-1 Report".
URL: https://app.notion.com/p/3dfe4d6d1d64819db731d215d9691fdb
Properties: Nama dokumen, Kategori=["Guideline Docs and Reports"], Sumber="Manual".
Link ditambahkan di section "Reports" pada page "Guideline, Manual Book, Reports Docs"
(3cfe4d6d-1d64-81d7-8109-d286d6ba5bb3).
Catatan: workspace kena limit blok gratis (grace s/d 2026-09-18 06:54 UTC) — page tetap berhasil.

## Telegram
Ringkasan dikirim ke owner chat 6687943152 (message_id 73) via `sendMessage` (token dari
`/home/ahagent/AI-Workspace/.env` — catatan: `state.WORKSPACE` resolve ke `/root/AI-Workspace`,
jadi `tgcore.token()` tidak menemukan `.env` yang benar; dikirim manual via urllib).

## Catatan teknis untuk sesi berikutnya
- Preferensi owner: kerjakan NEXONE lewat **Playwright**, bukan tembak API langsung.
- Script Playwright ada di scratchpad sesi (`pw/lib.mjs`: login/createTask/editTaskColumn/addTasksToSprint).
- Peta API NEXONE (read-back/verifikasi): lihat memory `nexone-api-map`.
