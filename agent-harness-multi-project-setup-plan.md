# Plan Setup Agent Harness Multi-Project

## 1. Tujuan

Membangun lingkungan kerja lokal berbasis **Munder Difflin** untuk mengorkestrasi beberapa coding agent secara paralel. Sistem ini dapat digunakan untuk OneAlpha, OneDatahub, produk Nexora, project freelance, website, aplikasi pribadi, dan eksperimen teknologi lainnya.

Target utama:

- Satu command center untuk mengelola banyak agent.
- Pembagian pekerjaan berdasarkan peran: lead, frontend, backend, QA, review, DevOps, dan dokumentasi.
- Setiap agent bekerja pada project, branch, atau worktree yang terisolasi.
- Pekerjaan dapat berjalan paralel, terjadwal, dan dipantau.
- Semua perubahan tetap melalui kontrol dan persetujuan manusia.
- Context, aturan coding, hasil pekerjaan, dan dokumentasi tersimpan konsisten.

## 2. Gambaran Solusi

Munder Difflin adalah desktop harness lokal. Ia tidak menggantikan model AI, tetapi menjalankan CLI agent yang sudah terpasang pada komputer, seperti Codex, Claude Code, Gemini CLI, Qwen, OpenCode, dan lainnya.

```text
User / Imam
    |
    v
Command Center / Lead Agent
    |
    +-- Frontend Agent
    +-- Backend Agent
    +-- QA Agent
    +-- Code Review Agent
    +-- DevOps Agent
    +-- Documentation Agent
    |
    v
Project repositories, tests, reports, and pull requests
```

Referensi:

- Munder Difflin: https://github.com/chaitanyagiri/munder-difflin
- Website/download: https://munderdiffl.in
- Panduan instalasi: https://munderdiffl.in/blog/how-to-install-and-use-munder-difflin/
- OpenAI Codex: https://github.com/openai/codex

## 3. Prinsip Implementasi

### 3.1 Local-first

Project dan konfigurasi disimpan di komputer lokal. Prompt dan file yang dibaca agent tetap dapat dikirim ke provider AI yang digunakan, sehingga data sensitif harus dikendalikan dengan baik.

### 3.2 Human-in-the-loop

Pada tahap awal, agent wajib meminta persetujuan sebelum:

- Mengubah atau menghapus file penting.
- Menjalankan migrasi database.
- Mengubah konfigurasi server.
- Mengakses production.
- Melakukan push atau merge ke branch utama.

### 3.3 Isolated work

Jangan menjalankan beberapa agent pada folder dan branch yang sama secara bersamaan. Gunakan branch atau Git worktree per task untuk menghindari konflik.

### 3.4 Reviewable output

Setiap pekerjaan agent harus menghasilkan:

- Ringkasan perubahan.
- Daftar file yang berubah.
- Test yang dijalankan.
- Risiko atau hal yang belum selesai.
- Rekomendasi langkah berikutnya.

## 4. Engine AI yang Direkomendasikan

### Tier 1 — Codex

Gunakan Codex sebagai Lead Agent dan coding agent utama.

```bash
npm install -g @openai/codex
codex
```

Login dilakukan ketika Codex pertama kali dijalankan.

### Tier 2 — Claude Code

Claude Code dapat digunakan sebagai reviewer kedua jika memiliki subscription Claude. Perbedaan provider berguna untuk mendapatkan sudut pandang review yang lebih independen.

```bash
npm install -g @anthropic-ai/claude-code
claude
```

### Tier 3 — Opsional

- Gemini CLI: eksplorasi dan dokumentasi.
- OpenCode: open-source dan bring-your-own-model.
- Qwen/Ollama: eksperimen dengan model lokal.
- GitHub Copilot CLI atau Cursor Agent: jika sudah digunakan.

Mulai dengan dua engine terlebih dahulu: Codex dan satu reviewer alternatif.

## 5. Struktur Folder Global

Gunakan satu root folder khusus untuk semua project yang boleh diakses agent.

