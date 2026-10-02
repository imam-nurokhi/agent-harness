# AI Assistant Widget — Academy First-Access, Accreditation Intelligence & KB Coverage (2026-09-19)

> **Status:** LIVE & terverifikasi di kedua app. sha256 yang disajikan URL publik **identik** dengan build yang diuji.
> **Host:** `31.97.67.241` (`dev-kemenkes`) · **Metode:** OODA + TDD, root-cause sebelum fix · **Service-desk:** tidak disentuh (sesuai owner).
> **Laporan teknis (VPS):** `agents/reports/2026-09-19-widget-fase6-academy-firstaccess-collector.md`
> **Belum ter-push ke git** — lihat §7.

## 1. Academy — AI Assistant muncul dari akses pertama

`agents.nexoratech.co/academy/` kini menampilkan tombol **AI Assistant** sejak halaman landing (sebelum login), bukan hanya setelah login.

- **Root cause:** `widget/main.js` sengaja meng-unmount widget setiap `isSignedOut()` — persis kondisi halaman landing.
- **Fix:** mount sekali & dipertahankan. Widget hidup di shadow root sendiri → tetap **0** entri navigasi tambahan, DOM landing tak berubah.
- **Gate:** tes baru `tests/test_widget_presence.py` (skip pada file committed, assert FAB pada build ter-inject). Suite ter-inject **94/94**; `run-tests.sh` default tetap 92 lulus + 2 skip.

## 2. Accreditation — kecerdasan penuh (interaktivitas)

- **Saran kontekstual per-layar** — chip pertanyaan relevan dengan layar yang sedang direview.
- **Tur berpandu** (tab Ask → `Mulai tur berpandu`) — menyusuri 9 area review: buka layar yang tepat → ajukan pertanyaan area itu → centang → lanjut (1/9 … 9/9).
- **Gate yang memandu** (tab Readiness) — tombol **buka layar** per area belum tercentang + alasan penolakan sign-off yang persis (`coverage N%, M open blocker(s)`).
- **Jaminan tanpa mismatch:** dibangun di inti bersama `widget/core/guidance.js` + peta `AREA_GUIDE`; gerbang `guidance.smoke.mjs` **44/44** membuktikan tiap route nyata dan **tiap prompt terjawab dari sumber**.

## 3. KB coverage — temuan owner: asisten tak bisa jawab hal paling dasar

Owner bertanya "Ada menu/modul apa saja?" di `/academy/` → `CLARIFICATION_NEEDED`. Data collector membenarkan ini **norma, bukan edge case**: **7 CLARIFICATION_NEEDED vs 1 ANSWERED** dari pemakaian nyata.

**Root cause (struktural):**

1. Academy **tidak punya aturan per-modul sama sekali**, padahal accreditation punya satu per layar (`gen-screen-*`). Karena itu "apa itu CPD / Question Bank / Grading Queue / Talent Search" gagal semua.
2. Kata **"modul"/"fitur"** tidak ada sebagai keyword di mana pun; aturan menu academy semuanya **berkualifikasi persona** (`"menu operator"`).
3. Accreditation kena versi ringannya: `gen-nav-overview` hanya punya keyword **frasa**, jadi menyisipkan kata "modul" memecah frasa → skor 0.

**Perbaikan di GENERATOR** (bukan file hasil generate, supaya tidak pernah basi): ikhtisar 38 modul (union nav semua persona), **satu aturan per modul** (siapa yang melihat + alur terkait; perilaku layar sengaja TIDAK dikarang → diarahkan jadi finding), app-overview, getting-started, keyword per-kata + frasa `apa itu <kata>`, keyword judul alur. Academy **43 → 84 aturan**.

**Hasil terukur (battery pertanyaan realistis):**

| App | Sebelum | Sesudah |
| --- | --- | --- |
| academy | 20/32 (63%) | **32/32 (100%)** |
| accreditation | 22/24 (92%) | **24/24 (100%)** |

## 4. Daftar gap KB dibuat bisa ditindaklanjuti

Ditemukan saat menelusuri: collector menyimpan classification/route/reviewer tapi **tidak menyimpan teks pertanyaan** — jadi "daftar lubang KB" hanya berupa hitungan, tak bisa dipakai kerja.

Diperbaiki di corong tunggal `store.js` (`MAX_RECORDED_TEXT = 500`): `question.asked` dan `answer.given` kini membawa teks pertanyaan — persis yang dijanjikan notice transparansi widget ("Pertanyaan … direkam"). `bin/lib/feedback_report.py` (`ah feedback`) kini menampilkan **daftar pertanyaan yang gagal dijawab**, per layar, diurut frekuensi → itulah backlog KB berikutnya.

## 5. Collector — hardening

`_send_json` menelan `BrokenPipeError`/`ConnectionResetError` (client menutup koneksi setelah data tersimpan → lossless; sebelumnya hanya traceback berisik di journal). Tes **29/29**, `ah-feedback` restart, healthz 200.

## 6. Verifikasi

| Gate | Hasil |
| --- | --- |
| academy injected suite | **94/94** |
| academy default run-tests | 92 lulus + 2 skip |
| academy KB regression (baru) | GREEN |
| accreditation test:widget (incl. guidance 44) | GREEN |
| accreditation test:vanilla-shell | GREEN (12) |
| core store.smoke (+4 assertion gap-capture) | GREEN |
| ops/feedback/tests | 29/29 |
| `ops/prototypes/verify.sh` (URL publik) | **ALL CHECKS PASSED** |

**Bukti live (fetch ke URL publik, bukan file disk):** `/academy/` 698.298 B dan `/accreditation/` 395.484 B — **sha256 publik == sha256 build yang diuji** untuk keduanya; penanda fitur baru ada di bytes yang disajikan. Deploy manual (disetujui owner), backup pra-deploy di `/var/backups/{academy,accreditation}/`.

*Catatan: e2e React (roles/readiness-visibility) tidak bisa dijalankan di lingkungan ini — API IPv4-only vs browser IPv6 localhost + CORS. Murni isu environment, bukan regresi kode; diverifikasi lewat probe pada artefak standalone.*

## 7. Catatan push (perlu tindakan owner)

GitHub connector di sesi ini **read-only** (`create_branch` & `create_or_update_file` → 403) dan tidak ada kredensial push lokal (`git push` → could not read Username). Jadi seluruh kode widget (Fase 0–5 + pekerjaan ini) **masih uncommitted** dan situs belum reproducible dari git.

**Untuk menutup:** owner menambahkan Personal Access Token ke `.env` (pola CLAUDE.md §9, jangan kirim via chat) → agent commit + push ke `dev` → `refresh.sh` republish reproducible. Sampai itu **jangan jalankan `refresh.sh`** untuk kedua app — ia `git reset --hard` ke `origin/dev` dan akan menghapus kerja uncommitted.

## 8. Keputusan owner — LLM di belakang widget

**Ditunda.** Owner memilih perkuat KB dulu: tetap deterministik, tanpa API key/biaya. Desain hybrid sudah siap bila diaktifkan: KB tetap otoritatif + bersitasi; pertanyaan di luar KB jatuh ke Claude lewat proxy **same-origin** `/widget-ai/`, dilabeli `AI_SUGGESTION`, tetap tercatat sebagai gap. Catatan penting: keberatan CSP di rollout plan **tidak berlaku** untuk desain ini — proxy satu origin tidak butuh pelonggaran CSP, dan itu satu-satunya tempat aman untuk API key.
