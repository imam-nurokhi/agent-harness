# AI Assistant widget rollout — Fase 0 (build reproducibility) + Fase 1 (feedback collector)

**Tanggal:** 2026-09-18 · **Host:** `31.97.67.241` (`dev-kemenkes`) · **Plan induk:**
`docs/ai-assistant-widget-rollout-plan.md` · **Status:** Fase 0 & 1 selesai dan
terverifikasi. Fase 2–6 belum dikerjakan. **Service-desk sengaja tidak disentuh sama
sekali** (keputusan owner: accreditation dulu, lalu academy; service-desk pending).

---

## 0. Eksplorasi sebelum eksekusi — apa yang berubah dari asumsi dokumen rencana

Tiga sub-agent Explore memverifikasi klaim `docs/ai-assistant-widget-rollout-plan.md`
langsung terhadap disk sebelum eksekusi dimulai. Koreksi yang ditemukan (semuanya kecil,
tidak mengubah arsitektur rencana):

- `ReadinessWidget.jsx` sebenarnya **411 baris**, bukan 386.
- `src/data/roles.js` sebenarnya **160 baris**, bukan 155, dan punya **7** `{group}`
  marker eksplisit, bukan 8 (`dashboard`/`tasks` ada di luar grup mana pun).
- Direktori widget punya **10 file**, bukan 9 — dokumen rencana melewatkan `version.js`
  (12 baris, `PROJECT_ID`/`PROTOTYPE_VERSION`/`WIDGET_VERSION`).
- Enam dokumen sumber kebenaran (`00-README-...md` dst.) ada di **root repo**
  `accreditation`, bukan di `nexaccred-react/docs/` (path itu tidak ada).
- Klaim "active route = class pada `aside nav button`" di academy **tidak** didukung
  `tests/helpers.py` — perlu verifikasi browser langsung sebelum Fase 4/5 membangun di
  atasnya (dicatat, belum diverifikasi karena Fase 4/5 belum dikerjakan sesi ini).
- Local clone `accreditation` mengklaim "up to date with origin/dev" padahal
  `origin/dev` tracking ref-nya sendiri beku di `afbc668` — perlu `git fetch` langsung
  dari GitHub API untuk tahu tip sebenarnya (`dcb8aee`).

---

## 1. Fase 0 — pulihkan jalur build accreditation

### 1.1 Baseline sebelum disentuh

```
GET /accreditation/ (dengan basic auth)  →  365.425 B, mtime 2026-09-18 05:06:19
sha256 63451dd7...ee6bb1
```

Headless probe (Playwright, kredensial dari `/root/prototypes-basic-auth.txt`):
`fabCount=1`, `window.NexReadiness.version=0.1.0`, `PROJECT_ID=nexaccred`,
`PROTOTYPE_VERSION=1.0.0-pilot.1`, `window.RequirementReadiness` punya kelima method,
**0 console error, 0 page error** — persis baseline §2 dokumen rencana.

Backup manual dibuat **sebelum** apa pun disentuh (lihat §1.4 kenapa ini wajib):
`/var/backups/accreditation/accreditation-pre-refresh-20260918-112142.tar.gz`
(107.766 B, sha256 index.html sama dengan live).

### 1.2 `git ls-remote` — ground truth independen

```
$ git ls-remote https://github.com/NexoraTechTeam/accreditation.git dev
dcb8aee0506d3abd94e11c2f6a0646743093abf2  refs/heads/dev
```

Local clone `/opt/nexora-prototypes/src/accreditation` sebelum ini: `git status`
bilang "up to date with origin/dev" tapi HEAD lokal masih `afbc668` — tracking ref-nya
sendiri tidak pernah di-fetch ulang sejak clone awal. `ops/prototypes/refresh.sh`'s
`pull()` sendiri sudah benar (selalu `git fetch --depth 1 origin dev` +
`reset --hard FETCH_HEAD` tiap jalan, tidak bergantung pada ref lokal yang basi) — jadi
ini bukan bug refresh.sh, hanya bukti bahwa `git status` di clone ini tidak bisa
dipercaya sebagai oracle.

