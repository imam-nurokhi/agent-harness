# AI Assistant widget — Requirement Readiness experiment (NEXACCRED pilot)

**Status:** eksperimen, Phase 1 (widget + contextual feedback). **Reconstructed** 2026-09-18
from `nexaccred-react/src/widget/WIDGET-README.md` + kode sumber (`store.js`, `knowledge.js`,
`contextAdapter.js`, `index.js`) di commit `dcb8aee` — file aslinya tidak pernah ditemukan di
repo, GitHub, atau filesystem host manapun, meski tiga intent knowledge (`gate`, `evidence-model`,
`pilot`) dan tiga file kode (`store.js` §6, `knowledge.js` §5, `contextAdapter.js` §4) mengutipnya.
Lihat `agents/reports/2026-09-18-ai-assistant-widget-rollout.md` untuk konteks pemulihannya.

Dokumen ini adalah **sitasi kepada reviewer**, bukan spesifikasi produk — `01-PRD-NexAccred.md`,
`03-Data-Model-NexAccred.md`, `04-Business-Process-NexAccred.md`, dan `05-RBAC-Separation-of-Duties.md`
di root repo `accreditation` tetap sumber kebenaran domain. Dokumen ini hanya menjelaskan **widget
itu sendiri**: apa yang dijawabnya, apa yang direkamnya, dan batasannya.

---

## §1. Apa ini

Widget floating (`✦ AI Assistant`, kanan bawah) yang dipasang di atas prototipe review NEXACCRED.
Tiga tab: **Ask** (tanya jawab bersumber dokumen), **Findings** (triase manusia atas
ketidakcocokan/gap yang ditemukan), **Readiness** (checklist gate + sign-off). Framework-agnostic
di intinya (`store.js`, `knowledge.js` tanpa dependensi React) dengan shell UI React
(`ReadinessWidget.jsx`) dan API publik `window.NexReadiness` / `window.RequirementReadiness`.

## §2. Scope pilot

Pilot review surface NEXACCRED menguji: role-based access, readiness calculation, accreditation
scope, assessment rules, critical/major issues, personnel & competence, document/evidence,
impartiality, dan approval boundary — sembilan area yang persis memetakan ke `CHECK_AREAS` (§7).
Setiap sesi terikat ke **satu** `PROTOTYPE_VERSION` (`nexaccred-react/src/widget/version.js`);
findings yang dicatat pada versi tertentu terikat ke versi itu selamanya — menaikkan
`PROTOTYPE_VERSION` memutus keterikatan itu secara sengaja, supaya finding lama tidak tertukar
dengan versi baru (lihat §8, batasan sadar).

## §3. API publik

`window.NexReadiness` (`index.js`): `{ version, PROJECT_ID, PROTOTYPE_VERSION, createStore,
answerQuestion, buildContext }` — antarmuka framework-agnostic untuk host non-React.

`window.RequirementReadiness` (paritas dengan referensi vendored
`nexaccred_requirement_readiness_prototype/rr-widget.js`): `{ init, setContext, open, ask, reset }`
— kontrak yang diasumsikan oleh host vanilla yang ditulis terhadap referensi tersebut. **Catatan
implementasi terkini:** `init()` dan `setContext()` masih no-op di build `dcb8aee` (lihat rencana
rollout §3.3) — host vanilla (mis. academy) tidak bisa mengandalkan pemanggilan ini untuk mount;
diberi implementasi nyata saat generalisasi widget ke inti bersama.

## §4. Kontrak konteks host minimum

Dikutip oleh `contextAdapter.js`. Host membangun ulang objek `context` **setiap render** dan
menyerahkannya sebagai satu prop — widget sepenuhnya pasif, tidak pernah membaca router/URL/auth
sendiri:

```
{ project, environment, prototypeVersion, route, screen, param,
  reviewer: { name, title, role },
  weights?  // ringkasan konfigurasi saja, TIDAK PERNAH seluruh dataset domain
}
```

Aturan privasi tertulis di kode dan mengikat: **ringkasan konfigurasi saja** (contoh: bobot 8
pilar), tidak pernah state domain penuh (daftar assessment, dokumen, personel individual, dst).

## §5. Guardrail jawaban AI

Dikutip oleh `knowledge.js`, mengikat bersama PRD FR-10:

- Jawab **hanya** dari sumber yang disetujui (`SOURCES`: PRD, DATA_MODEL, RBAC, PROCESS, APP
  runtime, WIDGET/dokumen ini). Tidak ada sumber cocok → klasifikasi `CLARIFICATION_NEEDED` +
  arahan mencatat finding — widget tidak pernah mengarang jawaban.
- Asumsi/saran **tidak pernah** disajikan sebagai requirement yang disetujui.
- AI **tidak pernah** menyetujui (approve), menuduh (assign blame), atau membuat keputusan
  compliance formal — sesuai FR-10, semua jawaban bersifat advisory dan berlabel jelas (aksen
  violet di UI).
- Bilingual ID/EN. Best-match menang: rule dengan skor keyword terbanyak yang menjawab, sehingga
  pertanyaan spesifik mengalahkan yang generik.

