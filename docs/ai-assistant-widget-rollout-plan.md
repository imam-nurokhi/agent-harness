# AI Assistant widget — perkuat di accreditation, lalu terapkan ke academy & servicedesk

**Tanggal:** 2026-09-18 · **Host:** `31.97.67.241` (`dev-kemenkes`) · **Status:** rencana, belum dieksekusi
**Diminta oleh:** owner · **Sifat:** dokumen rencana (bukan catatan perubahan)

---

## 1. Ringkasan

Widget **AI Assistant** sudah hidup di `https://agents.nexoratech.co/accreditation/`. `/academy/` dan
`/servicedesk/` belum memilikinya sama sekali. Dokumen ini memetakan apa yang sebenarnya sudah
terpasang, apa kelemahannya, lalu menyusun jalur penerapannya ke dua aplikasi lain — dengan
prasyarat yang diminta owner: **self-knowledge accreditation diperkuat lebih dulu**, dan **setiap
jejak pemakaian reviewer harus tersimpan** sebagai bahan melengkapi requirement sebelum sprint
development dimulai.

---

## 2. Verifikasi keadaan sekarang

Diukur langsung, bukan diasumsikan (headless chromium, 1440×960, via Basic Auth prototipe):

| Path | HTTP | Ukuran | Widget |
|---|---|---|---|
| `/accreditation/` | 200 `text/html` | 365.425 B | **ada** |
| `/academy/` | 200 `text/html` | 620.088 B | tidak ada |
| `/servicedesk/` | 200 `text/html` | 401 B (+ `assets/index-pWIkaViZ.js`) | tidak ada |

Yang terkonfirmasi hidup di `/accreditation/`:

- FAB `✦ AI Assistant` (1 buah) + teaser bubble, tiga tab **Ask / Findings / Readiness**
- Header panel: `nexaccred · 1.0.0-pilot.1 · Executive Dashboard · Joan Marsh`
- `window.NexReadiness` → `{version: 0.1.0, PROJECT_ID: nexaccred, PROTOTYPE_VERSION: 1.0.0-pilot.1,
  createStore, answerQuestion, buildContext}`
- `window.RequirementReadiness` → `{init, setContext, open, ask, reset}`
- Pertanyaan uji "bagaimana readiness dihitung?" → dijawab, berlabel `ANSWERED_FROM_SOURCE`, dengan
  sitasi `📚 03-Data-Model-NexAccred.md · 01-PRD-NexAccred.md · runtime application state`
- **0 console error, 0 pageerror**
- `localStorage` sesudah dipakai: `nexreadiness:nexaccred:{events, session, messages}`

### 2.1 Tiga temuan yang mengubah bentuk pekerjaan

**a. Semua jejak reviewer hanya tersimpan di browser masing-masing.** Kunci
`nexreadiness:nexaccred:{session,messages,findings,events,signoff,checks}` di `localStorage`. Tidak
ada satu byte pun yang sampai ke owner kecuali reviewer menekan **Export JSON** dan mengirimkannya
sendiri. Permintaan owner — feedback tersimpan, tidak boleh hilang, dan reviewer sadar jejaknya
direkam — **belum terpenuhi sama sekali**.

**b. Knowledge engine-nya rapuh.** Matcher-nya `String.includes` berskor panjang-kata:

```js
for (const kw of rule.match) if (kw && q.includes(kw)) score += kw.length > 4 ? 2 : 1;
```

Commit terakhir `dcb8aee` ada justru karena pertanyaan "apa aturan blocking?" jatuh ke penolakan
palsu — patch-nya menambah keyword `blocking`, `blocked`, `aturan blocking`, `r1`…`r4`. Tapi keyword
pendek itu sendiri jadi jebakan substring: `'r1'` cocok di dalam "Q1", `'ai '` di dalam "email ",
`'kan '` di dalam "bagaimana ". Ambangnya efektif 1 — satu kecocokan apa pun sudah menjawab — dan
seri dimenangkan urutan array, sehingga `readiness-formula` sangat difavoritkan.

**c. Klon sumber di VPS ini basi, dan jalur build reproducible terputus.**

| | commit | widget |
|---|---|---|
| `/opt/nexora-prototypes/src/accreditation` (lokal) | `afbc668` 2026-09-17 | **tidak ada** |
| `origin/dev` (GitHub) | `dcb8aee` 2026-09-18 05:06 | ada |

Sumber widget ada di `origin/dev` lewat tiga commit owner hari ini:

```
dcb8aee 05:06  fix: knowledge keywords blocking/R1-R4 (hindari CLARIFICATION palsu)
fca7dcf 04:40  feat: AI assistant awareness system (mencolok FAB + teaser + badge)
2a76adc 04:34  feat: readiness AI assistant widget + full-stack local run
afbc668 (17/9) feat: initial NexAccred package v1.0     <-- klon lokal berhenti di sini
```

Build tercommit `dist-standalone/index.standalone.html` berukuran 318.254 B dan **tanpa widget**;
file yang tayang 365.425 B **dengan** widget, mtime 18 Sep 05:06 — sama dengan waktu commit
`dcb8aee`. Backup pra-widget ada di
`/var/backups/accreditation/accreditation-20260918-050429.tar.gz` (berisi build 318.254 B), dan
backup itu bukan produk `ops/prototypes/refresh.sh`. Kesimpulannya: file tayang **di-upload/di-build
manual**, `refresh.sh` belum pernah dijalankan sejak widget lahir.

Konsekuensi praktis: `ops/prototypes/refresh.sh accreditation` sekarang akan `git reset --hard` ke
`dcb8aee` lalu `build:standalone` — jadi menjalankannya **memulihkan** reproducibility, bukan
merusaknya. Tapi itu harus dibuktikan dengan perbandingan perilaku, bukan diasumsikan.

---

## 3. Anatomi widget yang ada (ref `dev` = `dcb8aee`)

Seluruh kode widget terkurung di satu direktori — `nexaccred-react/src/widget/`:

| File | Baris | Peran | Portabel? |
|---|---|---|---|
| `store.js` | 278 | Evidence store vanilla, gate math, sign-off | **Ya, generik** |
| `registry.js` | 16 | Registry handle multi-project | **Ya, generik** |
| `widget.css` | 71 | `.rr-fab`, `.rr-fab-badge`, `.rr-teaser` + 4 keyframes | **Ya, generik** |
| `store.smoke.mjs` | 61 | Smoke test store (belum masuk npm script) | **Ya, generik** |
| `index.js` | 65 | Export publik + dua global `window.*` | Ya, rename namespace |
| `ReadinessWidget.jsx` | 386 | Seluruh UI React; style **inline**, tanpa Tailwind | Shell generik, copy Indonesia |
| `contextAdapter.js` | 52 | `buildContext()` + 18 `SCREEN_LABELS` | **Tulis ulang per app** |
| `knowledge.js` | 394 | 26 intent NexAccred + matcher + penolakan | **Tulis ulang per app** |
| `WIDGET-README.md` | 53 | Dokumentasi + batasan yang diakui sendiri | — |

Ditambah build referensi yang di-vendor: `nexaccred_requirement_readiness_prototype/`
(`rr-widget.js` 19.541 B — IIFE bebas framework, tapi "AI"-nya hanya enam cabang `if/else`; berguna
sebagai **acuan bentuk API dan mount vanilla**, bukan sebagai bahan port).

### 3.1 Model data & semantik yang harus dipertahankan

**Persistensi.** `localStorage`, kunci `` `nexreadiness:${project}:${part}` `` — satu kunci per slice.
Ada mirror di memori sebagai sumber kebenaran ketika storage tidak tersedia (test Node, private
mode), `hydrate()` sekali, dan `cache` untuk `getSnapshot()` yang hanya di-invalidasi saat write.

**Gate.** Biner, tanpa nilai parsial:

```js
percent = Math.round(done / 9 * 100);
blockers = findings.filter(f => f.blocking && f.status === 'open').length;
ready    = percent === 100 && blockers === 0;
```

Sembilan area wajib (`CHECK_AREAS`): `roleAccess`, `readinessFormula`, `scope`, `nextAssessment`,
`criticalIssues`, `personnel`, `evidence`, `permissions`, `edgeStates`.

`severity ∈ {blocker,major,minor,info}` hanya metadata; **`blocking: boolean`** yang dihitung gate —
dua flag berbeda. Menerima/menolak finding membersihkan gate tanpa menghapus buktinya.

**Sign-off.** `signOff()` **menolak** (`{ok:false, reason:'coverage N%, M open blocker(s)'}`), bukan
memperingatkan, selama gate belum lolos. Terikat satu `PROTOTYPE_VERSION`. Transisi status finding
`open → accepted|rejected|superseded` **hanya oleh manusia** — AI boleh menyarankan, tidak boleh
menulis.

**Pasca-baseline.** Begitu sign-off `APPROVED`/`APPROVED_WITH_EXCEPTIONS`, finding baru otomatis
`CHANGE_REQUEST` — bukan perubahan scope yang diam-diam.

**Audit.** `events[]` append-only: `session.started`, `route.viewed`, `question.asked`,
`answer.given`, `finding.recorded`, `reviewarea.checked`, `finding.decided`, `baseline.signoff`,
`session.reset`.

**Konteks.** Widget sepenuhnya pasif — tidak pernah membaca router/URL/auth. Host membangun ulang
objek `context` setiap render dan menyerahkannya sebagai satu prop. Aturan privasinya tertulis di
kode: **ringkasan konfigurasi saja, tidak pernah seluruh dataset domain**.

### 3.2 Pelajaran mahal yang harus ikut terbawa

Empat hal ini sudah dibayar sekali; jangan ditemukan ulang:

1. `getSnapshot()` **wajib** mengembalikan objek ter-cache. Objek baru tiap panggilan =
   `useSyncExternalStore` infinite loop = **halaman putih** (`store.js:66-68`).
2. Glow FAB **box-shadow saja**. `transform` infinite merusak hit-testing tombol; karena itu animasi
   float hanya berjalan 3× saat load (`fca7dcf`).
3. `PROTOTYPE_VERSION` harus dinaikkan setiap prototipe berubah, supaya finding lama tidak tertukar
   dengan versi baru.
4. `QUICK_PROMPTS` memilih ikonnya lewat `q.startsWith('Apa saja')` — ubah kalimat prompt, ikonnya
   diam-diam salah.

### 3.3 Cacat yang harus diperbaiki, bukan ikut diport

- **`docs/widget-readiness-ai-assistant.md` tidak ada di mana pun** — tidak di repo, tidak di
  riwayat git, tidak di filesystem host ini, tidak di `~/AI-Workspace/docs/`. Padahal `SOURCES.WIDGET`
  menampilkannya sebagai **sitasi kepada reviewer**, dan tiga intent (`gate`, `evidence-model`,
  `pilot`) mengutipnya. Reviewer diberi rujukan ke dokumen yang tidak bisa dibuka siapa pun.
- `SOURCES` tidak pernah bisa mengutip `00-README-Document-Index.md` dan `02-ERD-NexAccred.mermaid`.
- `RequirementReadiness.init()` dan `setContext()` **no-op**. Host vanilla yang ditulis terhadap
  `rr-widget.js` referensi (di mana `init(cfg)` yang me-mount) akan diam-diam tidak melakukan apa pun.
- `UNRESOLVED_QUESTION` tidak pernah di-assign jalur kode mana pun — hanya muncul di dalam teks
  penolakan.
- `widgetHandle()` jatuh ke `Object.values(handles)[0]`: dengan dua widget ter-mount, project key
  tak dikenal diam-diam mengendalikan widget yang mendaftar pertama. Handle juga tidak pernah
  di-unregister saat unmount.
- Import mati: `CLASSIFICATIONS` di `ReadinessWidget.jsx:16`.
- **Tidak ada satu pun tes UI widget.** `data-testid="readiness-widget"` ada di bundle tapi tidak
  pernah di-assert. Satu-satunya tes adalah `store.smoke.mjs`, dan itu belum terpasang di npm script.

---