### 1.3 Bug ditemukan & diperbaiki: `ops/prototypes/refresh.sh`

`refresh.sh accreditation` (invoke pertama) **gagal** di langkah terakhir:

```
== verify
./ops/prototypes/refresh.sh: line 97: /opt/nexora-prototypes/src/accreditation/nexaccred-react/ops/prototypes/verify.sh: No such file or directory
```

Sebab: script `cd` ke `$SRC/accreditation/nexaccred-react` di tengah eksekusi (untuk
`npm install`/`build:standalone`), lalu di baris terakhir memanggil
`exec "$(dirname "$0")/verify.sh"` — path itu dihitung relatif terhadap `$0` (path
saat script dipanggil), bukan terhadap lokasi script sebenarnya, jadi resolve salah
begitu cwd berubah.

**Perbaikan** (`ops/prototypes/refresh.sh`): tambah
`SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"` di awal, ganti baris
terakhir jadi `exec "$SCRIPT_DIR/verify.sh"`. Diverifikasi dengan menjalankan ulang
`./ops/prototypes/refresh.sh accreditation` dari `~/AI-Workspace` — build + publish +
verify semua sukses dalam satu invoke.

### 1.4 Hasil: build sekarang **byte-identik** dengan yang tayang

```
$ sha256sum /var/www/prototypes/accreditation/index.html
63451dd75879f19d51d4d39e3b18c0fa8f3a9771cf0d9bbebb0b7e3a07ee6bb1   (SAMA dengan baseline §1.1)
```

Ini membuktikan `dev@dcb8aee` + `npm run build:standalone` memang mereproduksi persis
apa yang tayang — jalur reproducible **pulih**, bukan cuma diasumsikan pulih.

Catatan penting untuk fase selanjutnya: `refresh.sh`'s `publish()` **tidak menyimpan
backup** — `rm -rf "$dest.old"` di akhir menghapus versi lama permanen begitu swap
sukses. Backup manual sebelum tiap `refresh.sh`/publish manual adalah langkah wajib,
bukan opsional, sampai `publish()` sendiri diperbaiki (belum dikerjakan sesi ini).

### 1.5 `docs/widget-readiness-ai-assistant.md` — direkonstruksi

Dikutip oleh 3 knowledge intent (`gate`, `evidence-model`, `pilot`) dan oleh 3 file
kode (`store.js` §6, `knowledge.js` §5, `contextAdapter.js` §4) tapi tidak pernah ada
di mana pun (repo, GitHub, filesystem host, `~/AI-Workspace/docs/`) — dikonfirmasi oleh
Explore agent sebelum ditulis. Direkonstruksi dari `WIDGET-README.md` + pembacaan
langsung `knowledge.js`/`store.js`/`contextAdapter.js`, dengan section numbering (§1–§8)
yang persis mencocokkan sitasi `§4`/`§5`/`§6` yang sudah tertanam di kode. File baru:
`docs/widget-readiness-ai-assistant.md`.

### 1.6 Verifikasi Fase 0

```
$ ./ops/prototypes/verify.sh
ALL CHECKS PASSED   (semua 3 app + isolation + "neighbours untouched": Command Center,
                     n8n, academy-test — semuanya masih seperti semula)
```

**Rollback Fase 0:** restore
`/var/backups/accreditation/accreditation-pre-refresh-20260918-112142.tar.gz` ke
`/var/www/prototypes/accreditation/`; revert perubahan `refresh.sh` (2 baris) kalau
perlu — keduanya independen dan reversibel terpisah.

---

## 2. Fase 1 — Feedback collector: "tersimpan, tidak boleh hilang, reviewer aware"

### 2.1 Server: `ops/feedback/collector.py`

