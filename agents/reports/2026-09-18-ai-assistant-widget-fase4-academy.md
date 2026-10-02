# AI Assistant widget rollout — Fase 4 (port ke academy)

**Tanggal:** 2026-09-18 · **Host:** `31.97.67.241` (`dev-kemenkes`) · **Plan induk:**
`docs/ai-assistant-widget-rollout-plan.md` · **Lanjutan dari:**
`agents/reports/2026-09-18-ai-assistant-widget-fase3.md` · **Status:** selesai dan
tayang di `https://agents.nexoratech.co/academy/`. **92/92 test Playwright academy
hijau sebelum dan sesudah**, dan byte yang tayang identik dengan byte yang diuji.
Service-desk tetap tidak disentuh.

---

## 1. Prasyarat: python3-venv dipasang host-wide

Academy menjalankan test suite-nya lewat `./run-tests.sh` (venv + pytest +
Playwright Python). Host ini tidak punya `pip`, `venv`, `ensurepip`, `virtualenv`,
maupun `pytest` sama sekali — jadi gerbang 92-test, yang merupakan **satu-satunya
pengaman nyata** untuk fase ini, tidak bisa dijalankan tanpa memasang sesuatu.

Disimulasikan dulu (`apt-get install -s`) sebelum dieksekusi: **3 paket baru, 0
upgrade, 0 removal** — `python3.12-venv`, `python3-pip-whl`,
`python3-setuptools-whl`. Ketiganya paket pustaka pasif: tidak ada service yang
di-restart, tidak ada config yang berubah, tidak menyentuh nginx/docker/systemd.
Blast radius terhadap vhost tetangga (dev-kemenkes, dev-support, monitoring):
nihil. Baru setelah simulasi itu bersih, paketnya dipasang.

Catatan operasional: venv academy (`/opt/nexora-prototypes/src/academy/.venv`,
~200 MB dengan Chromium) adalah artefak lokal, tidak tercommit, dan aman dihapus —
`run-tests.sh` akan membangunnya ulang.

## 2. Observe dulu — dua klaim dokumen rencana diuji langsung

### 2.1 Baseline 92/92 sebelum apa pun disentuh

```
$ ./run-tests.sh -q
92 passed in 122.09s
```

### 2.2 Klaim "active nav = class" TERBUKTI SALAH

Dokumen rencana §5.1 menyatakan route aktif academy bisa dibaca dari *class* pada
`aside nav button`. Laporan Fase 3 §9 sudah menandai klaim ini tidak didukung
`tests/helpers.py` dan wajib diverifikasi live. Hasil pengukuran langsung (chromium
headless terhadap `/academy/` yang tayang, login sebagai Dinda Pramesti):

- **Setiap** `aside nav button` punya `className` **identik**
  (`flex w-full items-center gap-2.5 rounded-md px-3 py-2 text-left text-sm`).
- Tidak ada `aria-current`, tidak ada `data-*`.
- `className` **tidak berubah sama sekali** saat pindah menu.

Sinyal yang sesungguhnya ada di **inline style**, bukan class:

| | inline style |
|---|---|
| aktif | `background-color: rgba(255, 255, 255, 0.1); color: rgb(255, 255, 255)` |
| non-aktif | `background-color: transparent; color: rgba(255, 255, 255, 0.55)` |

Diverifikasi berpindah benar (Dashboard → Training Catalog). Jadi `context.js`
membaca `btn.style.backgroundColor !== 'transparent'`. Kalau klaim dokumen diikuti
mentah-mentah, widget akan **selalu** melaporkan item pertama sebagai layar aktif —
dan tidak ada test yang akan menangkapnya, karena `helpers.py` sendiri tidak pernah
membaca class. Ini persis kelas jebakan "a 200 is not a verification" di CLAUDE.md §4.

### 2.3 Risiko console-error TERBUKTI NYATA, dan memang mematikan

Laporan Fase 3 §9 butir 2 memperingatkan: respons gagal ke collector bisa muncul
sebagai console error **tingkat browser**, di luar kendali `collector.js`. Terbukti
dengan angka: injeksi pertama ke bundle asli, dijalankan terhadap test server yang
tidak punya collector →

```
36 failed, 56 passed
console.error: Failed to load resource: the server responded with a status of 501 (Unsupported method ('POST'))
```