## 4. Self-knowledge accreditation: apa yang tersedia untuk diperkuat

Inilah jawaban atas permintaan "analisa mendalam ke code, temukan alur kerja, ada menu apa saja".

### 4.1 Paket dokumen (sumber kebenaran, sudah lengkap)

| File | Ukuran | Fakta otoritatif |
|---|---|---|
| `00-README-Document-Index.md` | 4,6 KB | **5 pertanyaan** produk, tabel P1–P7, **7 baris batasan prototipe** |
| `01-PRD-NexAccred.md` | 16,9 KB | **FR-1…FR-12**, P1–P7, rantai akreditasi, persona, NFR |
| `02-ERD-NexAccred.mermaid` | 7,9 KB | 30 entitas, 33 relasi |
| `03-Data-Model-NexAccred.md` | 15,8 KB | **R1–R4** (bentuk bernomor kanonik), band, bobot, matriks izin |
| `04-Business-Process-NexAccred.md` | 12,3 KB | **BP-1…BP-8**, owner, trigger, batas sistem |
| `05-RBAC-Separation-of-Duties.md` | 7,6 KB | matriks **11 peran × 6 domain**, dua batas kritis |

Rantai akreditasi (PRD §2), layak dikutip verbatim:

```
Requirement → Scheme → Process → Personnel → Competence → Document →
Evidence → Implementation → Assessment → Finding → CAPA → Risk → Readiness
```

**FR-10 adalah kontrak yang mengatur AI mana pun di aplikasi ini:** beroperasi di atas compliance
graph (bukan chatbot generik); setiap jawaban mengutip requirement/dokumen/evidence; **AI dilarang
memutuskan compliance formal** — advisory berlabel jelas; konten AI ditandai aksen violet.

**R1–R4** (Data Model §3 Step 2) — aturan blocking hanya bisa **menurunkan** band:

| Rule | Kondisi | Cap |
|---|---|---|
| R1 | 1 critical gap belum selesai | Ready with Risks |
| R2 | ≥2 critical gap belum selesai | Not Yet Ready |
| R3 | Pilar Competence < 60% | Not Yet Ready |
| R4 | Witness outstanding **dan** <30 hari ke visit | Not Yet Ready |

Band: 🟢 Ready ≥90 · 🟡 Ready with Risks 75–89 · 🟠 Not Yet Ready 60–74 · 🔴 Not Ready <60.
Bobot 8 pilar: Requirements 20, Evidence 15, Personnel 10, Competence 15, Operations 10,
Documentation 10, Assurance 10, CAPA 10.

### 4.2 Menu: 41 item dalam 8 grup

Sumber tunggal `nexaccred-react/src/data/roles.js` (155 baris) — `ROLES`, `ROLE_NAME_TO_ID`, `NAV`,
`PARENT_NAV`, `HIDDEN_NAV_KEYS`.

| Grup | Item |
|---|---|
| *(tanpa grup)* | `dashboard`, `tasks` |
| Accreditation | `accreditation-profile`, `accreditation-scope`, `standards`, `schemes`, `requirements`, `compliance` |
| Operation | `certification-activities`, `personnel-competence`, `clients`, `audits`, `technical-review`, `certification-decisions` — 5 di antaranya ber-flag **`synced`** (dari Platform Audit) |
| Document & Evidence | `document-library`, `evidence-repository`, `forms-templates`, `records` |
| Assurance | `internal-assessment`, `ab-assessment`, `findings`, `capa`, `risk`, `impartiality` |
| Intelligence | `ai-assistant`, `gap-analysis`, `assessment-simulator`, `impact-analysis` (4 ber-flag **`ai`**), `readiness` |
| Reporting | `compliance-report`, `assessment-pack`, `management-report`, `analytics` |
| Administration | `users`, `roles`, `organization`, `workflow`, `notifications`, `configuration`, `integrations`, `audit-trail` |

`PARENT_NAV` memetakan 15 sub-route ke induknya. `HIDDEN_NAV_KEYS = ['ai-assistant']` —
menu AI lama **disembunyikan** karena digantikan widget, tapi route-nya tetap terdaftar.

Route→screen ada di `src/screenRegistry.jsx` (374 baris): 33 `case` eksplisit + `tableConfigs(ctx)`
dengan 21 kunci yang semuanya dirender satu `TableScreen`. Navigasi adalah state machine
`navigate(route, param)`, **tanpa URL router**.

**Keterjangkauan per persona** (dari `ROLES`; `head` memakai `all: true`):

| Persona | id | Jumlah route |
|---|---|---|
| Head of Accreditation | `head` | **41** (semua) |
| Accreditation Staff | `staff` | 24 |
| Internal Auditor | `auditor` | 14 |
| Impartiality Committee | `impartiality` | 11 |
| Document Controller | `doccontrol` | 9 |
| System Administrator | `admin` | 8 (nol route bisnis, by design) |

Enam persona demo: Joan Marsh (head) · Maria Santos (auditor) · K. Devi (impartiality) ·
Rahayu Ningsih (staff) · Helda Mutiara (doccontrol) · R. Alvi (admin). Password demo seragam
`NexAccred123!`.

### 4.3 Alur kerja: BP-1 … BP-8

| BP | Judul | Owner |
|---|---|---|
| BP-1 | Onboarding scheme akreditasi baru (**tanpa keterlibatan developer**) | Head |
| BP-2 | Continuous readiness monitoring (dihitung ulang setiap page load) | Head; semua peran memasok |
| BP-3 | Persiapan assessment AB (notifikasi 45/30/14/7 hari) | Head |
| BP-4 | Finding → CAPA → Closure | Owner finding; Head menyetujui |
| BP-5 | Witness audit cycle | Head |
| BP-6 | Requirement change management | Head |
| BP-7 | Document control (`REQUIRED_DOCUMENT_TYPE` vs `DOCUMENT`) | Document Controller |
| BP-8 | Role-based daily operation | Semua peran |

Batas sistem, verbatim: *"NexAccred never duplicates or writes to Platform Audit or AIHCM."*

### 4.4 Yang sudah ada sebagai "bantuan", dan bisa dipanen

Tidak ada onboarding, tour, atau tooltip system sama sekali. Yang ada justru lebih baik: **teks
penjelas yang sudah ditulis untuk user** — ~35 kalimat `sub=` di setiap `PageHead`, komponen `Note`,
`IntegrationBanner` (penjelas provenance Platform Audit), `FormField hint=`, layar
**Readiness Methodology** (dokumentasi-diri aplikasi: bobot bisa diedit langsung, tabel rule mana
yang sedang memicu scheme mana, audit raw-vs-final), dan judul kartu dashboard yang persis memetakan
ke pertanyaan README ("Why aren't we ready?", "What should we fix first?").

### 4.5 Dua route mati dan satu drift

- `assessment-prep` — dipanggil dari `screens/Accreditation.jsx:91` dan `screens/Dashboards.jsx:155`,
  ada di `PARENT_NAV`, **tidak ada `case`** di `screenRegistry.jsx` → "not implemented".
- `ab-register` — komponen `AbRegister` **ada** dan sudah di-import di `screenRegistry.jsx:13`,
  hanya kurang satu baris `case`.
- Drift doc-vs-kode: RBAC §4 menulis Staff 25 / Impartiality 5; kode memberi 24 / 11. Asisten harus
  mengutip salah satu — mana yang benar adalah keputusan owner.

---

## 5. Dua aplikasi target

### 5.1 Academy (DeAcademy) — paling sulit, dan satu-satunya dengan jebakan tes

`lsp-unified-app.html`, 620.088 B, **179 baris**, hasil **esbuild minify tanpa sourcemap**. React 18 +
lucide + Tailwind semuanya inline.

Layout internal: `<div id="root">` di baris 12 · `<script>` dibuka baris 13 · IIFE dibuka baris 14 ·
baris 21 = **412.516 karakter** bundle · baris 22–40 kode tambahan yang masih readable · mount +
IIFE ditutup di akhir baris 40 · baris 41–176 blok lisensi lucide · `</script></body></html>`
baris 177–179.

**Penghalangnya:** tidak ada yang di-export. `grep 'window.React'` → **0 hit**; `globalThis.*` → **0
hit**. React, ReactDOM, lucide, dan seluruh komponen (`Gd`, `pe`, `qp`, `Fh`, `Rh`…) adalah lokal di
dalam `(()=>{ … })()`. Widget **tidak bisa** memakai React app ini, tidak bisa membaca state-nya,
tidak bisa memanggil `setTab`/`goTo`.

Konsekuensinya:

- Titik suntik: `<script>` **baru** antara baris 177 dan 178 — murni append, tidak menyentuh baris 21.
- Harus **vanilla JS**, dan harus **inline** (bukan `<script src>`) agar alur `file://` double-click
  yang dipimpin `AGENTS.md` tetap jalan.
- Render ke **shadow root** sendiri — reset Tailwind bundle (`*,:after,:before{...}`) akan bocor.
- Konteks dibaca dari DOM, memakai kontrak yang sudah terbukti di `tests/helpers.py`: route aktif =
  tombol ber-class aktif di `aside nav button`; menu = teks semua `aside nav button`; user+role =
  teks tombol akun; belum login = `aside nav button` kosong.
- Navigasi = sintesis `.click()` pada `aside nav button` — persis yang dilakukan `helpers.py::goto`,
  jadi ini jalur yang didukung.

⚠️ **Blast radius tes: 92 tes Playwright.** `test_roles.py::test_every_view_renders` menuntut
`nav_items()` **persis sama** dengan daftar persona, dan fixture `assert_healthy` gagal pada **satu
saja** console error. Maka: widget **tidak boleh** menambah entri nav, dan **tidak boleh** memancarkan
`console.error` — termasuk saat POST ke collector gagal.

7 persona: Dinda Pramesti (participant) · Ratna Wijayanti (corporate_admin) · Nadia Iskandar
(operator, 13 menu) · Kevin Wijaya (verifier) · Hendra Wijaya (tutor_examiner) · Arya Wicaksono
(admin) · Surya Dharmawan (management). Plus guest landing pra-login dan entri nav "upsell" terkunci
yang di-inject dinamis.

Korpus grounding-nya **kaya dan eksternal** (~170 KB `docs/`): `PRD.md` (51 KB), `DATA-MODEL.md`
(50 KB, 35 entitas), `API-ENDPOINTS.md`, `ROLES-PERMISSIONS-MATRIX.md` (matriks + **16 Prinsip
Kunci**), `PROCESS-FLOWS.md` (16 alur), `erd.mermaid`, `positions.json` (147 posisi).

Prinsip yang tidak boleh dilanggar asisten: isolasi multi-tenant (Operator melihat *metadata* internal
training, tidak isinya) · data kompetensi digerbangi consent · Tutor ≠ Examiner · ganti workspace
**mengubah konteks, tidak menambah hak** · Super Admin ≠ Operator · **Management 100% read-only,
tanpa pengecualian** · dua gerbang pembayaran **terpisah** dan tidak boleh digabung validasinya.

Dan satu hal yang harus dihormati: "Analisa" di Management dan "Recommended for You" **sengaja bukan
AI** (PRD §4.17/§5), sementara AI proctoring masuk out-of-scope (§7). Asisten memposisikan diri
sebagai panduan di atas model terdokumentasi, bukan pengganti keduanya.

### 5.2 Service desk (NexServe) — paling mudah, dan sudah punya "AI" yang harus diselaraskan

React 18 + Vite sungguhan. `src/ServiceDesk.jsx` 3.301 baris, **nol tes**, **nol provider** (tanpa
Context/Redux/router/theme). Seluruh state adalah 14 `useState` di dalam satu `App()` (baris 3103).

Tiga opsi mount, dengan rekomendasi jelas:

1. **Satu baris di samping `<Toast message={toast} />` (baris 3299) — direkomendasikan.** Widget
   langsung dapat `view, persona, agentIdentityName, requests, services, memberships, slaPolicy,
   bookings` dan aksi `goTo(view, {serviceId, prefill})` / `switchPersona(p)`. `Toast` sudah jadi
   preseden overlay `fixed bottom-6 right-6 z-50`.
