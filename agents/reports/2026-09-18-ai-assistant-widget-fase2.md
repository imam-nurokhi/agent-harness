# AI Assistant widget rollout — Fase 2 (strengthen accreditation self-knowledge)

**Tanggal:** 2026-09-18 · **Host:** `31.97.67.241` (`dev-kemenkes`) · **Plan induk:**
`docs/ai-assistant-widget-rollout-plan.md` · **Lanjutan dari:**
`agents/reports/2026-09-18-ai-assistant-widget-fase0-fase1.md` · **Status:** Fase 2a–2d
selesai dan terverifikasi live. Repo `accreditation` masih belum bisa di-push (lihat
laporan Fase 0/1 §2.5) — publish tetap manual, sama seperti Fase 1.

---

## 1. Fase 2a — Matcher baru: tokenized + idf-lite + ambang minimum + top-3

### 1.1 Regression set dulu (TDD)

`nexaccred-react/src/widget/knowledge.smoke.mjs` (baru) — ~45 pertanyaan ID+EN,
termasuk pertanyaan persis yang memaksa commit `dcb8aee` ("apa aturan blocking?") dan
jebakan substring yang commit itu tinggalkan.

**RED terhadap matcher lama:** 13 gagal, termasuk yang terkonfirmasi persis seperti
temuan dokumen rencana:
- `'ai '` cocok di dalam "email" → "kirim notifikasi ke email siapa?" salah dijawab
  `ai-layer`.
- `'kan '` cocok di kata apa pun mengandung substring itu → kalimat panjang berisi
  "akan...bagaimana" salah dijawab.
- `'cap '` (hack spasi-akhir) cocok di dalam "capable".
- **Seri dimenangkan urutan array** (bukan cuma trap): "kenapa readiness turun jadi
  ready with risks?" dijawab `readiness-formula` (rule pertama di array), bukan
  `readiness-why-capped` yang sebenarnya relevan — keduanya skor sama di bawah matcher
  lama, dan `readiness-formula` menang karena dipindai duluan. Ini persis kalimat
  dokumen rencana: *"seri dimenangkan urutan array, sehingga readiness-formula sangat
  difavoritkan."*

### 1.2 Desain matcher baru

Setiap keyword — kata tunggal maupun frasa — direduksi ke token
(`/[a-z0-9]+/g`, lowercase) dan dicocokkan sebagai **rangkaian token utuh** ber-padding
spasi terhadap token pertanyaan, bukan `String.includes` mentah:

- **Kata pendek (≤4 karakter, tempat semua jebakan lama hidup — `r1`–`r4`, `p1`–`p7`,
  `ai`, `kan`)** wajib cocok sebagai **satu token utuh**. "Q1" tokenisasi jadi `q1`,
  tidak pernah sama dengan token `r1`.
- **Kata tunggal panjang (>4 karakter)** boleh tetap cocok sebagai substring di dalam
  token lain — supaya imbuhan bahasa Indonesia tetap tertangkap ("dihapus" tetap
  cocok ke akar kata "hapus", persis seperti matcher lama secara kebetulan). Ini
  trade-off yang disengaja, bukan terlewat: versi pertama pakai whole-token-only untuk
  semua kata dan itu **memecah** pencocokan imbuhan — ditemukan lewat regression test
  sendiri, diperbaiki dengan aturan panjang ini.
- **Frasa (≥2 token)** wajib cocok sebagai rangkaian token kontigu (menggantikan
  substring mentah lama, jadi tidak sensitif spasi ganda/tanda baca).

**idf-lite:** setiap keyword dapat skor dasar (frasa=3, kata panjang=2, kata
pendek=1) **plus bonus +1 jika keyword itu unik untuk satu rule** (document frequency
1 dalam pool-nya). Document frequency dihitung **terpisah per pool** (manual vs
generated — lihat §2) supaya kata umum di KB generated tidak melemahkan bonus
keyword manual yang kebetulan sama.

**Ambang minimum:** `MIN_SCORE = 2` — satu kecocokan keyword pendek yang **dipakai
bersama** ≥2 rule (skor 1, tanpa bonus unik) sekarang gagal ambang dan turun ke
`CLARIFICATION_NEEDED` alih-alih otomatis "menjawab" seperti matcher lama (yang
efektif berambang 1). **Catatan jujur:** di 26-intent KB manual saat ini, hampir
semua keyword sudah unik per rule (hanya `audit trail` dan `matriks` yang dipakai
≥2 rule, keduanya kata panjang jadi tetap lolos ambang) — jadi ambang ini jarang
benar-benar memfilter apa pun di KB manual sekarang. Ia akan mulai berperan nyata
begitu KB generated (§2, banyak label layar/role yang berpotensi tumpang tindih)
tumbuh lebih padat. Mekanismenya sudah benar dan teruji; efeknya baru terasa penuh
nanti — dicatat di sini supaya tidak ada yang mengira ambang ini "tidak melakukan
apa-apa" karena bug.

**Top-3 "Maksud Anda…?":** saat tidak ada rule mencapai ambang, jawaban
`CLARIFICATION_NEEDED` sekarang menyertakan hingga 3 topik berskor tertinggi (dari
gabungan pool manual+generated) sebagai saran, bukan sekadar "saya tidak tahu" kosong
seperti sebelumnya.

### 1.3 GREEN — dan koreksi yang ditemukan di tengah jalan

Setelah implementasi awal: 6 gagal tersisa, semuanya ditelusuri satu per satu dan
ternyata **bukan bug matcher, tapi kesalahan penulisan test sendiri** (hint jawaban
yang salah dikutip, `ctx.reviewer.role` tidak diisi untuk `role-guide`, dan dua
pertanyaan uji yang ternyata memang secara sah cocok ke keyword lain — "email" memang
keyword sah untuk `demo-accounts`, "direvisi" memang sah cocok ke akar kata "revisi"
di rule `gate`). Setelah dikoreksi: **GREEN, 0 gagal**, exit 0. Diwire ke
`npm run test:widget` (bersama `store.smoke.mjs` dan `collector.smoke.mjs` dari Fase
1) — ketiganya jalan berurutan dalam satu perintah.

---

## 2. Fase 2b — KB turunan-kode (`scripts/gen-knowledge.mjs`)

Skrip baru, dijalankan `node scripts/gen-knowledge.mjs` (atau `npm run gen:knowledge`),
membaca `src/data/roles.js` dan `src/screenRegistry.jsx` sebagai teks (regex, bukan
parser JS/JSX penuh — dua file saja, bentuknya stabil, dependency parser tidak
sepadan) dan memancarkan `src/widget/knowledge.generated.js` — **48 rule**: 1 ringkasan
nav, 6 akses-per-role, 41 status-per-layar.

**Dua bug ditemukan & diperbaiki saat generator ditulis** (bukan di app, di skrip
generator itu sendiri):
1. Regex tunggal untuk parse `ROLES` memakai beberapa grup opsional dipisah `[\s\S]*?`
   lazy — akibatnya `routes: [...]` untuk 5 dari 6 role **kosong senyap** (hanya role
   `head`, yang justru TIDAK punya array `routes`, kebetulan lolos). Diperbaiki
   dengan memecah `ROLES` per blok role dulu (posisi `^  \w+: \{`), baru regex
   sederhana per blok — bukan satu regex raksasa. **Manfaat sampingan:** setelah
   diperbaiki, generator menghasilkan angka **Staff 24, Impartiality 11** — cocok
   persis dengan yang diverifikasi manual di eksplorasi awal sesi ini, dan inilah
   bukti mekanis untuk keputusan §4.
2. Kunci `tableConfigs` yang mengandung tanda hubung ditulis dengan quote
   (`'evidence-repository': {`), regex saya semula hanya menangkap kunci tanpa quote
   → 7 layar (evidence-repository, forms-templates, internal-assessment,
   compliance-report, assessment-pack, management-report, audit-trail) **salah**
   ditandai "TIDAK punya implementasi" padahal semuanya nyata. Diperbaiki: regex
   kunci sekarang menerima quote opsional. Setelah fix: **0 nav item salah ditandai
   tidak-implementasi** — sesuai fakta, karena kedua route mati (`assessment-prep`,
   `ab-register`) memang bukan nav item top-level, hanya sub-route lewat
   `PARENT_NAV`.