TDD: test suite (`ops/feedback/tests/test_collector.py`, 26 test) ditulis **sebelum**
`collector.py` ada — RED dikonfirmasi (`ModuleNotFoundError: No module named
'collector'`) sebelum implementasi ditulis, GREEN setelahnya (26/26, termasuk satu
putaran perbaikan untuk `GET /collect` yang semula 404 alih-alih 405).

Desain: `ThreadingHTTPServer` stdlib murni di `127.0.0.1:7788`. `POST /collect` +
`GET /healthz`. Validasi ketat: field top-level & per-event di-allowlist (field tak
dikenal ditolak `400`), `app` harus match `^[a-z][a-z0-9_-]{0,31}$`, body >64KB ditolak
`413`, batch >50 event ditolak, `eventId` duplikat di-skip (bukan ditolak keras — retry
memang diharapkan), dedup **dimuat ulang dari file NDJSON saat startup** (bukan cuma
in-memory) supaya restart proses tidak melupakan apa yang sudah tertulis. `remote_user`
diambil dari header `X-Remote-User` (diisi nginx dari `$remote_user`, **bukan** dari
body klien), `received_at` di-generate server (`datetime.now(timezone.utc)`), keduanya
tidak bisa dipalsukan klien — divalidasi eksplisit: mengirim field `receivedAt` di body
event ditolak sebagai field tak dikenal.

Rate limit: fixed-window per IP (`X-Real-IP` dari nginx, fallback socket addr),
default 60/menit.

### 2.2 Systemd unit: `ah-feedback`

`ops/feedback/ah-feedback.service`, disalin persis pola hardening `ah-dashboard.service`
(`EnvironmentFile`, `NoNewPrivileges=true`, `PrivateTmp=true`, `ProtectSystem=full`,
`UMask=0077`, `Restart=on-failure`) — **bukan** pola `ops/n8n/nexora-operations-backup.service`
(root system unit, tanpa hardening sama sekali). Data dir
`/var/lib/nexora-feedback/` dibuat `ahagent:ahagent 0750`. Diaktifkan via
`systemctl --user enable --now ah-feedback`; dikonfirmasi live:
`NoNewPrivileges=yes PrivateTmp=yes ProtectSystem=full UMask=0077`.

### 2.3 nginx: satu blok baru, aditif

`ops/nginx/agents.nexoratech.co.conf` — `location ^~ /widget-feedback/` baru di dalam
blok "Prototype review surfaces" yang sudah ada. TDD: 6 test baru
(`WidgetFeedbackLocationTests` di `ops/nginx/tests/test_validate_vhost.py`) ditulis
dulu — RED (6 gagal, "no /widget-feedback/ location found") sebelum blok ditulis,
GREEN sesudahnya (20/20 total, 14 test lama tetap hijau tanpa perubahan). Blok baru
merestate keenam header (bukan warisan — `add_header` di satu location mengganti
seluruh set warisan, bukan menambah), pakai `.prototypes.htpasswd` yang sama, dan
menambah `proxy_set_header X-Remote-User $remote_user;` +
`proxy_set_header X-Real-IP $remote_addr;` supaya collector bisa memercayai kedua
field itu.

`python3 ops/nginx/validate_vhost.py ...` → OK. `diff` terhadap
`/etc/nginx/sites-available/agents.nexoratech.co` sebelum copy menunjukkan **hanya**
blok baru yang ditambahkan (25 baris), tiga blok `/academy/`, `/accreditation/`,
`/servicedesk/` byte-identik dengan sebelumnya. `nginx -t` bersih →
`systemctl reload nginx` (bukan restart) → `verify.sh` tetap ALL CHECKS PASSED,
termasuk probe baru `== /widget-feedback/` (401 tanpa kredensial, 200 dengan).

### 2.4 Widget-side: `collector.js` + `identity.js` + hook di `store.js`

Repo: `accreditation` (`nexaccred-react/src/widget/`). File baru:
`collector.js`, `identity.js`, `collector.smoke.mjs`. Diubah: `store.js` (satu baris
hook di funnel tunggal `appendEvent()`), `ReadinessWidget.jsx` (identity gate wajib +
notice transparansi permanen + tab baru "Jejak saya"), `version.js` (tambah
`FEEDBACK_APP`), `package.json` (script `test:widget` baru).

