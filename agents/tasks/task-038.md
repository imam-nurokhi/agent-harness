# Task: NEXONE — self-registration grants full permissions (app_role_id NULL bypass)

- **ID:** task-038
- **Project:** NEXONE (`~/projects/internal/NEXONE`)
- **Class:** nexora
- **Role:** backend
- **Worktree:** `~/AI-Workspace/worktrees/task-038`
- **Base branch:** main

> **JANGAN DIJALANKAN DULU.** Temuan ini dicatat atas permintaan owner pada
> 2026-09-15; eksekusi menunggu keputusan owner. Jangan claim, jangan buat
> worktree, jangan jalankan `ah run` untuk task ini sampai diinstruksikan.

## Background
Ditemukan 2026-09-15 saat menyiapkan akun service integrasi SUPPORT → NEXONE.

Dua hal bertemu dan saling meniadakan kontrol akses:

1. `POST /api/v1/auth/register` bersifat **publik** — tidak ada middleware auth,
   tidak ada undangan, tidak ada verifikasi email
   (`Backend/internal/server/server.go:48`). User baru dibuat dengan
   `Role: "member"` dan `AppRoleID` kosong (`Backend/internal/handlers/auth.go:104-112`).
2. `requirePermissions` **meloloskan semua permission** ketika `app_role_id` NULL:

   ```go
   // Backend/internal/middleware/permissions.go:42-45
   if user.AppRoleID == nil {
       c.Next()
       return
   }
   ```

   Artinya "belum punya role" diperlakukan sebagai "boleh segalanya", bukan
   "belum boleh apa-apa" — persis kondisi setiap user hasil register.

**Terbukti, bukan dugaan.** Akun `support@nexoratech.co` (user id 24) didaftarkan
lewat endpoint publik di `dev-nexone.nexoratech.co`, tanpa role apa pun, lalu:

| Endpoint | Status |
|---|---|
| `GET /api/v1/clients` | 200 |
| `GET /api/v1/dashboard` | 200 |
| `GET /api/v1/internal-projects/dashboard` | 200 |

Data klien terbaca penuh oleh akun yang mendaftarkan dirinya sendiri.

Endpoint internal-project **selamat secara kebetulan**, bukan karena middleware:
`InternalProjectHandler.canAccess` (`internal_project.go:29-38`) mengecek baris
`internal_project_members` secara terpisah, sehingga `GET /internal-projects/15`
tetap 403. Grup rute lain (`clients`, `dashboard`, `clusters`, dst.) tidak punya
cek kedua semacam itu.

Diverifikasi di dev. **Kode yang sama ada di `main`**, jadi produksi
(`nexone.nexoratech.co`) harus dianggap terdampak sampai dibuktikan sebaliknya.

## Objective
User yang mendaftar sendiri tidak memperoleh akses apa pun sampai seorang admin
memberinya role secara eksplisit.

## Scope
- `Backend/internal/middleware/permissions.go` — `app_role_id` NULL harus **ditolak**,
  bukan diloloskan (fail-closed).
- `Backend/internal/server/server.go` + `handlers/auth.go` — putuskan nasib
  `/auth/register` publik: dimatikan, dibatasi domain, atau diganti alur undangan admin.
- Audit satu kali: user existing dengan `app_role_id IS NULL` di DB prod dan dev —
  berapa, siapa, kapan dibuat, mana yang tidak dikenali.
- Periksa grup rute lain yang hanya bergantung pada permission middleware.

## Out of scope
- Mendesain ulang model RBAC/AppRole.
- Integrasi SUPPORT → NEXONE itu sendiri (jalur terpisah; lihat Constraints).

## Acceptance criteria
- [ ] User baru tanpa `app_role_id` mendapat **403** di `/clients`, `/dashboard`,
      dan `/internal-projects/dashboard` — dibuktikan dengan test, bukan pernyataan
- [ ] Ada test yang gagal pada kode lama dan lulus pada kode baru (tulis test dulu)
- [ ] Admin (`role = "admin"`) tetap lolos seperti sebelumnya
- [ ] User dengan AppRole yang sah tidak kehilangan akses mana pun — regresi login
      dan board dijalankan
- [ ] Nasib `/auth/register` diputuskan dan dieksekusi, tidak dibiarkan menggantung
- [ ] Hasil audit akun `app_role_id IS NULL` dilaporkan (jumlah + tindakan per akun)
- [ ] Suite lama tetap hijau

## Constraints
- **Akun `support@nexoratech.co` (dev, user id 24) harus tetap berfungsi.** Akun ini
  dipakai integrasi SUPPORT → NEXONE. Ia mengandalkan bypass yang akan ditutup, jadi
  perbaikan ini **wajib** memberinya AppRole eksplisit dengan `internal-project.projects`
  (read + edit) plus keanggotaan project, dalam perubahan yang sama. Kalau tidak,
  menutup lubang ini akan mematikan integrasi SUPPORT.
- Fail-closed adalah perubahan perilaku: setiap akun yang selama ini "jalan" karena
  `app_role_id` NULL akan kehilangan akses. Audit dulu, baru ubah.
- Produksi menyimpan data klien nyata. Audit DB read-only; tidak ada perubahan data
  tanpa persetujuan owner.

## Required checks
- [ ] Unit test (middleware permission, NULL role ditolak)
- [ ] Integration/API test (register → akses ditolak)
- [ ] Lint
- [ ] Build
- [ ] Diff reviewed for secrets and stray files

## Progress
- [x] Temuan diverifikasi di dev dengan akun nyata (2026-09-15)
- [ ] MENUNGGU KEPUTUSAN OWNER — jangan mulai

## Report
- Scope done:
- Files changed:
- Commands run + results:
- Tests:
- Risks:
- Not done / blocked:
- Suggested next task:
