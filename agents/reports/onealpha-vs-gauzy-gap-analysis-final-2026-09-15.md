# Gap Analysis Final — Ever Gauzy vs OneAlpha

**Tanggal:** 15 September 2026
**Untuk:** Bahan keputusan manajemen (rebuild OneAlpha)
**Penyusun:** Sesi analisis Claude Code — Imam Nurokhi

## Apa yang baru di dokumen ini

Dua dokumen sebelumnya (`onealpha-vs-gauzy-analysis.md`, `analyze_onealpha-vs-gauzy.md`)
menyatakan batasan yang sama: **repo OneAlpha private dan tidak bisa diakses**, sehingga profil
OneAlpha 100% bersumber dari dokumen plan, bukan dari kode.

Dokumen ini **menutup gap verifikasi tersebut**. Basis bukti:

| Sumber | Status verifikasi |
|---|---|
| `CBQAGLOBAL-CRM-FRONTEND` | ✅ dibaca langsung — 59 page module, menu tree `NavLinks.jsx`, 442 endpoint call |
| `CBQAGLOBAL-CRM-BACKEND` (Java) | ✅ dibaca langsung — ~161 entity, ~120 controller |
| `CBQAGLOBAL-CRM-BACKEND-GOLANG` (Go) | ✅ dibaca langsung — 3 modul, routing & auth |
| Ever Gauzy | ✅ **dijalankan lokal**, di-seed penuh, API di-probe (1.209 path Swagger) |

Konsekuensinya: **tiga klaim dalam dokumen sebelumnya perlu dikoreksi** (Bagian 2).

---

## 1. Ringkasan eksekutif

1. **Keputusan strategis tidak berubah:** Gauzy tetap **referensi arsitektur, bukan basis kode**.
   Verifikasi ke kode justru *memperkuat* kesimpulan itu.
2. **Tapi alasannya berubah.** Dokumen sebelumnya beralasan "OneAlpha jauh lebih kecil, adopsi
   Gauzy = overkill". Faktanya **skala keduanya setara** (OneAlpha ~161 entity Java vs Gauzy 175
   entity core). Alasan yang benar: OneAlpha **sudah punya** hampir semua yang bisa diberi Gauzy,
   dan yang tidak dimiliki Gauzy justru inti bisnis OneAlpha.
3. **Overlap riil turun drastis.** Setelah dibandingkan ke kode aktual, hanya **2 dari 9 modul**
   yang punya nilai adopsi nyata — dan keduanya *bukan* modul bernilai bisnis tertinggi.
4. **HRIS dan sebagian besar "Coming Soon" perlu diklarifikasi statusnya** — HRIS sudah ada
   backend + frontend yang cukup lengkap, bertentangan dengan asumsi "belum ready".
5. **Nilai terbesar Gauzy bagi OneAlpha sekarang: time-tracking→billing loop, model 2-level
   tenancy, dan pola MCP/AI** — bukan modul bisnis.

---

## 2. Koreksi terhadap dokumen analisis sebelumnya

| # | Klaim sebelumnya | Temuan dari kode | Dampak |
|---|---|---|---|
| **K1** | "OneAlpha jauh lebih kecil & spesifik dari Gauzy; adopsi penuh = overkill" | OneAlpha Java: **~161 entity, ~120 controller**; frontend **59 modul halaman, 442 endpoint call**. Skala **setara** Gauzy (175 entity core). | Argumen "overkill karena ukuran" **tidak valid**. Argumen yang benar: **duplikasi** — OneAlpha sudah punya CRM, PM, HRIS, Finance, RBAC, email, workflow sendiri. |
| **K2** | "Ada layanan **Go Audit** terpisah yang menangani sebagian API eksekusi audit" | Service Go **tidak menangani audit sama sekali**. Isinya **Project Management + HRIS + auth** (`/api/v1/pm/*`, `/api/v1/hris/*`). Seluruh domain audit ada di **Java** (`/api/audit/*`, `/api/v1/audit-*`). Go memvalidasi JWT terbitan Java (`lib/javaauth`), jadi **melengkapi, bukan menggantikan**. | Keputusan manajemen "pertahankan Go Audit sebagai bounded service" **salah sasaran**. Yang perlu diputuskan: masa depan **Go PM/HRIS** vs controller PM/HRIS yang **juga masih ada di Java** — ini overlap/migration frontier yang nyata. |
| **K3** | "HRIS belum ready / belum dibangun" | Backend: 8 entity (`HrisRecord, Attendance, Leave, Payroll, Performance, Expense, TaxBenefit, Tenure`) + controller `/api/hris/*`. Frontend: subtree penuh — Recruitment (10 halaman: manpower request → job requisition → vacancies → candidates → selection → offering → hiring approval → pre-onboarding → reports), Employee Mgmt, Organization (department, job title, grades, org structure, branch), competencies, employee documents. Hanya **Performance** yang "Coming Soon". | Rekomendasi "build vs buy HRIS" **sudah terlambat sebagai pertanyaan terbuka** — investasi sudah berjalan. Pertanyaan yang benar: *lanjutkan atau hentikan*, dan bagaimana menghindari duplikasi personel dengan Competency Management di Audit Platform. |
| **K4** *(tambahan)* | "Auth OneAlpha: Keycloak 25 + Entra SSO + OneDatahub" | Di kode saat ini: **JWT terbitan Java sendiri** (`security/jwt/`), refresh-token interceptor di frontend, Go memvalidasi JWT yang sama. Tidak ditemukan integrasi Keycloak/Entra di dua repo backend ini. | Keycloak/Entra adalah **target arsitektur**, bukan kondisi saat ini. Perlu ditegaskan di meeting agar estimasi effort auth tidak diremehkan. |

> Catatan kejujuran: K4 berdasarkan dua repo backend yang ada di mesin ini. Bila integrasi
> Keycloak berada di repo/gateway lain (mis. OneDatahub atau konfigurasi nginx/infra), klaim ini
> perlu dikonfirmasi ke tim infra — bukan dibantah dari dokumen ini.

---

## 3. Perbandingan per modul (sesuai sidebar OneAlpha aktual)

Skor overlap: ⬛⬛⬛ tinggi · ⬛⬛ sedang · ⬛ rendah · — nihil