2. Wrapper di `src/App.jsx` (4 baris) — diff nol ke prototipe, tapi widget tidak dapat state apa pun.
3. Screen ter-registrasi nav — paling mirip pola accreditation; `Sparkles` sudah ter-import.

19 view key, 4 persona (5 kartu login): employee · manager · agent (single-team & multi-team) · admin.
Model otorisasi agent-nya **data-driven, bukan flag peran**: `TEAMS` (9) → `TEAM_MEMBERSHIPS_SEED`
(9, ber-tanggal) → `isMembershipActive()` → `getAuthorizedTeams()`. Membership IT milik Dewi
**sengaja kedaluwarsa** untuk membuktikan akses lewat itu *dikecualikan*, bukan sekadar disembunyikan.

Lifecycle tiket: `standard` = Submitted → Pending Approval → Approved → Assigned → In Progress →
Resolved → Closed; `noApproval` memotong dua langkah persetujuan. Hanya requester yang boleh
menutup.

**Tiga permukaan AI simulasi yang sudah ada** — diselaraskan, bukan diduplikasi:

- `parseAIQuery(rawText, services)` (baris 845) — intake bahasa alami, 5 cabang aturan + fallback
  keyword, mengembalikan `{view, serviceId, summary, prefill}`. **Ini kontrak integrasi paling
  bernilai di kedua aplikasi**: input sama, output sama, handoff `goTo` sama.
- "AI Assist" per tiket untuk agent (sekitar baris 1830) — Summarize Request + Suggest Resolution,
  7 playbook hardcoded.
- `KnowledgePage` (baris 3053) — 4 artikel, subtitle *"Search approved articles before opening a
  request."* Korpus sitasi alami, mencerminkan `sources[]` accreditation.

Kosakata desain yang sudah ada dan harus dipakai: `Sparkles` + `text-indigo-600`,
`Loader2 animate-spin` + "Thinking…", kartu `bg-indigo-50 border-indigo-100`, chip pill
`bg-indigo-50 text-indigo-700`, latensi palsu 550 ms.

Dokumentasinya **hanya `AGENTS.md` 1.556 B** — tanpa PRD, data model, ERD, business process, atau
RBAC doc. Di sini **kode adalah dokumentasinya**, dan komentarnya memang substantif (komentar
10 baris soal kejujuran analytics, komentar otorisasi tim, rasionalisasi `ComboCreate`). Kebalikan
persis dari academy.

⚠️ `dist/` dibangun dengan `--base=/servicedesk/` dari flag CLI yang **tidak tercommit di mana pun**,
sementara `vite.config.js` tidak punya `base`. Widget **tidak boleh** memakai URL aset/API absolut.
Worktree juga kotor: `index.html` termodifikasi (CDN Tailwind → `/tailwind.js`), `public/` untracked.
`React.StrictMode` aktif → efek dobel di dev, jadi setiap efek yang mengirim request harus idempoten.

### 5.3 Perbandingan biaya port

| | academy | service-desk |
|---|---|---|
| Sumber app yang bisa diedit | **Tidak** (bundle minified) | **Ya** (3 file modul) |
| React terjangkau widget | **Tidak** (IIFE tertutup) | **Ya** |
| Akses state app | DOM-scraping saja | Langsung, 14 `useState` + `goTo` |
| Korpus grounding | **Kaya & eksternal** (~170 KB docs) | **Kode saja** (+ `AGENTS.md` 1,5 KB) |
| AI yang sudah ada | Tidak ada | `parseAIQuery` + AI Assist + Knowledge |
| Blast radius tes | **Tinggi** (92 tes) | **Nol** |

Karena itu urutannya: **service desk dulu, academy kemudian.**

---

## 6. Prasyarat operasional

- CSP ketiga path: `default-src 'self'` → `connect-src` mewarisi `'self'`. **POST same-origin ke
  collector sudah diizinkan; CSP tidak perlu disentuh.** (`ops/nginx/README.md` mencatat CSP sudah
  tiga kali dituduh salah — jangan longgarkan apa pun di sini.)
- Butuh **satu** `location ^~ /widget-feedback/` baru di vhost, memakai `.prototypes.htpasswd` yang
  sama. Prosedur wajib: edit `ops/nginx/agents.nexoratech.co.conf` → `validate_vhost.py` →
  `ops/nginx/tests` → copy ke `/etc/nginx/sites-available/` → `nginx -t` → `systemctl reload nginx`.
  **Jangan pernah restart.**
- `add_header` **mengganti**, bukan menambah: blok baru harus menyebut ulang keenam header.
- Aset yang absen harus `404`, bukan jatuh ke shell SPA sebagai `200 text/html` — nested regex
  location + probe permanen di `verify.sh` sudah menangani ini; jangan dilemahkan.
- Push hanya ke `dev`/`staging`, **tidak pernah** `main/master/production/prod` (`AGENTS.md` ketiga repo).

---

## 7. Keputusan owner yang mengikat rencana ini

| Topik | Keputusan |
|---|---|
| Penyimpanan feedback | Collector service di VPS ini; **tidak boleh hilang**; reviewer **aware** jejaknya direkam |
| Identitas reviewer | **Wajib** isi nama + email sekali, sebelum widget bisa dipakai |
| Kedalaman KB academy/servicedesk | **Auto-generate dari kode dulu**, isi manual menyusul |
| Interaktivitas tahap 1 | Navigasi + tur berpandu · Saran kontekstual per layar · Checklist gate yang memandu |

---

## 8. Rencana pelaksanaan

### Fase 0 — Pulihkan jalur build (prasyarat semua fase lain)

1. `ops/prototypes/refresh.sh accreditation` — menarik `dev` ke `dcb8aee` lalu `build:standalone`.
2. Bandingkan hasil build dengan file yang tayang sekarang. Kalau perilakunya sama (FAB, 3 tab,
   26 intent, 0 console error, `window.NexReadiness.version === '0.1.0'`), jalur reproducible pulih.