**Identity gate** (`identity.js` + komponen `IdentityGate` di `ReadinessWidget.jsx`):
nama+email wajib diisi sekali sebelum tab Ask/Findings/Readiness bisa dipakai;
disimpan `nexreadiness:<project>:identity` + `deviceId` acak. **Terpisah** dari persona
demo (`context.reviewer`) — keduanya distempel ke tiap event: `actor` (persona) di
level event, `payload.reviewer` (identitas asli) diisi `collector.js` saat enqueue.

**Transparansi** — baris permanen di footer panel (bukan toast sekali muncul) + tab
"Jejak saya" yang menampilkan identitas tercatat, daftar event sesi ini, dan status
outbox ("N jejak menunggu terkirim" / "semua jejak sudah terkirim", di-refresh tiap 3
detik).

**Collector client** (`collector.js`): antrean `localStorage`
(`nexreadiness:<project>:outbox`), flush tiap 5 detik + `sendBeacon` saat
`pagehide`/`visibilitychange:hidden`. **Tidak pernah `console.error` atau throw** —
semua kegagalan jaringan tertangkap diam-diam, outbox tetap utuh untuk dicoba lagi.
Ini disengaja untuk akademi (92 test Playwright gagal total kalau ada satu
`console.error`), diverifikasi sekarang di accreditation supaya bukan asumsi saat
akademi digarap nanti.

**Bug ditemukan & diperbaiki:** `collector.js` semula mengirim `app: project` —
`project` adalah `PROJECT_ID` widget (`"nexaccred"`, namespace localStorage/context),
**bukan** nama app level-ops (`"accreditation"`, yang dipakai nginx/`refresh.sh`/`ah
feedback`). Data pertama kali mendarat di `/var/lib/nexora-feedback/nexaccred/` alih-
alih `.../accreditation/` — ketahuan dari probe end-to-end langsung terhadap
filesystem, bukan dari log. Perbaikan: `version.js` menambah konstanta
`FEEDBACK_APP = 'accreditation'` terpisah dari `PROJECT_ID`, `collector.js` mengirim
`app: FEEDBACK_APP`. Dibangun ulang & diterbitkan ulang, diverifikasi lagi — data
sekarang benar di `.../accreditation/`.

**TDD widget-side:**
`node src/widget/store.smoke.mjs` — 10/10 PASS (tidak berubah oleh perubahan ini,
membuktikan hook di `appendEvent` tidak mengubah semantik gate/sign-off).
`node src/widget/collector.smoke.mjs` (baru, shim `window`/`fetch`/`localStorage`
minimal tanpa browser sungguhan) — 6/6 PASS: outbox menahan event saat "server" gagal,
tidak kehilangan satu pun, identitas asli terlampir terpisah dari `actor` (persona),
outbox kosong lagi begitu "server" pulih, flush kosong tidak pernah throw. Diwire ke
`npm run test:widget`.

### 2.5 Kredensial GitHub tidak ada — publish manual, bukan lewat `refresh.sh`

Sesi ini **tidak punya kredensial push** ke `NexoraTechTeam/accreditation` (dicek: tidak
ada `gh` auth, `~/.netrc`, SSH key, atau token di `.env` — konsisten dengan CLAUDE.md
§8 butir 3 yang sudah menandai akses GitHub sebagai "blocked"). Karena
`refresh.sh`'s `pull()` selalu `git reset --hard` ke `origin/dev`, perubahan widget-
side (§2.4) hanya ada sebagai working-tree lokal yang belum di-commit/push — `refresh.sh
accreditation` akan **menghapusnya** kalau dijalankan sekarang.

**Keputusan (owner, diminta eksplisit):** publish manual satu kali, bypass git,
sambil mencatat trade-off-nya secara eksplisit di sini — bukan solusi permanen.

Prosedur yang dipakai (meniru persis `publish()` di `refresh.sh`):
```
1. npm run build:standalone   (dari working tree lokal, dcb8aee + perubahan widget)
2. backup live dulu → /var/backups/accreditation/accreditation-pre-widget-feedback-20260918-134839.tar.gz
3. copy dist-standalone/index.standalone.html → /var/www/prototypes/accreditation.new/index.html
4. chown www-data:www-data, chmod 755 dir / 644 file
5. swap atomik: rm .old → mv current .old → mv .new current → rm .old
```
Dijalankan **dua kali** — sekali sebelum bug `FEEDBACK_APP` (§2.4) ditemukan, sekali
lagi setelah diperbaiki, masing-masing dengan backup live tersendiri sebelum overwrite.

**Konsekuensi yang harus diketahui owner:** `/accreditation/` yang tayang sekarang
**bukan** hasil `refresh.sh` dan **tidak bisa direproduksi dari git** — persis defect
yang Fase 0 baru saja perbaiki, terjadi lagi karena keterbatasan kredensial, bukan
karena proses manual disengaja lagi. File widget-side (`collector.js`, `identity.js`,
hook `store.js`, UI `ReadinessWidget.jsx`, `version.js`, `package.json`) ada sebagai
*working tree lokal tidak ter-commit* di `/opt/nexora-prototypes/src/accreditation`.
**Begitu token push GitHub tersedia** (taruh di `.env`, lihat CLAUDE.md §9), langkah
rekonsiliasi: commit perubahan ke branch `dev`, push, lalu `refresh.sh accreditation`
sekali untuk memverifikasi build dari git menghasilkan byte yang sama dengan yang
tayang sekarang — itulah yang akan memulihkan reproducibility untuk kedua kalinya.

### 2.6 `ah feedback` — ringkasan baca untuk owner

`bin/lib/feedback_report.py` (pure functions, testable tanpa server) + `bin/lib/feedback.sh`
+ wiring di `bin/ah`. TDD: `tests/test_feedback_report.py` (14 test) ditulis mengikuti
konvensi `tests/test_weekly_report.py` (import langsung dari `bin/lib` via
`sys.path.insert`). Yang disurvei: pertanyaan per reviewer, **jumlah
`CLARIFICATION_NEEDED`** (ini yang jadi "daftar lubang KB" — poin utama fitur ini,
bukan sekadar hitungan pertanyaan), finding tercatat, sign-off terakhir per app.
Diverifikasi end-to-end: kirim event nyata lewat `https://.../widget-feedback/collect`,
`ah feedback accreditation` menampilkannya benar dengan `CLARIFICATION_NEEDED` ter-
hitung.

`bin/feedback_digest.py` — digest mingguan read-only ke Telegram, pola persis
`bin/sprint_reminder.py` (stdlib, `env()` fallback baca `.env` langsung karena
`state.WORKSPACE` bug yang sama). Timer baru (tidak tercommit di repo, sama seperti
`ah-sprint-weekly` — hidup di `~/.config/systemd/user/` saja):
`ah-feedback-digest.timer`, **Fri 07:30 WIB** (30 menit setelah `ah-sprint-weekly`,
alasan sama: hindari dua ping bertabrakan). Diuji `build_message()` langsung
(bukan kirim sungguhan ke Telegram — tidak perlu mengirim pesan uji ke chat owner
untuk memverifikasi format).

### 2.7 Data uji dibersihkan

Semua NDJSON hasil probe manual (`_probe_widget.mjs`, `_probe_e2e.mjs`,
`_probe_outage.mjs` — dihapus setelah dipakai) dan curl manual dihapus dari
`/var/lib/nexora-feedback/` sebelum sesi berakhir — dikonfirmasi kosong.

---

## 3. Verifikasi akhir sesi ini

```
$ python3 -m unittest discover -s tests              → 305 tests, OK  (291 lama + 14 baru)
$ python3 -m unittest discover -s ops/harness/tests   → 11 tests, OK  (tidak berubah)
$ python3 -m unittest discover -s ops/nginx/tests     → 20 tests, OK  (14 lama + 6 baru)
$ python3 -m unittest discover -s ops/n8n/tests       → 10 tests, OK  (tidak berubah)
$ python3 -m unittest discover -s ops/feedback/tests  → 26 tests, OK  (baru)
$ ./ops/prototypes/verify.sh                          → ALL CHECKS PASSED
```

**Drill koneksi putus (syarat wajib Fase 1):** widget dibuka live, 3 pertanyaan diajukan
sambil `ah-feedback` **dimatikan** (`systemctl --user stop`), lalu dinyalakan lagi.
Hasil: **0 console error selama outage maupun setelah restart**, dan ketiga pertanyaan
tersebut **semuanya** muncul di NDJSON setelah restart — nol jejak hilang.

**Isolasi/neighbours (setiap fase):** Command Center (`/`) tetap 401, n8n
(`/automation/`) tetap 401, `academy-test.nexoratech.co` tetap 200, kredensial
prototipe tetap tidak bisa membuka `/`. Ketiga blok location `/academy/`,
`/accreditation/`, `/servicedesk/` di `agents.nexoratech.co.conf` byte-identik
sebelum/sesudah — dikonfirmasi lewat `diff` dan lewat test
`test_the_three_prototype_blocks_are_untouched`.

---

## 4. Rollback (ringkas, per komponen)

| Komponen | Rollback |
|---|---|
| `refresh.sh` (fix path) | revert 2 baris; independen dari perubahan lain |
| Build accreditation (Fase 0) | restore `accreditation-pre-refresh-20260918-112142.tar.gz` |
| Publish manual widget (§2.5) | restore `accreditation-pre-widget-feedback-20260918-134839.tar.gz` (state SEBELUM widget-side ditambahkan, SETELAH Fase 0) |
| `ah-feedback` service | `systemctl --user stop ah-feedback`; data di `/var/lib/nexora-feedback/` tetap |
| nginx `/widget-feedback/` | hapus blok dari `agents.nexoratech.co.conf`, copy, `nginx -t`, reload |
| `ah-feedback-digest.timer` | `systemctl --user disable --now ah-feedback-digest.timer` |
| Widget-side JS (belum ter-push) | hapus/`git checkout --` di `/opt/nexora-prototypes/src/accreditation` — tidak ada commit yang perlu di-revert karena belum pernah di-commit |

---

## 5. Yang belum dikerjakan (lanjutan sesi berikut)

- **Fase 2** — ganti matcher `String.includes` (rapuh, terbukti oleh `dcb8aee`) dengan
  tokenisasi + skor idf-ringan + top-3 "maksud Anda"; `gen-knowledge.mjs` untuk KB
  turunan-kode; perbaiki 2 route mati (`assessment-prep` butuh screen baru,
  `ab-register` cuma butuh 1 baris `case`); keputusan owner soal drift RBAC
  (Staff 25 vs 24, Impartiality 5 vs 11).
- **Fase 3** — ekstrak `widget/core/*` bersama, divalidasi lewat fixture sintetis
  dulu sebelum menyentuh academy (karena service-desk sengaja dilewati sebagai
  "canary" — lihat risk register sesi perencanaan).
- **Fase 4** (academy) — verifikasi live browser dulu untuk klaim "active nav = class"
  yang tidak terbukti di `tests/helpers.py`; injeksi inkremental, gerbang 92/92 test
  Playwright di tiap langkah.
- **Fase 5** — interaktivitas bersama (tur, saran kontekstual, checklist gate) untuk
  accreditation + academy saja.
- **Kredensial push GitHub** — blocker nyata untuk semua fase widget-side berikutnya,
  bukan hanya accreditation. Sampai token ada di `.env`, setiap perubahan widget-side
  akan menghadapi pilihan yang sama seperti §2.5.