`collector.js` menangkap semua error dan tidak pernah memanggil `console.error`
sendiri — tidak relevan: **browser yang mencatatnya**, sebelum JS melihat apa pun,
dan tidak ada try/catch yang bisa menekannya. Drill koneksi-putus Fase 1 tidak
menangkap ini karena diuji lewat nginx+collector sungguhan yang tetap membalas
normal.

**Perbaikan** (di `widget/core/collector.js`, jadi accreditation ikut dapat):
- `collectorEnabled` diteruskan host → `createStore` → `appendEvent` → `enqueue`.
  Saat `false`, outbox **tetap terisi** di localStorage (jejak tidak hilang, masih
  bisa diekspor) tapi tidak ada request yang dikirim.
- Backoff: setelah 3 kegagalan berturut-turut, flush berhenti mencoba — membatasi
  kebisingan kalau collector mati di produksi, alih-alih satu baris error tiap 5 detik.
- `main.js` academy memutuskan nilainya: `location.protocol` http(s) **dan**
  `location.pathname` diawali `/academy/`. Collector hanya ada di balik vhost nginx,
  jadi di test server, di `file://`, dan di laptop siapa pun memang tidak ada yang
  mendengarkan — mengirim ke sana dijamin gagal.

Setelah perbaikan: **92 passed**.

## 3. Yang dibangun

| File (repo academy, `widget/`) | Isi |
|---|---|
| `app.config.js` | `PROJECT_ID=deacademy`, `FEEDBACK_APP=academy`, `PROTOTYPE_VERSION=3.9.0-pilot.1`, **8 CHECK_AREAS domain academy**, QUICK_PROMPTS |
| `context.js` | Satu-satunya file yang menyentuh DOM academy: `navItems()`, `activeNavButton()` (§2.2), `isSignedOut()`, `buildContext()`, `navigateTo()` |
| `knowledge.js` | 13 intent manual: multi-tenant, consent-gating, management read-only, separation of duties, payment gates, exam eligibility, workspace switching, "ini bukan AI", audit trail, UI-only enforcement, positions, widget purpose, gate |
| `knowledge.generated.js` | 43 rule ter-generate |
| `gen-knowledge.mjs` | Generator: 7 persona + 16 Prinsip Kunci + 16 alur + entitas data model |
| `main.js` | Entry: mount, poll navigasi 1 detik, unmount saat sign-out |
| `core/` | Disinkron verbatim dari repo accreditation, tidak pernah diedit di sini |

**CHECK_AREAS academy ditulis ulang total** (8 area, bukan 9 milik accreditation),
masing-masing diikat ke Prinsip Kunci bernomor: roleAccess (P8), multiTenant (P1),
consentGating (P2), dutySeparation (P3/P10), managementReadOnly (P11/P13),
paymentGates (P14), examEligibility (P12), edgeStates. Jadi mencentang sebuah kotak
berarti mengonfirmasi aturan yang benar-benar tertulis, bukan kotak generik.

**16 Prinsip Kunci ditanam sebagai KB, bukan sekadar niat**: `gen-knowledge.mjs`
memancarkan satu rule per prinsip (`prinsip 11` → isi lengkapnya), dan KB manual
menegaskan yang paling mudah dilanggar — Management 100% read-only tanpa
pengecualian, dan dua gerbang pembayaran yang tidak boleh digabung validasinya.

**`engine.js` diekstrak ke core** (seharusnya sudah di Fase 3 — layout dokumen
rencana menyebutnya, saya melewatkannya). Tanpa ini, matcher tokenized/idf-lite
harus disalin ke academy dan dua aplikasi bisa menjawab pertanyaan sama dengan
aturan berbeda. Accreditation direfactor memakainya; ke-45 pertanyaan regresinya
tetap GREEN — bukti refactor murni.

## 4. Injeksi: append-only, di publish saja

`ops/prototypes/build-academy-widget.sh` (baru): esbuild membundel
`widget/main.js` → satu IIFE non-module (ES module tidak jalan di `file://`, dan
double-click `README-HANDOFF.md` load-bearing), lalu menyisipkannya antara
`</script>` dan `</body>` — baris 177/178. Baris 21 (412.516 karakter) tidak
disentuh.