```text
~/AI-Workspace/
├── agents/
│   ├── shared-rules/
│   ├── prompts/
│   ├── task-templates/
│   └── reports/
├── projects/
│   ├── cbqa/
│   │   ├── onealpha-frontend/
│   │   ├── onealpha-backend/
│   │   └── onedatahub/
│   ├── nexora/
│   │   ├── nexone/
│   │   ├── nexone-erp/
│   │   ├── nexone-umkm/
│   │   └── nex-finance/
│   ├── freelance/
│   └── personal/
├── worktrees/
│   ├── onealpha-task-001/
│   ├── nexone-task-002/
│   └── freelance-task-003/
└── archives/
```

Pisahkan project kantor, freelance, dan pribadi. Jangan menambahkan seluruh home directory sebagai project ke harness.

## 6. Konfigurasi Munder Difflin

Saat onboarding:

1. Pilih mode technical.
2. Pilih folder kerja khusus, misalnya `~/AI-Workspace`.
3. Pilih Codex sebagai engine pertama.
4. Mulai dengan permission mode **Ask before changes**.
5. Tambahkan satu project sandbox kosong.
6. Uji satu task kecil sebelum menambahkan repository penting.

Setelah stabil, tambahkan project satu per satu. Pastikan command CLI bisa dijalankan secara manual sebelum dipakai oleh Munder Difflin.

## 7. Pembagian Peran Agent

### 7.1 Lead Agent — Michael / Codex

Tanggung jawab:

- Memahami permintaan pengguna.
- Memecah pekerjaan menjadi task kecil.
- Menentukan agent yang sesuai.
- Menjaga urutan dan dependency antar-task.
- Mengumpulkan hasil dan menyusun laporan.

Larangan:

- Tidak langsung mengubah production.
- Tidak menggabungkan perubahan tanpa review.
- Tidak membuat asumsi bisnis tanpa menandainya sebagai asumsi.

### 7.2 Frontend Agent

Menangani React, Next.js, Angular, Ionic, Tailwind, responsive UI, accessibility, dan browser testing.

Output minimum:

- Screenshot atau hasil visual.
- Test lint/build.
- Daftar perubahan UI.

### 7.3 Backend Agent

Menangani Laravel/PHP, Spring Boot, Go/Fiber, Node.js, REST API, database, authorization, dan integration.

Output minimum:

- Endpoint atau service yang berubah.
- Migration/SQL jika ada.
- Unit/integration test.
- Catatan backward compatibility.

### 7.4 QA Agent

Menangani test plan, test case, API testing, E2E, regression, bug reproduction, dan acceptance criteria.

QA agent tidak boleh hanya menyatakan “sudah aman”. Ia harus menyebutkan test yang dijalankan dan hasilnya.

### 7.5 Code Review Agent

Meninjau:

- Clean code.
- Security.
- Error handling.
- Query dan performa.
- Duplikasi logic.
- Konsistensi arsitektur.
- Risiko perubahan terhadap modul lain.

### 7.6 DevOps Agent

Menangani Docker, CI/CD, environment, deployment checklist, logging, backup, monitoring, dan incident runbook.

DevOps agent hanya boleh bekerja pada staging atau environment simulasi sampai disetujui manusia.

### 7.7 Documentation Agent

Menangani PRD, technical design, API documentation, user journey, onboarding, handover, release note, dan changelog.

## 8. Pola Kerja Task

```text
Request
  -> Clarify assumptions
  -> Create task and acceptance criteria
  -> Implement in isolated worktree
  -> Run tests
  -> Independent review
  -> Human approval
  -> Merge / deploy staging
  -> Regression check
  -> Documentation and closure
```

### Template task

```markdown
# Task: [Judul]

## Project
[Nama project dan repository]

## Background
[Mengapa task ini diperlukan]

## Objective
[Hasil yang ingin dicapai]

## Scope
- [Yang termasuk]

## Out of scope
- [Yang tidak termasuk]

## Acceptance criteria
- [ ] ...
- [ ] ...

## Constraints
[Teknologi, aturan bisnis, atau batasan]

## Required checks
- [ ] Unit test
- [ ] Integration/API test
- [ ] Build/lint
- [ ] Regression review

## Final report
- Changes:
- Tests:
- Risks:
- Follow-up:
```

