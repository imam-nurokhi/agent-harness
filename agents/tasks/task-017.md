# Task: NEXONE: sinyal perubahan keluar (updated_since + cursor)

- **ID:** task-017
- **Project:** NEXONE (`~/AI-Workspace/projects/nexora/NEXONE`)
- **Class:** nexora
- **Role:** backend
- **Worktree:** `~/AI-Workspace/worktrees/task-017`
- **Base branch:** dev

## Background
Kontrak lengkap: `agents/reports/nexone-support-slack-contract.md` (item N3 dan N4).

SUPPORT tidak punya cara mengetahui apa yang berubah di NEXONE. `GET
/internal-projects/:id/tasks` hanya menerima `page`, `limit`, `q`, sehingga satu-satunya
cara adalah memindai seluruh papan setiap kali. Selain itu bentuk response tidak konsisten:
list membungkus `{data,total,page,limit}` sedangkan create/update/move mengembalikan objek
telanjang, jadi klien harus menebak bentuknya.

Bergantung pada task-016 hanya untuk kolom referensi eksternal; kalau task-016 belum
mendarat, kerjakan bagian `updated_since` lebih dulu dan sebutkan urutannya di Report.

## Objective
SUPPORT dapat mengambil persis perubahan sejak poll terakhir, berulang kali, tanpa
kehilangan satu pun dan tanpa memproses ulang yang sama.

## Scope
- Tambah parameter `updated_since` pada endpoint list task, dengan cursor stabil untuk
  paginasi yang tidak bergeser ketika data berubah di tengah pengambilan.
- Pastikan urutannya deterministik (misalnya `updated_at` lalu `id`) supaya cursor aman.
- Samakan bentuk response create/update/move dengan list, atau dokumentasikan keduanya
  secara eksplisit kalau menyamakan akan merusak konsumen lain — pilih satu dan catat alasannya.
- Dokumentasikan parameter baru di dokumentasi API yang sudah ada.

## Out of scope
- Webhook/outbox push (polling dulu; webhook menyusul kalau latensi terasa).
- Perubahan apa pun di repo SUPPORT.

## Acceptance criteria
- [x] `updated_since` mengembalikan hanya task dengan `updated_at` lebih baru, terbukti lewat test
- [x] Paginasi memakai cursor: mengambil seluruh halaman tidak melewatkan dan tidak menggandakan task meskipun ada task yang berubah di antara dua permintaan
- [x] Permintaan yang sama diulang menghasilkan hasil yang sama (idempoten), dibuktikan test
- [x] Bentuk response list/create/update/move konsisten, atau perbedaannya terdokumentasi dengan alasan
- [x] Dokumentasi API diperbarui sesuai perilaku nyata
- [x] `go test ./...`, `go vet`, `go build ./cmd/api` hijau dengan output dikutip

## Constraints
Baca `CLAUDE.md`/`AGENTS.md` NEXONE lebih dulu. Tanpa membaca rahasia, tanpa menyentuh
production. Perubahan bentuk response berpotensi merusak frontend NEXONE — periksa
pemakaiannya di `Frontend/` sebelum mengubah, dan kalau berisiko, pilih jalur adapter dan
jelaskan. Bekerja hanya di worktree ini. Jangan commit, jangan push.

## Required checks
- [x] Unit test
- [x] Integration/API test
- [x] Lint
- [x] Build
- [x] Diff reviewed for secrets and stray files

## Progress
- [x] Petakan pemakaian endpoint list di frontend dan SUPPORT
- [x] Implementasi `updated_since` + cursor
- [x] Test idempotensi dan paginasi di bawah perubahan
- [x] Keputusan envelope + dokumentasi

## Report
- Scope done:
- Files changed:
- Commands run + results:
- Tests:
- Risks:
- Not done / blocked:
- Suggested next task:
