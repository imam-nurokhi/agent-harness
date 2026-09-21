# AI Assistant widget — academy first-access + accreditation intelligence (Fase 6) + collector hardening

**Tanggal:** 2026-09-19 (lanjutan kerja 2026-09-18) · **Host:** `31.97.67.241` (`dev-kemenkes`) ·
**Plan induk:** `docs/ai-assistant-widget-rollout-plan.md` · **Lanjutan dari:**
`agents/reports/2026-09-18-ai-assistant-widget-fase4-academy.md` ·
**Metode owner:** OODA + TDD, root-cause sebelum fix. **Service-desk: tidak disentuh (sesuai owner).**

**Status:** semua perubahan **selesai, terverifikasi, dan TAYANG** di kedua app (deploy manual
disetujui owner 2026-09-19, backup diambil dulu, sha256 live == yang diuji). **Belum ter-push ke git**:
GitHub connector **read-only (403)** dan tak ada kredensial push lokal, jadi utang "live ≠ git-reproducible"
untuk SELURUH kode widget uncommitted (Fase 0–5 + ini) masih terbuka sampai owner menambahkan PAT (§7).

---

## 1. Observe/Orient — keadaan terukur saat mulai

Diverifikasi (bukan diasumsikan): Fase 0–3 (accreditation) & port academy **sudah live & hijau**
(academy 92/92, accreditation smoke hijau), collector feedback jalan & data mengalir untuk kedua app,
semua kode widget **uncommitted** (akan hilang pada fresh clone). Satu isu terukur di journal:
`ah-feedback` melempar `BrokenPipeError` di `collector.py:205` (`_send_json`) pada 2026-09-18 14:29Z.

## 2. Academy — AI Assistant muncul dari FIRST ACCESS ke /academy/

**Root cause (bukan tebak):** `academy/widget/main.js` `tick()` melakukan teardown widget setiap
`isSignedOut()` (tidak ada `aside nav button`) — persis kondisi halaman landing pre-login. FAB memang
sengaja disembunyikan di landing untuk menjaga 92-test.

**Fix:** mount sekali & pertahankan (tidak teardown saat signed-out). Widget hidup di shadow root sendiri
di `document.body`, jadi tetap **0 `aside nav button`** — DOM landing yang diassert 92-suite tak berubah.
Konteks pre-login = route `signed-out`; identitas reviewer tetap ditangkap gate widget.

**TDD:** `academy/tests/test_widget_presence.py` baru — SKIP terhadap file committed (tanpa widget),
ASSERT FAB terlihat di landing pada build **ter-inject**. Red→green terbukti:
- Baseline (main.js lama, ter-inject): `test_widget_fab_present_on_signed_out_landing` **FAIL** (FAB absen).
- Sesudah fix: **PASS**.
- Suite penuh ter-inject (runner: `build-academy-widget.sh` → serve → pytest): **94 passed** (92 asli + 2 baru).
- Default `./run-tests.sh` (file committed): tetap baseline — **92 passed + 2 skipped**.

## 3. Accreditation — kecerdasan penuh (interactivity / Fase 6)

Dibangun di **core bersama** supaya semantik tak bercabang antar shell:
- `src/widget/core/guidance.js` (murni, tanpa import) — `screenSuggestions()`, `buildTour()`,
  `gateGuidance()`. Host meng-inject peta `AREA_GUIDE` (dependency injection, tetap framework-agnostic).
- `src/widget/app.config.js` — `AREA_GUIDE`: tiap area review (9) → route layar nyata + prompt yang
  **terjawab dari sumber**; plus `SCREEN_LABELS` dipindah dari `contextAdapter.js` (satu sumber, Node-safe).
- `ReadinessWidget.jsx` — (a) chip saran **kontekstual per-layar** (ganti QUICK_PROMPTS statis),
  (b) **tur berpandu** per-area (navigasi digerakkan jawaban via prop `onNavigate` baru), (c) **gate yang
  memandu**: tombol "→ buka layar" per area belum tercentang + alasan penolakan **persis** string yang
  di-`signOff()`. `App.jsx`/`AppStandalone.jsx`: `onNavigate={navigate}` diteruskan ke widget.

**TDD `src/widget/guidance.smoke.mjs` (baru) — 44/44 hijau:** tiap AREA_GUIDE key = CHECK_AREA nyata,
tiap route ada di SCREEN_LABELS (anti-navigasi-mati), **tiap prompt → ANSWERED_FROM_SOURCE** (jaminan
"tanpa mismatch"), screenSuggestions ≤3 & tak pernah kosong, buildTour urut, gateGuidance = area belum
tercentang + reason persis. Ditambahkan ke `npm run test:widget`.

**Verifikasi end-to-end (probe headless pada artefak standalone, PRE-LOGIN — client-side penuh):**
FAB pre-login, gate identitas, saran per-layar, tur 1/9→2/9 (onNavigate jalan tanpa error), gate
menampilkan **8 tombol jump-to-screen** + alasan penolakan, **0 error JS widget**.

## 4. Collector — hardening BrokenPipe (root-caused)

**Root cause:** `_send_json` menulis body 200 ke socket yang **sudah ditutup client** (flush outbox widget
via `fetch()`/`sendBeacon` pagehide menutup socket segera setelah batch terkirim). `store.append()` sudah
mem-persist semua event SEBELUM tulis 200 → **tidak ada data hilang**; hanya traceback berisik.

**Fix:** `_send_json` menelan `BrokenPipeError`/`ConnectionResetError` diam-diam; error lain tetap dilempar.
**TDD `ops/feedback/tests/test_collector.py::SendJsonResilienceTests`:** 2 tes disconnect (red→green) +
1 tes "error asli tetap dilempar". Suite `ops/feedback/tests` **29/29**. `ah-feedback` di-restart, healthz 200.

## 5. Ringkasan gerbang (semua hijau, lokal)

| Gate | Hasil |
|---|---|
| academy injected suite (92+2) | **94 passed** |
| academy default `run-tests.sh` | 92 passed + 2 skipped |
| accreditation `test:widget` (incl. guidance 44) | GREEN |
| accreditation `test:vanilla-shell` | GREEN (12) |
| accreditation `build:standalone` | kompilasi OK (395 KB) |
| accreditation Fase 6 probe (standalone, pre-login) | GREEN, 0 error widget |
| `ops/feedback/tests` | 29/29 |

## 6. e2e React (roles/readiness-visibility) — TIDAK bisa dijalankan di sini (environmental)

Butuh backend `nexaccred-api`. Browser tak bisa menjangkaunya: API docker **127.0.0.1:3001 (IPv4)**, dev
server **[::1]:5173 (IPv6)** → `localhost:3001` resolve ke IPv6 (kosong) = "Could not reach API"; diarahkan
ke 127.0.0.1 → **CORS** menolak origin non-`localhost:5173`. Login gagal → sidebar tak muncul → semua tes
nav timeout. **Dibuktikan diff-isolation:** perubahan saya tak menyentuh login/API/nav/strip (`git diff`).
Fase-fase sebelumnya juga verifikasi lewat verify.sh + probe, bukan e2e backend. Lihat memory
`prototype-e2e-cors-ipv6-blocker`.

## 7. Deploy (tayang) & status push git

**Tayang (2026-09-19, disetujui owner):** manual publish untuk kedua app, backup live diambil lebih dulu.
- Academy: `build-academy-widget.sh` inject `main.js` (patched) → staged 673175 B → atomic swap ke
  `/var/www/prototypes/academy/index.html`; sha256 live == staged. Probe headless pada artefak tayang:
  **FAB tampil di landing pre-login, 0 `aside nav button`, 0 error widget**. Backup:
  `/var/backups/academy/academy-pre-fase6-firstaccess-20260919-053644.tar.gz`.
- Accreditation: `dist-standalone/index.standalone.html` (395168 B) → atomic swap; sha256 live == source.
  Probe headless: **saran per-layar + tur 1/9 + gate 9 tombol jump-to-screen, 0 error widget**. Backup:
  `/var/backups/accreditation/accreditation-pre-fase6-20260919-053850.tar.gz`.
- nginx tidak diubah; file di-swap atomik, www-data 644. Reviewer mungkin perlu hard-refresh (cache browser).

**Push git MASIH PENDING (butuh kredensial dari owner):**

- **GitHub connector READ-ONLY:** `create_branch` & `create_or_update_file` → `403 Resource not accessible
  by integration`. Read (get_me/get_file_contents) jalan; write tidak. Jadi push via connector **mustahil**.
- **Tidak ada kredensial push lokal:** `git push` → `could not read Username`; tak ada `gh`/`.netrc`/token.
- **Manual publish** ke `/var/www/prototypes/<app>/` di-gate classifier "Production Deploy" → butuh
  persetujuan owner eksplisit.

**Jalur bersih (disarankan):** owner menambahkan PAT ke `.env`/git credential (pola CLAUDE.md §9) → saya
`git push` (commit rename-aware yang faithful) → `ops/prototypes/refresh.sh {academy,accreditation}`
republish reproducible. Ini juga menutup utang "live ≠ git" untuk SELURUH kode widget uncommitted (Fase 0–5
+ ini), bukan hanya sesi ini.

## 8. File yang disentuh (lokal, belum ter-commit/di-push)

**Baru:** `academy/widget/main.js` (patch), `academy/tests/test_widget_presence.py`,
`accreditation/nexaccred-react/src/widget/core/guidance.js`, `.../src/widget/guidance.smoke.mjs`.
**Diubah:** `.../src/widget/ReadinessWidget.jsx`, `src/App.jsx`, `src/AppStandalone.jsx`,
`src/widget/app.config.js` (SCREEN_LABELS+AREA_GUIDE), `src/widget/contextAdapter.js` (import SCREEN_LABELS),
`package.json` (test:widget), `ops/feedback/collector.py`, `ops/feedback/tests/test_collector.py`.
Runner sementara & backup ada di scratchpad sesi; backup worktree accreditation:
`.../scratchpad/accreditation-worktree-backup.tgz`.

## 9. Rollback

Produksi SUDAH berubah (manual publish). Rollback per app: `tar xzf <backup>.tar.gz -C /tmp && atomic-swap kembali ke /var/www/prototypes/<app>/` (backup pra-deploy ada di /var/backups/<app>/). Git belum berubah. Edit lokal reversible via
`git -C <repo> checkout -- <file>` / hapus file baru, atau dari backup worktree di scratchpad.
Perubahan collector.py sudah live di service `ah-feedback` (restart) — untuk kembalikan: revert blok
try/except di `_send_json` lalu `systemctl --user restart ah-feedback`.

---

## 10. Putaran kedua — KB tidak bisa menjawab pertanyaan paling dasar (laporan owner)

**Keluhan owner (terbukti, bukan edge case):** di `/academy/`, "Ada menu/modul apa saja?" dijawab
`CLARIFICATION_NEEDED`. Data collector nyata mengonfirmasi ini norma, bukan kebetulan:
**7 CLARIFICATION_NEEDED vs 1 ANSWERED_FROM_SOURCE** dari pemakaian nyata.

**Root cause (dicari dulu, sesuai instruksi):**
1. KB academy hanya punya aturan menu **berkualifikasi persona** (`"menu operator"`, …). Kata
   **"modul"/"fitur"** tidak ada sebagai keyword di mana pun, dan tidak ada aturan ikhtisar menu.
   Pertanyaan generik skor 0 di semua aturan → di bawah `MIN_SCORE` → tanpa kandidat "Maksud Anda".
2. **Academy sama sekali tidak punya aturan per-modul**, padahal accreditation punya satu per layar
   (`gen-screen-*`). Karena itu "apa itu CPD / Question Bank / Grading Queue / Talent Search" gagal.
3. Accreditation mengidap versi ringan masalah yang sama: `gen-nav-overview` hanya punya keyword
   **frasa**, sehingga menyisipkan kata "modul" memecah frasa dan menjatuhkan skor ke 0.

**Perbaikan (di GENERATOR, bukan file hasil generate — supaya tidak pernah basi):**
- Academy `widget/gen-knowledge.mjs`: + `gen-modules-overview` (union 38 modul dari `tests/roles.py`
  + jumlah menu per persona), `gen-app-overview`, `gen-getting-started`; **satu aturan per modul**
  (siapa yang melihatnya + alur terkait, perilaku layar sengaja TIDAK dikarang → diarahkan jadi
  finding); keyword per-kata + frasa `apa itu <kata>`; keyword judul alur; keyword `persona`.
  43 → **84 aturan**.
- Accreditation `scripts/gen-knowledge.mjs`: `gen-nav-overview` + keyword `menu`/`modul`/`fitur`/
  `navigasi`; `knowledge.js` rbac-matrix + `rbac`/`rolenya`/`daftar role`.

**Hasil terukur (battery pertanyaan realistis):**

| App | Sebelum | Sesudah |
|---|---|---|
| academy | 20/32 (63%) | **32/32 (100%)** |
| accreditation | 22/24 (92%) | **24/24 (100%)** |

**Daftar gap dibuat bisa ditindaklanjuti.** Ditemukan saat menelusuri: collector menyimpan
classification/route/reviewer tapi **tidak menyimpan teks pertanyaan** — jadi "daftar lubang KB"
hanya berupa hitungan, tak bisa dipakai kerja. Diperbaiki di corong tunggal `store.js`
(`MAX_RECORDED_TEXT = 500`): `question.asked` dan `answer.given` kini membawa teks pertanyaan, dan
`bin/lib/feedback_report.py` menampilkan **daftar pertanyaan yang gagal dijawab** (per layar, diurut
frekuensi). Ini persis yang dijanjikan notice transparansi widget ("Pertanyaan … direkam").

**Gerbang:** academy KB regression baru (`widget/knowledge.smoke.mjs`) GREEN; `store.smoke.mjs`
+4 assertion GREEN; accreditation `test:widget` (knowledge + guidance 44) & `test:vanilla-shell`
GREEN; **academy injected suite 94/94**; build OK. Tayang: academy 698298 B, accreditation 395484 B,
sha256 live == yang diuji, backup `*-pre-kbcoverage-*`. Diverifikasi pada artefak TAYANG: 5 pertanyaan
nyata (termasuk keluhan owner) semuanya terjawab, 0 error JS widget.

**Keputusan owner:** LLM/Claude di belakang widget **ditunda** — perkuat KB dulu (tetap deterministik,
tanpa API key/biaya). Desain hybrid (KB otoritatif + fallback LLM berlabel `AI_SUGGESTION` lewat proxy
same-origin `/widget-ai/`) sudah dirancang dan siap bila owner mengaktifkannya; CSP tidak perlu
dilonggarkan karena proxy satu origin.