**Manual menang atas generated:** diimplementasikan dengan memisahkan alur, bukan
menggabung satu pool — `answerQuestion()` sekarang mengecek pool **manual dulu**;
hanya jatuh ke pool **generated** kalau manual tidak mencapai `MIN_SCORE`. Ini juga
menghindari kontaminasi idf antar-pool (lihat §1.2). Diverifikasi langsung: pertanyaan
yang menyentuh kosakata RBAC umum ("akses auditor kemana saja?") tetap dijawab rule
manual (`rbac-matrix`) yang memang relevan; pertanyaan memakai kosakata role-id murni
("doccontrol") yang TIDAK ada padanannya di KB manual berhasil dijawab generated
(`gen-role-routes-doccontrol`) dengan sumber `CODE`.

**Keterbatasan yang diketahui, dicatat jujur:** ekstraksi teks `sub=` dari komponen
`PageHead` di `screens/*.jsx` (~35 kalimat, ditulis untuk manusia) **sengaja tidak
dikerjakan** pass ini — pemetaan teks itu ke route yang benar butuh baca JSX
terstruktur (bukan regex teks aman), dan `tableConfigs`-nya sendiri sudah menyediakan
`title`+`sub` untuk 21 dari 41 layar secara akurat. Layar di luar `tableConfigs`
mendapat deskripsi dari `NAV.label` + status implementasi, bukan kalimat `sub=`
aslinya. Follow-up yang jujur untuk sesi berikutnya, bukan cacat tersembunyi. Bacaan
`readiness.js`/`schemes.js`/`records.js` (bobot, state demo) juga belum dikerjakan
pass ini — di luar dua sumber yang sudah dipakai.

`SOURCES` di `knowledge.js` ditambah `README` (`00-README-Document-Index.md`), `ERD`
(`02-ERD-NexAccred.mermaid`), dan `CODE` (label untuk KB ter-generate) — sesuai
rencana §2b.

---

## 3. Fase 2c — Dua route mati

- **`ab-register`** — perbaikan satu baris murni: komponen sudah diimpor
  (`screenRegistry.jsx:13`), tinggal tambah
  `case 'ab-register': return <AbRegister ctx={ctx} onNavigate={navigate} />;` —
  signature-nya (`{ctx, onNavigate}`) persis sama dengan `StandardRegister`/
  `SchemeRegister` yang sudah dipakai, jadi tidak butuh perubahan lain.
- **`assessment-prep`** — biaya jauh lebih besar dari `ab-register` (persis seperti
  yang dicatat dokumen rencana): dipanggil dengan parameter `schemeKey` dari dua
  tempat (tombol "Prepare for Assessment" di `Dashboards.jsx:155` dan
  `Accreditation.jsx:91`), tapi **tidak ada screen sama sekali** untuknya di mana
  pun — bukan cuma `case` yang hilang. Alur checklist persiapan assessment sungguhan
  (BP-3: notifikasi 45/30/14/7 hari, dokumen wajib per scheme, status witness) adalah
  fitur nyata yang perlu di-scope bersama owner, bukan sesuatu yang pantas
  diimprovisasi di sini. Ditambahkan **stub jujur** (`AssessmentPrep` di
  `screens/Accreditation.jsx`, baru): breadcrumb + judul benar, `Note` oranye yang
  secara eksplisit bilang "belum diimplementasikan di prototipe ini" (bukan pesan
  generik "not implemented"), dan dua tombol nyata yang mengarah ke apa yang SUDAH
  ada untuk scheme itu (Scheme Detail, AB Assessment) — supaya klik tombol tidak
  jadi jalan buntu, tapi juga tidak berpura-pura fitur itu sudah ada.
  - **Bug kecil ditemukan saat menulis stub ini:** komponen `PageHead` di
    `components/ui.jsx:85` hanya meneruskan `c.route` saat breadcrumb diklik, **tidak
    pernah** `c.param` — draf pertama stub ini menaruh `param: key` di breadcrumb
    "Scheme Detail" yang, kalau diklik, akan diam-diam mendarat di scheme default
    (`iso27001`) alih-alih scheme yang sedang di-prep. Diperbaiki sebelum sempat
    tayang: breadcrumb scheme dibuat tidak-bisa-diklik (label statis), param yang
    benar hanya dikirim lewat tombol "Buka Scheme Detail" yang memang mendukungnya.

Setelah kedua perbaikan: `npm run build:standalone` sukses, 0 error build.

---

## 4. Fase 2d — Drift RBAC: kode dipakai sebagai ground truth