3. `ops/prototypes/verify.sh` harus hijau.
4. Tulis `docs/widget-readiness-ai-assistant.md` yang hilang (§3.3). Ini bukan kerapian — tiga intent
   mengutipnya sebagai sumber kepada reviewer. Direkonstruksi dari `WIDGET-README.md` + kode.

### Fase 1 — Feedback collector: "tersimpan, tidak boleh hilang, reviewer aware"

**Sisi server** — service baru, **bukan** tempelan di Command Center. `bin/lib/dash.py` adalah
control-plane yang menjalankan proses (`jobs.spawn`); ingest dari browser tidak boleh menempel di sana.

- `ops/feedback/collector.py` — Python stdlib, `ThreadingHTTPServer` di `127.0.0.1:7788`. Hanya
  `POST /collect` (+ `GET /healthz`). Tanpa eksekusi apa pun, tanpa dependensi.
- Durabilitas: append-only NDJSON `/var/lib/nexora-feedback/<app>/<YYYY-MM-DD>.ndjson`, `flush()` +
  `os.fsync()` per baris, rotasi harian, `0640 ahagent:ahagent`. Batas ukuran body, batas rate per IP,
  tolak field tak dikenal. Setiap baris menyimpan juga `remote_user` Basic Auth dan `received_at`
  server — stempel waktu dari klien tidak dipercaya.
- Unit `ahagent`: `ops/feedback/ah-feedback.service`, mengikuti pola `ah-dashboard.service`
  (`EnvironmentFile`, `NoNewPrivileges`, `ProtectSystem=full`, `PrivateTmp`).
- nginx: `location ^~ /widget-feedback/ { proxy_pass http://127.0.0.1:7788/; }` + Basic Auth
  prototipe + keenam header dinyatakan ulang, lewat prosedur §6.
- Backup: masukkan `/var/lib/nexora-feedback/` ke jadwal backup yang ada — itulah yang membuat
  "tidak boleh hilang" berlaku juga terhadap kehilangan disk, bukan hanya kehilangan browser.

**Sisi widget** — `widget/core/collector.js`, disisipkan pada **satu** corong `write()` +
`appendEvent()` di `store.js`. Jangan tebar `fetch` ke seluruh UI.

- Antrean tahan-gagal: event masuk buffer `localStorage` (`nexreadiness:<project>:outbox`), dikirim
  batch tiap ~5 detik dan pada `visibilitychange`/`pagehide` lewat `navigator.sendBeacon`. Baris yang
  gagal **tetap** di outbox dan dicoba lagi — collector mati tidak menghilangkan satu pun jejak.
- Idempoten: tiap event bawa `eventId` + `sessionId`; server menolak duplikat.
- **Tidak boleh `console.error`** apa pun (syarat 92 tes academy) — kegagalan dicatat diam-diam ke
  state widget.
- `localStorage` tetap dipertahankan sebagai buffer, tidak diganti.

**Identitas + transparansi** — `widget/core/identity.js`.

- Saat widget pertama dibuka: form **wajib** Nama + Email (validasi bentuk), disimpan di
  `nexreadiness:<project>:identity` + `deviceId` acak. Widget tidak menjawab sebelum diisi.
- Identitas ini **terpisah** dari persona demo. Keduanya distempel ke setiap event: `reviewer`
  (manusia nyata) dan `persona` (peran yang sedang dicoba).
- **Notice transparansi yang selalu terlihat**, bukan sekali lalu hilang: baris tetap di footer panel
  ("Pertanyaan, finding, dan layar yang Anda buka direkam untuk perbaikan requirement") plus tab
  **"Jejak saya"** yang menampilkan apa saja yang sudah terkirim untuk reviewer itu. Ini yang
  memenuhi "user aware dengan jejak reviewer yg dilakukan".

**Sisi baca untuk owner**

- `bin/ah feedback` — ringkasan per app, per reviewer: jumlah pertanyaan, pertanyaan yang jatuh ke
  `CLARIFICATION_NEEDED` (**inilah daftar lubang KB**), finding terbuka, status gate.
- Digest Telegram mingguan lewat pola `bin/sprint_reminder.py` yang sudah ada.

### Fase 2 — Perkuat self-knowledge accreditation (sebelum port, sesuai permintaan owner)

**2a. Ganti matcher.** Normalisasi + tokenisasi; cocokkan **frasa** dan **token utuh** (menghapus
jebakan `'r1'`/`'ai '`/`'kan '`); skor idf-ringan; ambang minimum; dan kembalikan **top-3 kandidat**
sebagai "Maksud Anda…?" alih-alih langsung menolak. Antarmuka
`answerQuestion(question, ctx) → {answer, sources, classification}` **tidak berubah**.

**2b. KB turunan-kode (sesuai pilihan owner).** Script `nexaccred-react/scripts/gen-knowledge.mjs`
membaca sumber kebenaran yang sudah ada dan memancarkan `knowledge.generated.js`:

| Sumber | Yang dihasilkan |
|---|---|
| `src/data/roles.js` (`NAV` 41/8 grup, `PARENT_NAV` 15, `ROLES.routes[]`) | "menu apa saja", "saya boleh ke mana sebagai X", peta grup→item |
| `src/screenRegistry.jsx` (33 case + 21 `tableConfigs`) | "di layar ini saya melakukan apa", real vs stub |
| `sub=` tiap `PageHead` (~35 kalimat) | deskripsi satu-kalimat per layar, sudah ditulis untuk user — pakai verbatim |
| `src/lib/readiness.js` | bobot 8 pilar, 3 ambang, 4 band, R1–R4 + string alasan persisnya |
| `src/data/schemes.js`, `records.js` | keadaan demo saat ini (ISO 27701 tertahan 2 critical + Competence 52; ISO 27001 witness 2/3) |

KB manual (26 intent) **menang** atas yang generated; generated mengisi celah navigasi/peran/layar
yang selama ini kosong. Tambahkan `00-README` dan `02-ERD` ke `SOURCES`.

**2c. Perbaiki dua route mati** (§4.5) sebelum asisten diizinkan menyarankan navigasi ke sana.