| # | Modul OneAlpha | Status riil (kode) | Padanan Gauzy | Overlap | Rekomendasi |
|---|---|---|---|---|---|
| 1 | **Dashboard** (Combined) | Live | Dashboard + `dashboard-widget` | ⬛ | Native. Gauzy hanya referensi layout widget. |
| 2 | **CRM** — Prospect (Company/Leads/Proposals), Clients, Project, Expense, Sales (Invoice/Payment), Task, Reports | Live, **57 entity CRM** termasuk Proposal + Revision/History/Services/ApprovalTracking/CommercialTerm, SalesTarget, Contract, Workflow | `deal`, `pipeline`, `pipeline-stage`, `contact`, `invoice`, `payment`, `expense` | ⬛ | **Native.** OneAlpha jauh lebih kaya. ⚠️ `proposal` Gauzy = **job/freelance bid**, bukan penawaran komersial — false friend, dikonfirmasi ulang di instance lokal. |
| 3 | **Audit Platform** — 15 submenu (dashboard, clients, matrix, schedule, process, findings, form catalog/entry, output template, certificate monitoring, competency, finance confirmation, utilization, libraries, reconciliation, import review) | Live, **44 entity audit** + workflow state machine (`AuditWorkflow/Step/State/Transition`, stage-gate, TR decision) + form engine (`AuditTemplate/Field/FormDraft/FormEvidence` + autosave + evidence upload) + `AuditCertificate/Revision`, `Competency`, `PersonnelQualification`, `ImpartialityRule`, `AuditTrail` | **Nihil.** Probe ke 1.209 path Swagger instance lokal: tidak ada `audit`, `certificate`, `standard`, `finding`, `accreditation`, `competency` | — | **100% native.** Nilai bisnis tertinggi, referensi eksternal nihil. Gauzy `approval-policy` (single-stage) **tidak layak** jadi referensi state machine bertingkat. |
| 4 | **Project Management** — Dashboard, Projects, Timesheet, Library (kanban/tickets/templates/activity) | Live, di **Go** (`/api/v1/pm/*`: kanban, tasks, tickets, gantt, clock-in/out, time-logs, timesheets) **dan masih ada di Java** (`/api/v1/pm`) | `organization-project`, `project-module`, `sprint`, `task`, `time-log`, `timesheet`, `time-slot`, `daily-plan` | ⬛⬛⬛ | **Adopsi pola tertinggi** — khususnya rantai `time-log → timesheet → invoice-item → invoice → payment` yang belum tertutup di OneAlpha. ⚠️ Selesaikan dulu duplikasi PM Java vs Go. |
| 5 | **HRIS** — Recruitment (10 halaman), Employee Mgmt, Organization, Performance(soon) | **Live sebagian** (bukan "belum ready") | `employee`, `candidate` (+interview/feedback/source/skill/education), `time-off-request/policy`, `employee-award`, `employee-appointment`, `approval-policy` | ⬛⬛ | Skema ATS & time-off Gauzy matang dan bisa jadi referensi penyempurnaan. ⚠️ **Jaga batas**: personel HRIS ≠ `PersonnelQualification`/`Competency` milik Audit Platform. |
| 6 | **Academy** | Coming Soon | **Nihil** — tidak ada entity course/training/LMS | — | Jangan build LMS penuh. Batasi ke penugasan + tracking compliance, playback ke LMS eksternal. |
| 7 | **Knowledge Management** | Coming Soon | `help-center` + `help-center-article` (+versi artikel) — **sederhana**; sudah diuji di instance lokal | ⬛ | Beda kelas total vs spek Nexora (RAG, akses 5-dimensi, governance ISO 9001 cl.7.5, watermarking, audit trail append-only). Ambil hanya konsep *immutable article version*. |
| 8 | **Document Management** | Coming Soon | `organization-document` = **link URL + nama saja**, tanpa versi/retensi/approval (terverifikasi saat seeding) | ⬛ | ⚠️ **Ambiguitas scope wajib diputuskan:** duplikat dengan KMS, atau evidence-store Audit Platform? OneAlpha sudah punya `AuditFormEvidence`/`AuditDocument`/`ProjectDocument` — kemungkinan besar ini **sudah sebagian terbangun** di modul Audit. |
| 9 | **Asset Management** | Coming Soon | `equipment` + `equipment-sharing` + `equipment-sharing-policy` (request→approval→periode) — sudah diuji, berfungsi | ⬛⬛ | Cukup **kalau** scope = peminjaman aset kantor. **Tidak cukup** untuk depresiasi, maintenance, atau **kalibrasi alat ukur auditor** (tidak ada di Gauzy). |
| — | **Settings** — role/permission, approval workflow, rate mgmt, currency, format number, chart of account, email | Live | `role`, `role-permission` (1.592 baris seed), `email-template`, `accounting-template` | ⬛⬛ | Model permission enum Gauzy lebih bersih dari `JobtitlePermissionEntry`; layak jadi referensi refaktor RBAC. |

---

## 4. Yang ADA di Gauzy dan TIDAK ada di OneAlpha

Diverifikasi langsung di instance lokal yang sudah di-seed:

| Kapabilitas Gauzy | Nilai untuk OneAlpha |
|---|---|
| **Time-log → Timesheet → Invoice-item → Invoice → Payment** end-to-end | **Tertinggi.** Mengubah `AuditorUtilization` + timesheet PM jadi angka billable otomatis. Ini gap monetisasi paling konkret. |
| **Multi-tenant 2 level** (`tenant` → `organization`, `TenantOrganizationBaseEntity`) | OneAlpha hanya `company_id` + `Branch` scoping. Kalau "Master Tenant" jadi kebutuhan, ini blueprint siap pakai. |
| **Screenshot/activity tracking, time-slot** | Relevan untuk bukti utilisasi auditor lapangan. |
| **Goals/OKR + KPI** | OneAlpha punya SalesTarget saja; OKR lintas divisi belum ada. |
| **Equipment sharing** | Basis Asset Management (modul 9). |
| **MCP server + 12 plugin `ai-provider-*`** | Paling langsung applicable untuk roadmap AI/agent OneAlpha — bangun **satu kali**, pakai bersama KMS. |
| **Plugin architecture (67 plugin nyata)** | Referensi extension point bila OneAlpha mau modular. |

---

## 5. Temuan empiris dari menjalankan Gauzy (tidak ada di analisis sebelumnya)

Instance dijalankan lokal, di-seed penuh (12 employee, 17 contact, 8 project, 56 task, 115 time
log, 8 invoice, 4 deal, dst.) via REST API. Temuan kualitas:

1. **Endpoint rusak di rilis stabil** — `POST /api/merchants` balas `201` tanpa body dan **tidak
   mempersist baris**; `GET /api/merchants` balas `400 {}`.
2. **DTO tidak terdokumentasi** — banyak controller CRUD tanpa schema di Swagger; field wajib baru
   ketahuan dari pesan error runtime.
3. **Enum tidak konsisten antar modul** — invoice `FULLY_PAID`, expense `PAID`, sprint `active`,
   project-module `in-progress`.
4. **Validasi relasi longgar** — project duplikat nama bisa dibuat berulang tanpa penolakan.

**Implikasi:** menjadikan Gauzy *basis kode* berarti mewarisi utang kualitas ini ke produk
teregulasi (ISO/ISCC/LVV) yang justru menuntut ketertelusuran ketat. Memperkuat keputusan
"referensi saja".

---

## 6. Risiko

| Risiko | Tingkat | Mitigasi |
|---|---|---|
| **Lisensi AGPL-3.0** — copy kode/skema ke produk proprietary memicu copyleft | 🔴 Tinggi | Legal sign-off **sebelum** reference mining mendalam. Opsi lisensi komersial Ever Co. bila perlu. |
| **Duplikasi PM & HRIS antara Java dan Go** | 🔴 Tinggi | ADR khusus: tentukan service owner per domain, hentikan yang redundan. |
| **Duplikasi data personel**: HRIS Employee vs Audit `PersonnelQualification`/`Competency` | 🟠 Sedang | Satu sumber kebenaran identitas; kompetensi audit sebagai *overlay*, bukan salinan. |
| **Scope bertabrakan**: KMS vs Document Management vs AuditFormEvidence | 🟠 Sedang | Putuskan di meeting ini; jangan mulai development sebelum jelas. |
| **Ekspektasi manajemen** bahwa Gauzy mempercepat fitur inti | 🟠 Sedang | Sampaikan: Gauzy menutup **0%** kebutuhan Audit Platform. |
| **False friend penamaan** (kasus `proposal`) | 🟢 Rendah | Kolom "potensi salah penamaan" di matriks pola. |

---

## 7. Rekomendasi

### Keputusan yang diminta ke manajemen
1. **Setujui Gauzy sebagai referensi arsitektur saja** — bukan basis kode, bukan fork. *(tidak berubah)*
2. **Tunjuk pemilik gate Legal AGPL** sebelum Phase 2.
3. **Putuskan pemilik domain PM & HRIS**: Java atau Go — hentikan duplikasi.
4. **Klarifikasi status HRIS**: lanjutkan pembangunan internal, atau beli — mengingat sudah ada
   investasi Recruitment 10 halaman + 8 entity.
5. **Putuskan scope KMS vs Document Management** sebelum development dimulai.

### Prioritas adopsi dari Gauzy (urut nilai)
1. **Time-tracking → billing loop** (Gauzy `time-log`/`timesheet`/`invoice-item`) — gap monetisasi.
2. **Model tenancy 2 level** (`tenant`→`organization`) — bila Master Tenant jadi kebutuhan.
3. **Pola MCP + AI provider abstraction** — bangun sekali untuk KMS *dan* agent harness.
4. **Model permission enum-based** — referensi refaktor RBAC.
5. **Equipment sharing** — basis Asset Management sederhana.

### Yang jangan diadopsi
- Domain Audit/Certification (nihil di Gauzy) · modul `proposal` (false friend) ·
  `organization-document` sebagai Document Management · `help-center` sebagai KMS ·
  tooling Nx/Lerna/dual-ORM/GraphQL · skema auth Gauzy.

---

## 8. Lampiran — instance referensi yang sudah siap

Gauzy berjalan lokal dan **sudah terisi data ber-konteks CBQA** (klien dari registry OneAlpha),
bisa dibuka berdampingan saat mendesain modul:

```
webapp   http://localhost:4200      admin@ever.co / admin
API      http://localhost:3000/api  Swagger: http://localhost:3000/swg
compose  ~/AI-Workspace/projects/sandbox/ever-gauzy/.deploy/local
seed     .deploy/local/seed/*.py
```

Laporan seeding + diagram relasi data antar modul Gauzy:
`agents/reports/gauzy-local-seed-and-onealpha-gap-2026-09-15.md`