## §6. Model auditabilitas — evidence over blame

Dikutip oleh `store.js`. **Auditabilitas berasal dari events tersimpan + keputusan manusia, tidak
pernah dari opini AI.** Semua yang direkam widget masuk `localStorage` di bawah kunci
ber-versi (`nexreadiness:<project>:<part>`) supaya sesi review selamat dari refresh dan tetap bisa
diatribusikan ke satu versi prototipe.

Bentuk yang disimpan:

- **session** — `{ id, project, environment, prototypeVersion, reviewer, startedAt }`
- **messages** — tiap giliran Ask, dengan `sources[]` dan `classification`
- **findings** — `{ id, question, aiResponse, sources[], classification, severity, status, route,
  screen, param, prototypeVersion, reviewer, owner, decision, decidedBy, decidedAt,
  resultingVersion, at }`
- **events** — append-only: `session.started, route.viewed, question.asked, answer.given,
  finding.recorded, reviewarea.checked, finding.decided, baseline.signoff, session.reset`
- **signoff** — `{ status: PENDING|APPROVED|APPROVED_WITH_EXCEPTIONS|REJECTED, version, by, role,
  note, at }`

**Transisi status finding hanya oleh manusia**: `open → accepted | rejected | superseded`. AI boleh
menyarankan status, tidak boleh menulisnya. Sistem tidak menuding siapa pun — hanya menyediakan
jejak (evidence over blame).

NFR yang mengikat: tiap aksi state-changing tercatat immutable (who/what/when/entity); tiap klaim
readiness harus traceable ke requirement + evidence; perubahan bobot & permission audit-trailed.

## §7. Gate & sign-off

**Prototype Ready ≠ Requirement Ready ≠ Development Ready.** Gate widget ini: sembilan
`CHECK_AREAS` (§2) harus 100% ditandai selesai **dan** nol open blocker:

```js
percent = Math.round(done / 9 * 100);
blockers = findings.filter(f => f.blocking && f.status === 'open').length;
ready    = percent === 100 && blockers === 0;
```

`severity ∈ {blocker, major, minor, info}` hanyalah metadata deskriptif; **`blocking: boolean`**
adalah flag terpisah yang benar-benar dihitung gate. Menerima/menolak finding membersihkan gate
tanpa menghapus buktinya (finding tetap tersimpan, hanya `status` berubah).

Sign-off (`signOff()`) **menolak** secara eksplisit — bukan sekadar memperingatkan — selama gate
belum lolos, dengan alasan persis: `{ok:false, reason:'coverage N%, M open blocker(s)'}`. Status
sign-off terikat satu `PROTOTYPE_VERSION` tertentu.

**Pasca-baseline**, begitu sign-off `APPROVED`/`APPROVED_WITH_EXCEPTIONS`, finding baru otomatis
diklasifikasi `CHANGE_REQUEST` — bukan perubahan scope yang diam-diam. Alur lengkap: New/Changed
Requirement → Change Request → Impact Assessment → Human Decision → Recorded Approval → Planning →
Implementation → Verification. Pertanyaan yang wajib terjawab pada tiap perubahan: sudah adakah
saat baseline? kapan muncul? siapa pengusul & penyetuju? versi & sprint terdampak? defect-vs-baseline
atau scope change?

## §8. Batasan sadar (dan roadmap yang sengaja tidak diambil)

- Knowledge masih rule-based lokal, bukan retrieval/LLM sungguhan (itu Phase 4 — lihat rencana
  rollout §12: sengaja tidak masuk, karena CSP `default-src 'self'` juga akan memblokir panggilan
  keluar dari browser).
- Belum ada backend: multi-reviewer, dashboard agregat, atau versioning server-side (Phase 2–5,
  belum diambil).
- **Naikkan `PROTOTYPE_VERSION` tiap kali prototipe berubah** — kalau tidak, finding lama akan
  tertukar dengan versi baru yang tidak lagi merepresentasikan state yang sama. Siapa yang berhak
  menaikkannya adalah keputusan owner (lihat rencana rollout §13.4), bukan keputusan engineering.
- `init()`/`setContext()` di `window.RequirementReadiness` masih no-op (§3) — jangan bangun host
  vanilla di atas asumsi bahwa keduanya melakukan sesuatu sampai generalisasi widget memberi
  implementasi nyata.

## Paritas referensi

Dibandingkan dengan build referensi yang di-vendor
(`nexaccred_requirement_readiness_prototype/rr-widget.js`, IIFE bebas framework): tab Ask/Findings/
**Readiness** (dulu disebut *Session* di referensi), quick prompts, checklist 9 area, gate 100%+0
blocker, flag `blocking` per finding, `window.RequirementReadiness.open/ask/setContext/reset` +
hook `window.updatePrototypeStatus(snapshot, gate)`. Perbedaan sadar: widget ini melacak triase
finding `open→accepted/rejected/superseded` (referensi: `OPEN→RESOLVED`), memisahkan `severity` dari
`blocking`, dan knowledge-nya ter-grounding ke paket v1.0 NEXACCRED asli (referensi mensimulasikan
jawaban dengan skor tetap 87%, tanpa grounding nyata).