**2d. Putuskan drift doc-vs-kode** RBAC §4 (Staff 25 vs 24, Impartiality 5 vs 11) — asisten harus
mengutip satu angka, dan itu keputusan owner.

### Fase 3 — Generalisasi widget jadi satu inti bersama

Pecah jadi inti bersama + konfigurasi per aplikasi, supaya semantik gate **tidak bisa** menyimpang
antar aplikasi:

```
widget/core/        store.js  collector.js  identity.js  engine.js  registry.js
                    widget.css  ReadinessWidget.jsx (shell React)
                    rr-vanilla.js (shell DOM, khusus academy)
widget/app.config.js   PROJECT_ID, PROTOTYPE_VERSION, STORAGE_PREFIX,
                       CHECK_AREAS, QUICK_PROMPTS, SOURCES, UI copy
widget/knowledge.js    per aplikasi (manual + generated)
widget/context.js      per aplikasi (buildContext + SCREEN_LABELS)
```

Sumber kanonik: repo `accreditation`. `ops/prototypes/sync-widget.sh` menyalin `widget/core/` ke dua
repo lain saat refresh; `app.config.js` / `knowledge.js` / `context.js` dimiliki masing-masing repo.

Shell React melayani **accreditation + service desk**; shell vanilla hanya untuk academy. Inti
dibagi bersama supaya gate/sign-off/audit tidak pernah bercabang.

Ikut dibereskan saat generalisasi: `QUICK_PROMPTS` jadi `{label, question}`; `PROTOTYPE_VERSION` masuk
config (bukan import langsung oleh store & tiga tab); copy UI keluar dari JSX; import mati
`CLASSIFICATIONS` dihapus; `widgetHandle()` tidak lagi fallback ke handle pertama; handle
di-unregister saat unmount; `init`/`setContext` diberi implementasi nyata untuk host vanilla.

### Fase 4 — Port ke service desk (dulu: paling murah, blast radius nol)

1. Mount `<ReadinessWidget project="nexserve" context={…}/>` di samping `<Toast/>` (baris 3299).
2. `context.js`: `SCREEN_LABELS` dari `PAGE_TITLES` (baris 1251, 18 entri) + `login`; reviewer dari
   persona aktif + `agentIdentityName`.
3. `knowledge.generated.js` dari `NAV_ITEMS_BY_PERSONA` (1145), `REQUEST_LIFECYCLE` (768),
   `TEAMS`/`TEAM_MEMBERSHIPS_SEED`/`isMembershipActive` (44–95), `SLA_POLICY_DEFAULTS`,
   `STATUS_STYLES` (32 badge = kosakata status kanonik), `TEMPLATE_LIBRARY` (526), `KNOWLEDGE`
   (4 artikel, korpus sitasi).
4. `CHECK_AREAS` **ditulis ulang** untuk domain service desk (lifecycle, SLA, otorisasi tim, intake
   NL, coverage gap, edge state) — jangan pakai 9 area accreditation.
5. Selaraskan dengan AI yang sudah ada: `parseAIQuery` dipertahankan sebagai jalur intake; widget
   memakai kontrak kembalian yang sama `{view, serviceId, summary, prefill}` untuk navigasinya.
6. Perbaiki `AGENTS.md`: peta view-nya tidak lengkap (12 dari 19), dan base `/servicedesk/` datang
   dari flag CLI yang belum tercommit.

### Fase 5 — Port ke academy (vanilla, paling hati-hati)

1. Shell `rr-vanilla.js` + `widget/core/*` dibundel jadi **satu blok `<script>` inline**, disuntik
   `ops/prototypes/refresh.sh` di antara baris 177 dan 178 saat publish. Bundle sumber **tidak
   pernah** di-refactor (aturan keras `AGENTS.md`).
2. Render ke **shadow root** sendiri di `document.body`.
3. Konteks dari DOM; navigasi dengan sintesis `.click()` pada `aside nav button`.
4. **Tanpa entri nav, tanpa satu pun `console.error`.** `./run-tests.sh` (92 tes) dijalankan sebelum
   dan sesudah; keduanya harus **92 hijau**.
5. `knowledge.generated.js` dari `docs/` (§5.1) + peta nav `qp`, label peran `pe`, alert per peran
   `kv` dari bundle.
6. 16 Prinsip Kunci ditanam sebagai batasan yang tidak boleh dilanggar asisten — terutama
   **Management 100% read-only** dan dua gerbang pembayaran yang terpisah.

### Fase 6 — Interaktivitas (tiga yang dipilih owner)

Dibangun di inti bersama, jadi berlaku di tiga aplikasi sekaligus:

- **Navigasi + tur berpandu.** Jawaban boleh membawa `{action:'navigate', route}`; widget
  mengeksekusinya lewat adapter per app (`onNavigate` React / `goTo` service desk / sintesis klik
  academy). Tur berurutan per persona yang menyusuri `CHECK_AREAS`: satu area → layar yang tepat →
  apa yang diuji → centang → lanjut.
- **Saran kontekstual per layar.** Pada `route.viewed`, widget menawarkan 3 pertanyaan/pemeriksaan
  relevan untuk layar itu, dari peta route→saran yang **digenerate** bersama KB (Fase 2b/4/5) — jadi
  tidak ada daftar manual yang ikut basi setiap layar berubah.
- **Checklist gate yang memandu.** Tab Readiness berhenti pasif: menampilkan area yang belum
  tercentang, kriteria lulusnya, tombol langsung ke layarnya, dan alasan persis kenapa sign-off
  ditolak (`coverage N%, M open blocker(s)`).

---

## 9. File yang akan disentuh

**Baru — AI-Workspace**
`ops/feedback/collector.py` · `ops/feedback/ah-feedback.service` · `ops/feedback/README.md` ·
`ops/feedback/tests/` · `ops/prototypes/sync-widget.sh` · `docs/widget-readiness-ai-assistant.md` ·
`agents/reports/2026-09-18-ai-assistant-widget-rollout.md`