Tiga penjaga di script itu, semuanya fail-closed: menolak kalau bundle mengandung
`</script>` (akan menutup tag lebih awal dan merusak halaman), menolak kalau penanda
`</script>\n</body>` tidak ditemukan (bentuk bundle berubah), menolak kalau sumber
sudah mengandung `nexreadiness` (double-inject).

`lsp-unified-app.html` yang tercommit **tidak pernah diubah** — 620.088 byte,
`git status` bersih. Injeksi menulis ke file temp, dan `refresh.sh` menerbitkan file
temp itu.

## 5. Verifikasi

| Gerbang | Hasil |
|---|---|
| `./run-tests.sh` sebelum | **92 passed** |
| `./run-tests.sh` terhadap build ter-injeksi | **92 passed** |
| Byte tayang vs byte teruji | **sha256 identik** (`bed3c319…`) |
| `lsp-unified-app.html` di git | 620.088 byte, tidak berubah |
| `file://` double-click | app jalan, login jalan, widget mount, **0 console error** |
| Widget fungsional (localhost) | mount hanya setelah login, identity gate, jawab dari KB academy, **gate menampilkan 8 area** (bukan 9) |
| Live `/academy/` | jawab "Management READ-ONLY" dari KB-nya sendiri, konteks persona benar, **0 console error** |
| Collector produksi | data academy mendarat di `/var/lib/nexora-feedback/academy/` — namespace ops, bukan `deacademy` |
| `ops/prototypes/verify.sh` | ALL CHECKS PASSED, termasuk neighbours untouched |
| Suite accreditation | test:widget GREEN ×5, vanilla-shell fixture GREEN |
| Gerbang workspace | 305 · 11 · 20 · 10 · 26 — semua OK |

Widget sengaja **tidak mount sebelum login**: halaman landing pra-login tetap persis
seperti yang diasumsikan test (nol `aside nav button`), dan reviewer belum punya
konteks persona untuk melekatkan finding.

## 6. Rollback

- **Live academy:** restore `/var/backups/academy/academy-pre-widget-20260918-155911.tar.gz`,
  atau — lebih bersih — revert blok `academy)` di `ops/prototypes/refresh.sh` lalu
  `refresh.sh academy`: karena bundle yang tercommit tidak pernah diubah, itu
  menerbitkan ulang file asli langsung dari git. Rollback academy secara struktural
  lebih aman daripada accreditation (yang punya state hasil upload manual).
- **Kode widget academy:** hapus `/opt/nexora-prototypes/src/academy/widget/` (untracked).
- **Core (`collectorEnabled`, `engine.js`):** ada di working tree accreditation yang
  belum ter-commit; hapus/`git checkout --` untuk kembali ke akhir Fase 3.
- **python3-venv:** `apt-get remove python3.12-venv` kalau memang diinginkan (tidak
  ada yang lain di host ini bergantung padanya).

## 7. Yang masih terbuka

1. **Kredensial push GitHub masih belum ada** — dan sekarang dampaknya dua kali
   lipat: seluruh `widget/` academy (app.config, context, knowledge, main,
   generator) **hanya ada sebagai file untracked lokal**, sama seperti perubahan
   widget accreditation. `refresh.sh`'s `pull()` melakukan `git reset --hard`, yang
   tidak menghapus file untracked — jadi ini selamat dari refresh, tapi **tidak
   selamat dari clone ulang repo**. Begitu token ada di `.env`: commit + push kedua
   repo ke `dev`, lalu `refresh.sh` sekali untuk membuktikan build dari git
   menghasilkan byte yang sama.
2. **Fase 5 (interaktivitas)** belum dikerjakan: tur berpandu, saran kontekstual per
   layar, checklist gate yang memandu. Adapter navigasinya sudah ada
   (`navigateTo()` academy, `onNavigate` accreditation), jadi pondasinya siap.
3. **Service-desk tetap pending** sesuai keputusan owner. `sync-widget.sh` masih
   menolaknya secara eksplisit (exit 2) sampai pekerjaan itu dijadwalkan.
4. Poll 1 detik di `main.js` adalah kompromi sadar: bundle academy tertutup, tidak
   ada event navigasi yang bisa di-subscribe. Kalau nanti ada cara yang lebih murah
   (mis. bundle mengekspos sesuatu), itu perbaikan yang layak.