## 9. Aturan Project dengan AGENTS.md

Setiap repository sebaiknya memiliki `AGENTS.md` di root. File ini menjadi kontrak kerja agent.

Contoh isi:

```markdown
# Agent Instructions

## Project overview
[Deskripsi singkat project]

## Stack
- Frontend: ...
- Backend: ...
- Database: ...

## Commands
- Install: ...
- Test: ...
- Lint: ...
- Build: ...

## Rules
- Jangan mengubah migration lama tanpa persetujuan.
- Jangan menyimpan credential di repository.
- Jangan push langsung ke main.
- Semua perubahan harus memiliki test atau alasan jika test tidak tersedia.

## Architecture boundaries
[Layer dan modul yang boleh saling memanggil]

## Definition of done
- Code compiled.
- Test passed.
- No secret leaked.
- Documentation updated.
- Summary prepared.
```

Selain `AGENTS.md`, gunakan file berikut jika diperlukan:

```text
docs/
├── architecture.md
├── business-rules.md
├── api-contracts.md
├── deployment.md
└── known-issues.md
```

## 10. Workflow Berdasarkan Jenis Pekerjaan

### Feature baru

1. Lead membaca requirement.
2. Documentation Agent menyusun acceptance criteria.
3. Backend Agent menyiapkan API/data.
4. Frontend Agent mengimplementasikan UI.
5. QA Agent membuat dan menjalankan test.
6. Review Agent memeriksa perubahan.
7. Imam menyetujui merge dan staging deployment.

### Bug fixing

1. QA Agent mereproduksi bug.
2. Backend atau Frontend Agent mencari root cause.
3. Agent membuat regression test.
4. Perbaikan dilakukan pada worktree terpisah.
5. QA menguji skenario utama dan dampak samping.

### Clean code review

1. Review Agent memetakan masalah berdasarkan severity.
2. Agent tidak langsung melakukan refactor besar.
3. Refactor dipecah menjadi task kecil.
4. Test baseline dijalankan sebelum perubahan.
5. Setelah refactor, test dibandingkan dengan baseline.

### Dokumentasi atau analisis

1. Documentation Agent mengumpulkan context.
2. Lead memvalidasi scope dan audience.
3. Output dibuat dalam Markdown terlebih dahulu.
4. Jika diperlukan, hasil dikonversi menjadi DOCX, PDF, atau Slides.

## 11. Manajemen Git dan Worktree

Pola branch:

```text
main
└── develop
    ├── feature/onealpha-audit-scheduling
    ├── fix/nexone-invoice-total
    ├── chore/cleanup-api-validation
    └── docs/project-handover
```

Contoh worktree:

```bash
git worktree add ../worktrees/task-001 -b feature/task-001 develop
```

Aturan:

- Satu agent aktif pada satu worktree.
- Jangan menjalankan dua agent yang mengubah file sama secara paralel.
- Commit harus kecil dan deskriptif.
- Merge dilakukan setelah QA dan review.
- Jangan memberikan credential production ke agent coding.

## 12. Schedule dan Automation

Schedule yang berguna:

- Daily repository health check.
- Daily review terhadap failed CI/CD.
- Weekly dependency/security review.
- Weekly clean code backlog.
- Weekly documentation drift check.
- Release checklist sebelum staging atau production.

Contoh instruksi schedule:

```text
Setiap Senin pukul 09.00, periksa repository aktif.
Laporkan branch yang tertinggal, failed pipeline, dependency rentan,
test yang gagal, dan dokumentasi yang belum diperbarui.
Jangan mengubah kode atau melakukan merge otomatis.
```

Gunakan trigger hanya untuk pekerjaan yang aman dan dapat diaudit. Hindari auto-deployment production pada fase awal.

## 13. Keamanan

Checklist minimum:

- [ ] Gunakan folder project yang eksplisit.
- [ ] Mulai dengan mode approval.
- [ ] Jangan memasukkan `.env`, private key, token, atau password ke prompt.
- [ ] Tambahkan secret file ke `.gitignore`.
- [ ] Gunakan akun database read-only untuk analisis.
- [ ] Pisahkan local, staging, dan production credential.
- [ ] Nonaktifkan akses production untuk agent default.
- [ ] Review command destruktif sebelum dijalankan.
- [ ] Backup sebelum migration atau refactor database.
- [ ] Audit perubahan melalui Git.

Agent coding dapat menjalankan command dan mengubah file sesuai permission yang diberikan. Permission folder dan mode approval harus diperlakukan sebagai kontrol keamanan utama.

## 14. Rencana Pilot

### Hari 1 — Instalasi dan validasi

- Install Node.js LTS jika belum tersedia.
- Install Codex CLI dan login.
- Install Munder Difflin.
- Tambahkan project sandbox kosong.
- Jalankan satu task dokumentasi sederhana.

### Hari 2 — Project nyata berisiko rendah

- Tambahkan satu repository non-production.
- Tambahkan `AGENTS.md`.
- Uji Lead Agent dan QA Agent.
- Uji branch/worktree.
- Validasi hasil report.

### Hari 3–4 — Multi-agent

- Tambahkan Frontend, Backend, Review, dan Documentation Agent.
- Uji satu enhancement kecil.
- Ukur durasi, token, error, konflik, dan kualitas output.

### Hari 5 — Standardisasi

- Finalisasi prompt dan template task.
- Buat checklist review.
- Buat aturan project per repository.
- Dokumentasikan cara recovery jika agent gagal.

## 15. Roadmap 30 Hari

### Minggu 1 — Foundation

- Munder Difflin berjalan stabil.
- Codex terhubung.
- Struktur workspace tersedia.
- Permission dan backup dasar selesai.

### Minggu 2 — Development workflow

- Agent role tersedia.
- `AGENTS.md` ditambahkan ke project utama.
- Workflow branch/worktree digunakan konsisten.

### Minggu 3 — QA dan review

- Template test case.
- Regression checklist.
- Code review otomatis sebagai draft.
- Security review dasar.

### Minggu 4 — Automation dan reporting

- Schedule health check.
- Weekly engineering report.
- Dashboard task dan agent.
- Evaluasi biaya, kualitas, dan waktu hemat.

## 16. KPI Keberhasilan

Ukur hal berikut setelah dua minggu:

- Waktu dari request sampai draft pertama.
- Persentase task yang selesai tanpa rework besar.
- Jumlah bug yang lolos QA.
- Jumlah konflik Git.
- Persentase test yang berhasil dijalankan.
- Waktu review manusia.
- Jumlah perubahan yang harus di-rollback.
- Penghematan waktu dibanding workflow manual.

Target awal:

- 2–4 agent aktif secara paralel.
- 100% perubahan melalui branch/worktree.
- 0 credential production diberikan ke agent.
- 100% task memiliki acceptance criteria.
- Semua perubahan penting memiliki ringkasan dan test result.

## 17. Konfigurasi Awal yang Disarankan

```text
Lead:          Codex
Coding:        Codex atau Claude Code
QA:            Codex dengan instruksi testing ketat
Review:        Claude Code/OpenCode atau Codex kedua
Concurrency:   Maksimal 4 agent
Permission:    Ask before changes
Production:    Tidak diizinkan
Merge:         Manual approval
Database:      Local/staging only
Schedule:      Report dan health check saja
```

## 18. Kesimpulan

Setup ini dapat menjadi virtual engineering office untuk project kantor, freelance, dan pribadi. Munder Difflin berfungsi sebagai orchestration layer, sedangkan source of truth tetap berada pada Git, requirement berada pada task atau dokumen resmi, dan keputusan akhir tetap berada pada manusia.

Implementasi awal paling aman adalah Codex + Munder Difflin dengan empat peran inti: Lead, Coding, QA, dan Review. Setelah workflow stabil, tambahkan DevOps, Documentation, schedule, memory, dan engine AI lain.

