# AI Assistant widget rollout — Fase 3 (ekstrak inti bersama, academy-only)

**Tanggal:** 2026-09-18 · **Host:** `31.97.67.241` (`dev-kemenkes`) · **Plan induk:**
`docs/ai-assistant-widget-rollout-plan.md` · **Lanjutan dari:**
`agents/reports/2026-09-18-ai-assistant-widget-fase2.md` · **Status:** selesai dan
terverifikasi, termasuk validasi lewat fixture sintetis **sebelum** repo academy
disentuh sama sekali (bundle academy yang sesungguhnya **tidak** disentuh sesi ini —
itu Fase 4). Service-desk tetap sepenuhnya tidak disentuh.

---

## 1. Kenapa urutannya beda dari dokumen rencana asli

Dokumen rencana aslinya mengasumsikan service-desk jadi "canary" murah (0 test) yang
menyerap kesalahan generalisasi sebelum academy (92 test) disentuh. Karena owner
memilih accreditation → academy langsung (service-desk pending), canary murah itu
tidak ada. Mitigasinya: **fixture sintetis** — host DOM palsu yang meniru kontrak
academy (`aside nav button`), dipasangi `rr-vanilla.js` + `widget/core/*`, dijalankan
headless — divalidasi habis-habisan di sesi ini, sebelum repo academy asli disentuh
sedikit pun.

---

## 2. Ekstraksi `widget/core/*`

Dipindah dari `nexaccred-react/src/widget/` ke `.../widget/core/`: `store.js`,
`registry.js`, `widget.css`, `store.smoke.mjs`, `collector.js`, `collector.smoke.mjs`,
`identity.js` (§3.1 dokumen rencana menandai ketujuh ini "Ya, generik"). Semua path
impor di `index.js` dan `ReadinessWidget.jsx` diperbarui (`./store` → `./core/store`,
dst). `version.js` di-rename jadi `app.config.js` (nama sesuai dokumen rencana) — 3
titik impor, perubahan kecil.

**Dua coupling nyata ditemukan & diperbaiki saat pemindahan** (bukan cuma
"pindah file", tapi build langsung gagal dan menunjukkan kopling yang harus
dibereskan sebelum core benar-benar portable):

1. **`collector.js` mengimpor `FEEDBACK_APP` langsung dari `./version.js`** — kalau
   dibiarkan, setiap app yang sync `core/` akan tetap terikat ke nama app
   accreditation. Diperbaiki: `FEEDBACK_APP` sekarang mengalir sebagai parameter
   (`createStore(project, {feedbackApp})` → `store.js`'s `appendEvent()` →
   `collector.enqueue()`), dicache per-project di `collector.js` sendiri — nol impor
   lintas-direktori.
2. **`registry.js` mengimpor `PROJECT_ID` dari `./version.js`** hanya sebagai nilai
   default saat `project` tidak diisi — begitu `registry.js` pindah ke `core/`, build
   langsung gagal: `Could not resolve "./version" from "src/widget/core/registry.js"`.
   Sambil membetulkan ini, dua cacat yang sudah lama ditandai dokumen rencana §3.3
   ikut diperbaiki sekalian (sudah di situ, tinggal disentuh):
   - **`widgetHandle()` tidak lagi jatuh ke `Object.values(handles)[0]` saat project
     key dikenal tapi salah** — sebelumnya, dua widget ter-mount + key salah ketik =
     diam-diam mengendalikan widget yang mendaftar pertama. Sekarang: key dikenal
     → resolve ke situ atau `null`; key kosong sama sekali → fallback ke yang pertama
     (kenyamanan host satu-widget).
   - **`registerWidget()` sekarang mengembalikan fungsi unregister**, dipakai di
     `ReadinessWidget.jsx`'s `useEffect` cleanup — handle tidak lagi menggantung
     setelah unmount.

**Bug ketiga, terpisah:** `store.js`'s gate math (`readiness()`) ternyata memakai
`CHECK_AREAS` **module-level yang tetap** (9 area accreditation), bukan apa pun yang
dikonfigurasi per-instance — ditemukan lewat fixture sintetis (lihat §4), bukan lewat
inspeksi kode manual. Diperbaiki: `createStore(project, {..., checkAreas =
CHECK_AREAS})` sekarang menerima daftar area per-app, `defaultChecks` dihitung dari
situ, dipakai konsisten di `getChecks()` dan `reset()`. Accreditation & service-desk
(nanti) tidak perlu mengubah apa pun — default-nya tetap 9 area lama. Academy (Fase
4) akan memberi daftarnya sendiri lewat parameter ini, bukan menimpa file bersama.

**Static check framework-agnostic** (`core/framework-agnostic.smoke.mjs`, baru):
grep otomatis bahwa setiap file di `core/` tidak mengimpor React/direktori induk dan
tidak mengandung sintaks JSX. GREEN untuk kelima file (termasuk `rr-vanilla.js`,
lihat §3). Diwire ke `npm run test:widget` sebagai langkah pertama.

**Copy UI dibersihkan sekalian:** `QUICK_PROMPTS` dipindah dari array string di
`ReadinessWidget.jsx` ke `{label, question}` object di `app.config.js` — memperbaiki
cacat lain yang sudah ditandai dokumen rencana ("`shortPrompt()` memilih ikon lewat
`q.startsWith('Apa saja')` — ubah kalimat, ikon diam-diam salah"). Fungsi
`shortPrompt()` dihapus seluruhnya.

## 3. `rr-vanilla.js` — shell DOM untuk academy

File baru, ~250 baris, di `widget/core/`. **Bukan** port 1:1 dari `ReadinessWidget.jsx`
(React) — dibangun langsung di atas `createElement`/`addEventListener` murni, mount ke
**shadow root miliknya sendiri**. Fungsional, bukan port visual: tab Ask/Findings/
Readiness/Jejak saya, identity gate wajib, notice transparansi permanen, checklist
gate + sign-off dengan pesan penolakan persis (`coverage N%, M open blocker(s)`) —
semua lewat `widget/core/store.js` yang sama, tanpa logika gate kedua yang bisa
menyimpang.

`mount(hostConfig)` menerima `buildContext()` (host membaca DOM-nya sendiri tiap
dipanggil — widget tetap pasif), `answerQuestion(q, ctx)` (mesin knowledge per-app,
akan diisi konten academy di Fase 4), `checkAreas` (per-app, lihat §2), dan
`onNavigate(route)`. Mengembalikan `unmount()`.

**Keterbatasan yang disengaja pass ini:** hanya gaya minimal inline (bukan replikasi
visual penuh `widget.css`/tema React), karena tujuan Fase 3 adalah membuktikan
mekanisme (gate math, identity gate, funnel collector, isolasi shadow-root) bekerja
identik — bukan mengejar kecocokan piksel dengan shell React. Kualitas visual final
academy adalah pekerjaan Fase 4/5.

## 4. Fixture sintetis — gerbang wajib sebelum academy asli disentuh

`core/__fixtures__/fake-host.html` — HTML mandiri meniru kontrak DOM academy yang
sesungguhnya (`tests/helpers.py` di repo academy): `aside nav button` untuk menu +
route aktif, tombol akun untuk identitas reviewer. `scripts/verify-vanilla-shell.mjs`
menyajikan `src/widget/` lewat static server lokal (impor modul ES butuh origin
sungguhan, bukan `file://`), menjalankan Chromium headless via Playwright.

**RED ditemukan sebelum GREEN — tiga temuan nyata, bukan cuma kesalahan skrip test:**
1. Gate tidak pernah 100% walau kedua area palsu dicentang → inilah yang membongkar
   bug `CHECK_AREAS` module-level di §2.
2. 404 ke `/widget-feedback/collect` muncul sebagai **console error tingkat browser**
   — bukan dari kode `collector.js` sendiri (yang memang tidak pernah
   `console.error`/throw), tapi Chromium sendiri mencatat response gagal ke console.
   **Ini flag penting untuk Fase 4**, dicatat eksplisit di §6: gerbang "zero console
   error" akademi bisa gagal murni dari respons jaringan gagal, terlepas dari
   seberapa rapi `collector.js` menangani error di level JS. Drill koneksi-putus Fase
   1 tidak menangkap ini karena diuji lewat nginx+collector sungguhan yang tetap
   membalas normal; belum pernah diuji terhadap skenario 404/502 asli.
3. Dua kegagalan skrip test (bukan bug widget): batch-klik checkbox lewat NodeList
   yang sudah basi (setiap perubahan store memicu re-render penuh, jadi node lama
   terlepas dari DOM), dan asersi pesan sign-off salah kutip nama — sign-off memang
   memakai **persona/reviewer dari context** ("Dinda Pramesti"), bukan **identitas
   asli** yang dikumpulkan widget ("Fixture Reviewer") — dua konsep terpisah dengan
   sengaja sejak Fase 1, dan perilaku ini sudah benar; ekspektasi test-nya yang salah.

Setelah tiga temuan itu diperbaiki: **GREEN, 12/12 assertion**, termasuk nol
console/page error di seluruh alur (identity gate → tanya jawab → checklist gate →
penolakan sign-off → checklist lengkap → sign-off diterima → tab Jejak saya).
`npm run test:vanilla-shell` (baru) menjalankannya.

## 5. `ops/prototypes/sync-widget.sh` — academy-only, ditegakkan lewat exit code

Script baru. Allowlist **hardcoded ke `academy` saja**; invoke tanpa argumen,
`service-desk`, atau `all` semuanya **ditolak eksplisit** (exit 2, pesan
"deferred, out of scope this pass") — diuji langsung, ketiganya berperilaku benar.
`sync-widget.sh academy` menyalin `widget/core/` ke
`/opt/nexora-prototypes/src/academy/widget/core/` (untracked scratch — `git status`
di repo academy menunjukkan hanya `?? widget/`, belum di-commit, sesuai rencana).

**Portabilitas diverifikasi nyata, bukan diasumsikan:** dijalankan langsung dari
salinan di repo academy (`node --input-type=module` mengimpor
`./widget/core/store.js` dari dalam pohon academy), `createStore` dengan
`checkAreas` custom 2-item menghasilkan gate `total: 2` (bukan 9) — membuktikan
parametrisasi §2 benar-benar berfungsi lintas-repo, bukan cuma lintas-direktori di
repo yang sama.

## 6. Verifikasi & publish

```
$ npm run test:widget
GREEN (framework-agnostic) / GREEN / GREEN (gate) / GREEN (collector) / GREEN (knowledge)

$ npm run test:vanilla-shell
GREEN (vanilla shell fixture) — 12/12

$ npm run build:standalone
✓ built in ~3s, 389.42 kB
```

Publish manual (prosedur sama, kredensial push masih belum ada — lihat laporan Fase
0/1 §2.5): backup
`/var/backups/accreditation/accreditation-pre-fase3-20260918-142848.tar.gz`, swap
atomik. `ops/prototypes/verify.sh` → ALL CHECKS PASSED. Probe browser langsung:
`window.NexReadiness.version` tetap `0.1.0`, quick prompt baru (`🧭 Guide my review`
dst.) tampil & berfungsi, jawaban matcher tetap benar, **0 console/page error**.

Gerbang akhir workspace: `tests/` 305 · `ops/harness/tests` 11 · `ops/nginx/tests` 20
· `ops/n8n/tests` 10 · `ops/feedback/tests` 26 — semua hijau, tidak berubah dari Fase
2 (Fase 3 tidak menyentuh infra/nginx/collector server-side sama sekali).

---

## 7. File yang disentuh

**Repo `accreditation`** (masih belum ter-push — lihat §2.5 laporan Fase 0/1):
dipindah ke `nexaccred-react/src/widget/core/`: `store.js`, `registry.js`,
`widget.css`, `store.smoke.mjs`, `collector.js`, `collector.smoke.mjs`, `identity.js`.
Baru: `core/rr-vanilla.js`, `core/framework-agnostic.smoke.mjs`,
`core/__fixtures__/fake-host.html`, `scripts/verify-vanilla-shell.mjs`. Rename:
`widget/version.js` → `widget/app.config.js`. Diubah: `index.js`,
`ReadinessWidget.jsx` (path impor + `QUICK_PROMPTS` + cleanup unregister),
`package.json` (`test:vanilla-shell`).

**AI-Workspace:** baru `ops/prototypes/sync-widget.sh`.

**Repo `academy`:** untracked scratch `widget/core/` (hasil sync, belum dipakai —
Fase 4's job).

## 8. Rollback

Semua perubahan repo `accreditation` masih di working tree lokal, belum pernah
ter-commit — hapus/`git checkout --` untuk kembali ke akhir Fase 2. Untuk publish
live: restore `accreditation-pre-fase3-20260918-142848.tar.gz`. Repo academy: hapus
direktori `widget/` untracked — nol risiko, belum ada yang bergantung padanya.

## 9. Yang harus dibawa ke Fase 4, eksplisit

1. **Verifikasi live-browser dulu** untuk klaim "active nav = class pada
   `aside nav button`" (§5.1 dokumen rencana) — tidak terbukti di `tests/helpers.py`
   academy, belum diverifikasi sesi ini karena bundle academy asli belum disentuh.
2. **404/502 dari collector bisa muncul sebagai console error tingkat browser**,
   independen dari penanganan error `collector.js` sendiri (§4 temuan #2) — perlu
   diuji ulang khusus terhadap jalur nginx+collector *asli* dalam kondisi gagal
   (bukan cuma service dimatikan seperti drill Fase 1, yang ternyata tidak memicu
   ini), sebelum akademi mengandalkan "collector.js tidak pernah console.error" saja
   sebagai jaminan cukup untuk 92 test Playwright.
3. `checkAreas` academy sendiri (domain berbeda total dari 9 area accreditation)
   perlu ditulis dari nol — mekanismenya sudah siap (§2), isinya belum.
4. `knowledge.js`/`context.js` academy (baca `docs/` corpus ~170KB) — belum disentuh
   sama sekali sesi ini, murni Fase 4.