**Diubah — AI-Workspace**
`ops/nginx/agents.nexoratech.co.conf` (satu blok `location ^~ /widget-feedback/`) ·
`ops/nginx/tests/` (assert blok baru + keenam header) · `ops/prototypes/refresh.sh` (sync widget +
suntik academy) · `ops/prototypes/verify.sh` (probe collector) · `bin/ah` + helper `feedback` ·
`CLAUDE.md` (bagian baru: widget + collector)

**Repo accreditation** (sumber kanonik widget)
`nexaccred-react/src/widget/core/*` · `widget/app.config.js` · `widget/knowledge.js` +
`knowledge.generated.js` · `widget/context.js` · `scripts/gen-knowledge.mjs` · `screenRegistry.jsx`
(2 route mati) · `package.json` (script `test:widget`, `gen:knowledge`)

**Repo service-desk**
`src/widget/*` (config/knowledge/context) · `src/ServiceDesk.jsx` (satu baris mount di 3299) ·
`AGENTS.md`

**Repo academy**
`widget/*` (sumber vanilla + KB) · `lsp-unified-app.html` **hanya** lewat penyuntikan `refresh.sh`
saat publish — file bundle tidak di-refactor

---

## 10. Verifikasi

**Per fase, sebelum lanjut:**

- **Fase 0** — `refresh.sh accreditation` sukses; `verify.sh` hijau; headless chromium di
  `/accreditation/`: FAB ada, 3 tab ada, `window.NexReadiness.version === '0.1.0'`, 0 console error —
  sama seperti baseline yang sudah diukur 2026-09-18.
- **Fase 1** — `node src/widget/store.smoke.mjs` exit 0. Unit test collector (append-only, fsync,
  tolak duplikat `eventId`, tolak body besar, rotasi harian). End-to-end: buka widget → isi
  identitas → ajukan pertanyaan → catat finding → baris baru muncul di
  `/var/lib/nexora-feedback/accreditation/<tanggal>.ndjson` dengan nama+email, persona, route,
  klasifikasi. **Uji hilang-koneksi:** stop `ah-feedback`, ajukan 3 pertanyaan, start lagi —
  ketiganya harus menyusul terkirim dari outbox, nol hilang. `nginx -t` + reload, lalu `verify.sh` +
  `ops/nginx/tests` hijau, dan Command Center / n8n / `academy-test` tetap seperti semula.
- **Fase 2** — set regresi pertanyaan (≥40, ID+EN, termasuk yang memicu `dcb8aee`) dijalankan
  terhadap matcher lama dan baru; syarat lulus: **nol `CLARIFICATION_NEEDED` palsu**, nol salah-cocok
  `'r1'`/`'ai '`. `npm run test:e2e` (`roles.spec.js`, `readiness-visibility.spec.js`) tetap hijau.
- **Fase 4** — `npm run build` service desk; muat `dist/` di bawah `/servicedesk/`; ke-19 view dibuka
  tanpa console error; widget dapat konteks benar per persona; `goTo` dari jawaban berfungsi.
- **Fase 5** — `./run-tests.sh` academy: **92 hijau sebelum dan sesudah**. `file://` double-click
  tetap jalan. Zero console error (dijaga fixture `console_errors`).
- **Fase 6** — skrip Playwright yang menjalankan satu tur penuh di tiap aplikasi: buka widget →
  identitas → tur memandu ke setiap `CHECK_AREAS` → centang semua → sign-off diterima; dan jalur
  negatif: satu finding `blocking` terbuka → sign-off **ditolak** dengan alasan persis.

**Gerbang akhir:** `python3 -m unittest discover -s tests` (291), `ops/harness/tests` (11),
`ops/nginx/tests` (14+), `ops/n8n/tests` (10) — semua hijau. Lalu tulis
`agents/reports/2026-09-18-ai-assistant-widget-rollout.md` dengan perintah, pengukuran, dan rollback
per perubahan — **tidak ada git untuk workspace ini**, jadi laporan itulah satu-satunya catatan.

---

## 11. Rollback

Collector: `systemctl --user stop ah-feedback`, hapus blok `location` dari
`ops/nginx/agents.nexoratech.co.conf`, copy, `nginx -t`, reload. Data di `/var/lib/nexora-feedback/`
tetap. Widget: publish ulang dari build sebelumnya —
`/var/backups/accreditation/accreditation-20260918-050429.tar.gz` untuk kembali ke keadaan
pra-widget; `refresh.sh <app>` untuk kembali ke `dev` mana pun.

---

## 12. Yang sengaja tidak masuk

- **Provider LLM sungguhan / RAG** (Phase 4 di `WIDGET-README.md`). Semua tetap deterministik dan
  client-side. CSP `default-src 'self'` juga akan memblokir panggilan keluar dari browser, dan
  melonggarkannya bukan keputusan yang pantas diambil untuk sebuah prototipe.
- **n8n** untuk jalur feedback — `CLAUDE.md` §8 melarang webhook/workflow aktif tanpa persetujuan
  eksplisit owner, dan node `code`/`readWriteFile` memang dimatikan.
- **RBAC sisi server** untuk widget. Ketiga aplikasi adalah prototipe di balik satu Basic Auth
  bersama; identitas reviewer dikumpulkan untuk **atribusi feedback**, bukan sebagai kontrol akses.
- **Refactor bundle academy.** Dilarang keras oleh `AGENTS.md` repo itu; widget hanya di-append.

---

## 13. Pertanyaan terbuka untuk owner

1. **Drift RBAC** (§4.5, 2d): Staff 25 vs 24, Impartiality 5 vs 11 — angka mana yang benar?
2. **`docs/widget-readiness-ai-assistant.md`**: apakah dokumen aslinya masih ada di mesin Anda? Kalau
   ya, lebih baik dipakai daripada direkonstruksi.
3. **Retensi feedback**: berapa lama NDJSON disimpan, dan apakah reviewer boleh minta jejaknya
   dihapus?
4. **`PROTOTYPE_VERSION`**: setiap perubahan prototipe menaikkannya akan memutus keterikatan finding
   lama. Siapa yang memutuskan kapan dinaikkan?
5. Ketiga repo masih **public** (catatan terbuka dari laporan 2026-09-17) — tetap begitu, atau
   ditutup sebelum widget mengumpulkan data reviewer?
