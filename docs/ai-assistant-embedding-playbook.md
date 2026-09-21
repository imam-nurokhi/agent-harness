# AI Assistant Embedding Playbook — standing directives

> Berlaku untuk SEMUA aplikasi ke depan. Implementasi referensi kanonis:
> `projects/nexora/accreditation/nexaccred-react/src/widget/`
> (pola), `projects/nexora/accreditation/nexaccred_requirement_readiness_prototype/`
> (prototipe perilaku). Doktrin: `docs/widget-readiness-ai-assistant.md`.
>
> Saat user berkata "pasang AI Assistant ke aplikasi X" → ikuti dokumen ini
> + bedah referensi aplikasi X. **Tanpa perlu instruksi/guide ulang.**

## 1. Dua arahan permanen user (non-negotiable)

1. **Kecerdasan maksimal** — assistant harus menjawab sebanyak mungkin dari
   sumber approved aplikasi itu (dokumen + runtime), meminimalkan
   `CLARIFICATION_NEEDED`. Fallback jujur hanya untuk yang benar-benar di
   luar scope.
2. **Interaktif** — user harus langsung aware terhadap jawaban/aksi:
   auto-scroll ke chat terakhir, FAB mencolok, teaser, badge, quick prompts.
   Tidak boleh ada jawaban yang "muncul diam-diam".

## 2. Pola implementasi (copy structure, isi dari app target)

```
src/widget/  (atau src/assistant/ — nama folder bebas, struktur tetap)
  version.js         PROJECT_ID, PROTOTYPE_VERSION (naikkan tiap app berubah),
                     WIDGET_VERSION
  store.js           vanilla evidence store: session/messages/findings/events/
                     signoff/checks/gate. localStorage + memory mirror.
                     getSnapshot() WAJIB referentially stable (cache, invalidate
                     on write) — kalau tidak, useSyncExternalStore infinite
                     loop = blank page. Ada smoke test-nya (lihat §5).
  knowledge.js       answer engine dependency-free, bilingual (ID/EN).
                     Best-match scoring (bobot keyword panjang), bukan first-match.
                     Tanpa skor → CLARIFICATION_NEEDED + arahan jadi finding.
  contextAdapter.js  kontrak minimum: project, environment, prototypeVersion,
                     route, screen, param, reviewer{name,title,role} (+ ringkasan
                     state, BUKAN seluruh dataset).
  XxxWidget.jsx      FAB + panel 3 tab: Ask / Findings / Readiness(gate).
                     Mount di SEMUA entry (app + standalone + login).
  registry.js        window.RequirementReadiness.open/ask/reset + hook
                     window.updatePrototypeStatus(snapshot, gate) untuk host
                     non-React / script-tag.
  widget.css         attention system (lihat §4).
  *.smoke.mjs        tes node langsung (tanpa browser).
```

## 3. Checklist adaptasi per aplikasi (sumber = referensi app itu)

1. **Bedah dokumen sumber** (PRD, data model/ERD, RBAC/permissions, business
   process, README) + **kode runtime** (engine, config/defaults, seed/demo,
   routes, roles). Daftar semua fakta yang bisa jadi jawaban.
2. **knowledge.js**: ~20–30 intent dari fakta di atas. Tiap intent: keywords
   ID+EN, klasifikasi, daftar sumber, fungsi answer(ctx) dengan personalisasi
   (role/screen/weights reviewer). Pertahankan fallback jujur.
3. **contextAdapter**: petakan state host (role/route/param/user) + label
   layar + "pilot hint" per route (apa yang diuji di layar itu).
4. **Gate khas app**: definisikan area checklist + rumus passed + status
   sign-off + perilaku pasca-baseline (default CHANGE_REQUEST). Jangan
   biarkan sign-off lolos saat gate unpassed — tolak + beri alasan.
5. **Sembunyikan yang redundan**: tombol/menu AI lama di-hide (flag seperti
   `HIDDEN_NAV_KEYS`, bukan delete) setelah widget live — satu pintu AI.
6. **Port & kredensial demo** dicatat di AGENTS.md app + smoke probe bila ada
   backend (contoh: `test/api-smoke.mjs` pola RED→GREEN).

## 4. Standar awareness (FAB mencolok)

- FAB: gradient + **pulse-ring infinite (box-shadow saja)** + float **terbatas
  (3x saat load)** — infinite transform membuat tombol tidak stabil & susah
  diklik (terbukti di tes Playwright).
- Teaser bubble sekali per session, auto-dismiss ~15 dtk / saat dibuka.
- Badge merah = jumlah open findings saat panel tertutup (alasan kembali).
- Quick prompts (4) + auto smooth-scroll ke pesan terbaru tiap interaksi.
- Label konsisten: **"✦ AI Assistant"**.

## 5. Verification bar (wajib hijau sebelum klaim selesai)

1. `node` smoke store (stabilitas snapshot, finding lifecycle, gate math).
2. `node` knowledge checks: ≥20 pertanyaan representatif → grounded;
   hanya yang out-of-scope → CLARIFICATION_NEEDED.
3. `npm run build` (+ standalone bila ada) tanpa error.
4. Playwright chromium: halaman render (bukan blank), login/E2E inti,
   FAB+teaser+badge, tanya→jawaban grounded, checklist persist, 0 pageerror.

## 6. Hard rules (pelanggaran = revert)

- AI tak mengarang, tak approve, tak menuding; keputusan = manusia bernama.
- Audit = stored events + human decisions; findings terikat versi selamanya.
- Tak ada secret di repo (`.env`, kredensial non-demo); `node_modules`,
  `dist*`, `test-results` ter-exclude.
- Push hanya ke `dev`/`staging`; `main` owner-controlled.