`05-RBAC-Separation-of-Duties.md` §4 (tabel "Nav items") mengklaim Staff=25,
Impartiality=5. Kode (`src/data/roles.js#ROLES`) menghasilkan Staff=24,
Impartiality=11 — dikonfirmasi dua kali independen: sekali oleh Explore agent di awal
sesi (pembacaan manual), sekali lagi oleh `scripts/gen-knowledge.mjs` (ekstraksi
mekanis) di §2.

**Keputusan:** dokumen dikoreksi mengikuti kode, bukan sebaliknya — dan ini bukan
keputusan kebijakan yang perlu ditunda ke owner, karena **empat dari enam baris tabel
yang sama sudah cocok persis dengan kode** (Head 41, Auditor 14, DocControl 9, Admin
8) sebelum apa pun disentuh. Hanya dua baris yang menyimpang, dan pola itu jauh lebih
konsisten dengan "dua angka jadi salah ketik/basi di dokumen" dibanding "enam baris
seharusnya representasi rencana produk yang kode-nya justru menyimpang di 2 tempat
acak." Baris tabel diubah ke 24/11, dengan catatan editorial menyebutkan tanggal,
angka lama, dan cara verifikasinya (`src/data/roles.js#ROLES[id].routes.length`, lihat
juga `scripts/gen-knowledge.mjs`).

---

## 5. Verifikasi & publish

```
$ npm run test:widget    # store.smoke.mjs + collector.smoke.mjs + knowledge.smoke.mjs
GREEN / GREEN (gate) / GREEN (collector) / GREEN (knowledge)

$ npm run build:standalone
✓ built in ~3s, 388.44 kB (naik dari 371 kB Fase 1 — KB generated + matcher baru)
```

Publish manual (prosedur sama seperti Fase 1, kredensial push masih belum ada — lihat
laporan Fase 0/1 §2.5): backup live dulu
(`/var/backups/accreditation/accreditation-pre-fase2-20260918-141454.tar.gz`), lalu
swap atomik ke `/var/www/prototypes/accreditation/`.

`ops/prototypes/verify.sh` → ALL CHECKS PASSED (termasuk `/widget-feedback/` dan
"neighbours untouched" dari Fase 1, tidak berubah).

Probe browser langsung terhadap `/accreditation/` live: identity gate tetap muncul,
"apa aturan blocking?" sekarang menjawab dengan "R1" tersebut secara eksplisit (bukan
lagi kalah seri ke `readiness-formula`), "menu apa saja yang ada?" menjawab lewat KB
generated (ringkasan 41 nav/8 grup), **0 console error, 0 page error**.

Gerbang akhir workspace, semua hijau:
```
tests/               305  ·  ops/harness/tests  11  ·  ops/nginx/tests  20
ops/n8n/tests         10  ·  ops/feedback/tests  26
```

---

## 6. File yang disentuh (repo `accreditation`, masih belum ter-push — lihat §2.5
laporan Fase 0/1)

Baru: `scripts/gen-knowledge.mjs`, `src/widget/knowledge.generated.js`,
`src/widget/knowledge.smoke.mjs`. Diubah: `src/widget/knowledge.js` (matcher +
SOURCES + manual/generated split), `src/screenRegistry.jsx` (2 route),
`src/screens/Accreditation.jsx` (+`AssessmentPrep`), `package.json`
(`gen:knowledge` script), `05-RBAC-Separation-of-Duties.md` (§4, 2 angka).

## 7. Rollback

Murni git-level di repo `accreditation` (tidak ada perubahan infra/service/nginx di
Fase 2) — belum ada commit untuk di-revert karena belum pernah di-commit; hapus/`git
checkout --` file yang disebut §6 untuk kembali ke state akhir Fase 1. Untuk
publish-an live: restore
`/var/backups/accreditation/accreditation-pre-fase2-20260918-141454.tar.gz`.

## 8. Lanjutan

Fase 2 selesai. Fase 3 (ekstrak `widget/core/*` bersama, divalidasi lewat fixture
sintetis sebelum menyentuh academy) adalah langkah berikutnya sesuai urutan owner
(accreditation → academy, service-desk tetap pending). Kredensial push GitHub masih
jadi blocker yang sama untuk setiap fase widget-side berikutnya.
