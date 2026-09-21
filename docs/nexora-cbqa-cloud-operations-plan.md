# Rencana Cloud Operations Workspace Nexora / CBQA

## Status dan tujuan

Dokumen ini merangkum arah solusi hasil analisa dan diskusi untuk mengurangi pekerjaan manual di GitHub, NEXONE, Slack, Notion, dokumentasi, serta monitoring operasional. Targetnya adalah satu control plane yang dapat diakses melalui dashboard web, Telegram, dan Slack tanpa laptop harus selalu menyala.

Prioritas awal adalah fondasi operasional dan governance tanpa ketergantungan pada AI API. AI dapat ditambahkan kemudian setelah budget, data classification, dan kontrol akses stabil.

> **Infrastructure decision (2026-09-17):** untuk menunda biaya VM baru, n8n
> Community Edition akan berjalan sebagai Docker stack yang terisolasi pada
> `31.97.67.241`. Ia memakai database, volume, secret, network, dan listener
> loopback sendiri; tidak boleh berbagi credential atau mengubah container
> aplikasi existing. Floot tetap menjadi pembanding terpisah, bukan executor
> atau penyimpan data operasional sensitif.

## Implementasi historis

**Tanggal:** 2026-09-17

- Command Center Agent Harness sudah tersedia di `https://agents.nexoratech.co`.
- Dashboard berjalan sebagai systemd user service `ah-dashboard` milik `ahagent`, bind hanya ke `127.0.0.1:7777`, dan otomatis restart bila gagal.
- nginx hanya meneruskan HTTPS untuk hostname tersebut ke loopback dashboard. Port `7777` tidak dapat diakses melalui IP publik.
- TLS Let's Encrypt untuk `agents.nexoratech.co` telah aktif dan renewal Certbot terjadwal.
- Seluruh dashboard dan API dilindungi HTTP Basic Auth dengan credential unik yang tidak memakai ulang credential SSH. Initial credential disimpan root-only di VPS dan harus dirotasi setelah owner berhasil masuk.
- Header `nosniff`, anti-framing, referrer policy, permissions policy, HSTS untuk hostname, dan CSP aktif pada vhost baru.
- Vhost `agents` memiliki limit request dan koneksi per-IP; method selain `GET`, `HEAD`, dan `POST` ditolak.
- Helper root-only `/usr/local/sbin/rotate-agents-dashboard-password` tersedia untuk melakukan rotasi interaktif dan menghapus credential bootstrap setelahnya.
- Regression harness yang menangani judul task dengan karakter `&`, backslash, dan Unicode telah diperbaiki. Suite VPS: 183 test lulus.

Fase berikutnya tetap membutuhkan inventory integrasi dan credential terpisah yang scoped untuk GitHub, Slack, Notion, NEXONE, serta monitoring. Tidak ada integrasi AI, n8n workflow, atau credential production baru yang diaktifkan pada deployment dashboard ini.

### Deployment n8n (2026-09-17)

- n8n Community 2.39.6 dan PostgreSQL 17 berjalan sebagai project Docker `nexora-operations` di `31.97.67.241`, memakai network serta volume sendiri.
- n8n hanya bind ke `127.0.0.1:5678`. Nginx merutekan `https://agents.nexoratech.co/automation/` di balik TLS, Basic Auth, rate limit, dan header keamanan yang sudah ada.
- Konfigurasi menonaktifkan community packages, public API, templates, telemetry, version notifications, serta node Code, shell, SSH, dan filesystem. SSRF protection aktif.
- Verifikasi deployment: konfigurasi Compose valid; PostgreSQL healthy; UI lokal dan melalui proxy authenticated merespons `200`; akses anonymous mendapat `401`; port 5678 tidak terbuka ke publik; audit n8n tidak menemukan workflow, credential, atau node komunitas.
- Instance belum memiliki owner n8n atau workflow aktif. Pembuatan owner dilakukan melalui UI setelah autentikasi reverse-proxy, tanpa mengirim credential ke chat. Backup lokal harian root-only dengan retensi 14 hari telah dipasang untuk database, volume n8n, dan konfigurasi stack. Backup off-host, credential integrasi, dan workflow baru tetap menunggu scope serta approval eksplisit.
- Command Center source contains a read-only Operations panel: it probes n8n only through loopback, checks the backup timer, and presents approved links. NEXONE and Slack remain explicitly `not-configured` until their authorization and scopes are reviewed.

### Handoff state: cloud control surface (2026-09-17)

This is the authoritative continuation checklist for the work completed in this
phase. It records only state that was deployed and verified; it is not a claim
that the target integrations are already operational.

| Surface | Verified state | Access / result |
|---|---|---|
| Command Center | Live behind HTTPS, Basic Auth, rate limiting, and headers | `https://agents.nexoratech.co` |
| n8n UI | Live behind the same host protection, loopback-only upstream | `https://agents.nexoratech.co/automation/` |
| n8n workflows | **None active**; no n8n credential, webhook, AI provider, or community node is configured | No automatic report, notification, ticket, or deploy is produced by n8n yet |
| Backup | Isolated n8n/PostgreSQL backup timer active, local retention 14 days | Recovery source exists locally; off-host recovery is still pending |
| Telegram bot | Existing long-polling service active; command menu updated | Owner-paired chats only; no new polling process was introduced |

#### Telegram commands now deployed

The following commands were added to the existing paired-chat bot. They are
read-only or explanatory and never invoke n8n, shell, SSH, deployment, or a
production credential.

| Command | Current result | Security boundary |
|---|---|---|
| `/ops` | n8n loopback status, backup timer, server capacity, approved URLs | No secrets or control action |
| `/brief` | On-demand digest from the existing local harness data | Does not claim data from unconnected sources |
| `/reporting director\|management\|dev` | Audience-formatted aggregate task and operational summary | No task detail or personal data until owner RBAC exists |
| `/sources` | Explicit connected/unconnected source inventory | GitHub, Slack, Notion, NEXONE, billing, domain, and support remain unconnected |
| `/reminders` | Existing harness alert coverage | DevOps/domain/billing/sales/certificate/client reminders are not active yet |
| `/support` | Safe status of support intake | Rejects sensitive customer/incident details until helpdesk routing is approved |
| `/deploy` | Hard refusal | Production remains GitHub Environment approval only |

Existing harness commands for task management, agent runs, diffs, reports, and
push to `dev` or `staging` remain unchanged. They do not authorize `main`,
`master`, production deployment, production migration, credential changes, or
production shell access.

#### Telegram RBAC — deployed to the live local service (2026-09-17)

The per-chat role layer is now **deployed and running** on the live Telegram
service (`com.ah.telegram` launchd service on the workspace host). Deployment
followed the prescribed procedure: the four service files were backed up to
`archives/tg-deploy-backup-20260917/`, imports and role-resolution sanity were
validated with the service interpreter (legacy paired chat resolves to `owner`,
unknown chat resolves to no role), only the Telegram service was restarted, and
the service was verified `running` with a clean log afterwards. No Telegram
message was sent during verification.

- `viewer` receives only aggregate read-only status such as `/status`, `/ops`,
  `/brief`, and `/reporting`.
- `operator` may additionally view task and execution detail.
- `owner` alone may dispatch or stop agents, mutate tasks, trigger work, access
  diagnostics, push to `dev`/`staging`, and use `/grant`.
- Existing paired chats resolve to `owner` when no explicit role is recorded,
  preserving backward compatibility and preventing accidental lockout.
- A new paired chat becomes `viewer` once an owner exists. An owner cannot
  demote the final remaining owner.
- Notifications that include task/execution detail target `operator` and
  `owner` only.

Rollback path: restore the four backed-up files from
`archives/tg-deploy-backup-20260917/` and restart `com.ah.telegram` again.
Role behaviour (legacy paired chat = `owner`, viewer denied `/run`, last owner
cannot be demoted) is pinned by `tests/test_telegram_roles.py` and the
operations-command tests, all passing before the restart.

#### Current n8n capability versus active behavior

n8n is ready as a constrained workflow platform: workflow canvas, manual and
scheduled triggers, webhook framework, encrypted credential storage, execution
history, isolated PostgreSQL, and local backup are available. However, zero
workflow is active. Therefore the following outcomes are intentionally absent:

- no GitHub/Slack/Notion/NEXONE data ingestion;
- no daily report, alert, ticket, document update, customer response, or AI
  response generated by n8n;
- no Telegram webhook in n8n; the existing bot keeps sole long-poll ownership;
- no deployment, DNS, billing, payment, shell, SSH, filesystem, or custom-code
  action from n8n.

The n8n owner account must be created in the UI after passing host Basic Auth.
Do not send that account password, host Basic Auth credential, SSH credential,
or encryption key through chat, source control, Telegram, Slack, or Notion.

#### Continuation protocol

1. Start every change with a read-only inventory and identify the source of
   truth, data classification, owner, required scope, retention, and rollback.
2. Build one workflow at a time in a non-production mode with synthetic or
   redacted test data. Record its trigger, inputs, outputs, failure mode,
   alert target, and disable/rollback procedure.
3. Use a dedicated least-privilege credential per integration. Verify webhook
   signatures, replay protection, idempotency, egress allowlist, redaction,
   retries, and a dead-letter path before activation.
4. Test from manual execution through notification delivery. Capture execution
   evidence without secrets, then obtain explicit owner approval before enabling
   a schedule or webhook.
5. Re-run `n8n audit`, the focused harness tests, and a service health check.
   Update this document and the Notion handoff page with the actual resulting
   behavior and the next safe action.

#### Next implementation order

1. Create the n8n owner account and rotate the bootstrap host credential after
   owner access is confirmed.
2. ~~Establish owner RBAC for the Telegram surface~~ — **done 2026-09-17**:
   role layer deployed to the live `com.ah.telegram` service with backup,
   import validation, and health verification. Dashboard-side RBAC remains
   open until a non-owner dashboard audience actually exists.
3. Add a GitHub read-only integration with a dedicated token and one manual
   daily engineering-status workflow. No write scope, dispatch, or production
   deployment permission. The inactive review artifact is
   `ops/n8n/workflow-templates/github-read-only-daily-status.json`; it must be
   reviewed, supplied with a dedicated credential, and manually tested before
   import/activation. Run `ops/n8n/validate_workflow_templates.py` first; its
   manifest requires owner, data classification, credential scope, outputs,
   activation prerequisites, and rollback for every template.
4. Add a Slack notification credential restricted to the approved channel and
   wire only the reviewed report output.
5. Add monitor-only workflow(s) for uptime, SSL, backup freshness, and server
   capacity. Add domain/billing/certificate sources only with read-only API
   scope or a reviewed notification feed.
6. Resolve the NEXONE authentication review before any connection. Do not use
   broad credentials or scrape protected data as a workaround.
7. Add Notion and support intake only after document/FAQ allowlists, audience,
   retention, and human handoff policy are approved.
8. Consider AI only after the prior controls are stable, with a separate API
   project, budget cap, source allowlist, redaction, citations, and write-action
   approval gates.

#### Verification record

- Local focused tests for Telegram operations, Telegram control, task
  management, and operations surface: 31 passed.
- Syntax/import validation of the deployed Telegram command modules passed.
- `ah-telegram.service` was restarted after backup and verified `active`.
- `/ops` smoke test on the VPS returned: n8n loopback `ok`, daily local backup
  `ok`, and server capacity status. No Telegram message was sent for this test.
- 2026-09-17 continuation pass: full local suite 200 tests OK; isolated n8n
  stack tests 10 OK (`ops/n8n/tests`); `validate_workflow_templates.py` passes.
  Two latent test defects fixed at root cause: `test_validate_env.py` never
  executed (missing `unittest.main()` entry point, so its 5 tests silently
  never ran), and `test_job_exit_status.py` leaked one temp workspace per run
  into the repo root (stale `engine` module recreated `agents/.engine.lock`
  after cleanup; the module pop list now matches every sibling test). Leaked
  `tmp*` dirs removed; `.gitignore` now covers `agents/.engine.lock` and the
  tempfile leak pattern. RBAC deployed to `com.ah.telegram` per procedure;
  service verified `running`, log clean, zero leaks on repeat suite runs.

- 2026-09-17 nginx rate-limit pass (outage `agents.nexoratech.co`): root cause
  was the sustained rate, not the burst. `conf.d/agents-rate-limit.conf` still
  carried `rate=60r/m` (1 r/s) while `burst=200` had been raised in an earlier
  pass; a browser page load outruns the refill, so nginx answered `429` for
  `dash.js` (chip frozen on `connecting…`) and for the n8n asset chunks (blank
  `/automation/`). Reproduced from outside without credentials: 4 waves x 60
  parallel asset requests gave 33/240 `429` before the change, 0/240 after.
  Deployed `rate=10r/s` plus `Upgrade`/`Connection` forwarding to n8n, which the
  live vhost had never set. Both files backed up to `…bak-20260917T113952Z-*`;
  `nginx -t` then `systemctl reload nginx` (graceful, no restart, no other vhost
  touched). Artefacts, validator, probe and tests now live in `ops/nginx/`
  (8 tests OK) — previously the vhost existed only on the host with no reviewable
  copy. Loopback after reload: dashboard `/api/state` and `/dash.js` 200, n8n
  `/automation/` and `/healthz` 200; every asset referenced by the n8n HTML
  resolves under the `/automation/` prefix. `ah-dashboard` and `ah-telegram`
  restarted onto current code (both `active/running`, 0 restarts). Owner
  hard-refresh remains the acceptance gate.

- 2026-09-17 `/automation/` blank page, penyebab ketiga yang independen: n8n
  2.39.6 menyajikan bundel dari **root server** (`/assets/`, `/static/`) dan
  tidak lagi memasangnya di bawah `N8N_PATH`, sehingga vhost yang meneruskan
  prefix membalas `index.html` (200 `text/html`, 56733 B) untuk setiap aset dan
  `nosniff` menahan eksekusinya. Klaim handoff sebelumnya bahwa "prefix wajib
  utuh" keliru untuk n8n 2.x. Diperbaiki dengan `proxy_pass …:5678/` (trailing
  slash) plus redirect `location = /automation`. Dibuktikan lebih dulu di
  chromium headless lewat server block loopback sementara dengan CSP produksi
  yang sama: `RENDERED: YES`. Kontrol tanpa nginx sama sekali tetap blank, jadi
  CSP dan auth tidak bersalah dan CSP **tidak** dilonggarkan. Verifikasi §4
  sebelumnya ("6/6 aset → 200") keliru karena hanya memeriksa status code, bukan
  `Content-Type`; `verify_rate_limit.sh` sekarang memeriksa `Content-Type` bila
  diberi credential. Backup `…bak-20260917T124046Z-prefix`; `ops/nginx/tests`
  naik ke 10 test hijau.

- 2026-09-17 penutupan outage `agents.nexoratech.co`, diverifikasi end-to-end di
  chromium headless terhadap produksi dengan credential owner. Dua cacat lagi
  ditemukan setelah perbaikan prefix: (a) `limit_req` salah ukuran karena
  diturunkan dari estimasi handoff "40+ chunk" — satu cold load editor ternyata
  **797 request** terukur, dinaikkan ke `rate=50r/s` + `burst=1200`; (b) pada
  nginx 1.24 `limit_conn` menghitung tiap **stream HTTP/2** sebagai koneksi,
  sehingga `limit_conn 10` → 629×503 dan `64` → 407×503; dipasang
  `http2_max_concurrent_streams 128` eksplisit + `limit_conn 256` → 0×503.
  Hasil akhir: editor render ("Set up owner account"), 794×200 / 0×429 / 0×503;
  dashboard chip `live`, 0 pelanggaran CSP, 0 JS error. Satu-satunya pelonggaran
  CSP yang pernah dilakukan adalah `img-src 'self' data:` untuk favicon inline-SVG
  dashboard. `ops/nginx/tests` 14 hijau, angka 797 dipin sebagai konstanta.
  Job `101013-2ce5` yang `failed` ternyata spend limit Claude, bukan bug harness.
  **Wajib dirotasi:** credential Basic Auth `imam` (pernah lewat chat), bersama
  password root.

## Keputusan yang sudah disepakati

- n8n Community Edition berjalan sebagai stack terisolasi pada `31.97.67.241` untuk fase awal.
- Tidak ada container, database, credential, atau port aplikasi existing yang dipakai sebagai dependency.
- Floot tidak menjadi dependensi sistem. Floot yang sudah ada hanya dapat dipertahankan sebagai pembanding terpisah, atau tidak digunakan sama sekali.
- n8n Community Edition self-hosted digunakan sebagai kandidat utama mesin workflow; lisensinya gratis, tetapi server, backup, patching, dan keamanan tetap menjadi tanggung jawab operasional.
- Produksi, `main`, migrasi produksi, perubahan credential, dan tindakan berdampak tinggi wajib memerlukan persetujuan eksplisit Imam. Telegram dan Slack hanya mengarahkan ke approval resmi, tidak dapat membypass gate.
- Akun awal dengan akses detail adalah `imam.nurokhi`. Data untuk peran lain disajikan sebagai insight/aggregat sampai RBAC dan identitas organisasi terverifikasi.
- Customer support otomatis hanya memakai FAQ yang sudah dikurasi dan disetujui. Pertanyaan di luar cakupan diteruskan ke manusia.
- Integrasi AI, termasuk Claude Team atau ChatGPT/Codex, ditunda. Paket chat tidak dapat dipakai langsung sebagai API workflow; API/billing terpisah diperlukan bila fase AI dimulai.

## Arsitektur target

```text
Telegram / Slack / Dashboard Web
              |
              v
     Operations Workspace (akses owner)
              |
              +-- n8n workflow orchestration
              |     +-- scheduler, reminder, report, notification
              |     +-- webhook GitHub dan sumber yang disetujui
              |     +-- audit log dan retry/dead-letter handling
              |
              +-- Read model / database operasional terpisah
              |
              +-- GitHub Actions + protected environments
              |     +-- CI/CD dan approval produksi di GitHub
              |
              +-- Existing local agent harness
                    +-- menerima task/report terkontrol
                    +-- tidak diberi jalur autonomous ke produksi
```

Setiap komponen baru di VPS harus memiliki container, network, database, service account, secret store, backup, dan log retention sendiri. Ia tidak boleh memakai database, credential, port publik, atau konfigurasi aplikasi existing tanpa audit dan persetujuan eksplisit.

## Penerapan tanpa AI

### Dashboard dan task visibility

- Dashboard satu URL berisi status sprint, task, pull request, CI/CD, incident, uptime, domain/SSL, backup, dan billing reminder.
- NEXONE, GitHub, Slack, dan sistem lain tetap menjadi source of truth; workspace menyajikan read-only status dan tautan kontekstual, bukan duplikasi data bisnis.
- Data detail hanya tersedia untuk akun pemilik; laporan lain menggunakan agregasi dan redaksi sesuai audience.

### Telegram dan Slack

- Perintah/status owner-only untuk melihat ringkasan operasional, health, task tertunda, dan alert.
- Daily brief, kegagalan build, overdue review, incident, sertifikat/domain/billing jatuh tempo, serta eskalasi dikirim melalui channel yang disetujui.
- Semua request, acknowledgement, dan approval link dicatat dalam audit trail bersama.
- Tidak ada remote command execution, akses shell, atau deployment langsung dari pesan.

### Reporting dan dokumentasi

- Daily/weekly report deterministik untuk direktur, manajemen, dan developer dari data yang sudah disetujui.
- Pengingat dokumentasi saat issue/PR/release selesai; template runbook, changelog, dan release note dibuat sebagai draft untuk ditinjau manusia.
- Smart documentation tahap awal berupa source linking, template, status kelengkapan, dan stale-document reminder. Generasi/ringkasan berbasis AI ditambahkan kemudian.

### DevOps, domain, dan billing

- Pantau uptime, SSL expiry, domain expiry, kapasitas, backup, CI failure, dan incident dari probe atau API read-only dengan scope minimum.
- Billing dan renewal hanya menghasilkan reminder/escalation; tidak ada pembayaran, renewal, perubahan DNS, atau perubahan infrastruktur otomatis.
- Jangan mengubah monitoring yang telah berjalan pada VPS sebelum inventory dan approval perubahan tersedia.

### Agent orchestration dan deployment governance

- Agent harness yang sudah ada tetap menangani lifecycle development: plan, task, worktree, test, review, dan laporan.
- Workflow cloud mengumpulkan status dan mengirim notifikasi, bukan menjalankan agent dengan credential produksi.
- GitHub branch protection dan GitHub Environment menjadi gate otoritatif untuk produksi. Credential produksi hanya tersedia pada environment yang telah lolos approval Imam.
- Telegram/Slack dapat mengirim konteks dan tautan ke GitHub, tetapi tidak dianggap sebagai approval produksi yang valid.

### Customer dan developer support

- Fase awal menyediakan intake form/web chat, ticket routing, SLA reminder, status update, dan human handoff.
- Customer FAQ hanya menjawab artikel yang masuk allowlist. Tidak ada pencarian ke dokumen internal, data NEXONE, data client, atau tool execution.
- Support developer dapat menerima incident/bug report dan membuat task yang memerlukan konfirmasi sebelum ditulis ke sistem sumber.

## Data dan keamanan

- Lakukan inspeksi read-only terhadap setup parsial VPS sebelum pemasangan atau perubahan apa pun.
- Gunakan least privilege, credential per-integrasi, secret management, rotasi secret, webhook signature verification, replay protection, rate limiting, dan audit log.
- Nonaktifkan node n8n yang dapat menjalankan shell/filesystem serta community/custom node sampai melewati security review. HTTP egress dibatasi ke allowlist endpoint integrasi.
- Jangan mengirim payload sensitif ke log, Slack, Telegram, Floot, atau provider AI. Terapkan redaksi sebelum event dipersistenkan atau dinotifikasi.
- NEXONE hanya diintegrasikan setelah audit authorization selesai. Hingga saat itu gunakan metadata terbatas atau laporan manual yang telah direview, bukan credential akses luas atau data detail.
- Backup database/workflow dienkripsi, diuji restore-nya, dan memiliki retention policy yang jelas.

## Roadmap implementasi

### Fase 0: Discovery dan hardening

1. Mendapatkan izin inspeksi read-only ke `31.97.67.241`.
2. Inventaris container, reverse proxy, domain, port, network, resource headroom, backup, firewall, dan setup n8n/automation parsial.
3. Memetakan integrasi yang boleh dibaca, data classification, owner setiap credential, dan jalur incident.
4. Menetapkan batas isolasi stack baru dan rollback plan tanpa mengubah layanan existing.

### Fase 1: Fondasi operasional non-AI

1. Menyelesaikan isolasi deployment n8n, database, log, backup, dan akses owner-only berdasarkan hasil discovery.
2. Menghubungkan event GitHub read-only/terverifikasi dan notifikasi Slack/Telegram owner-only.
3. Membangun dashboard status, daily brief, CI failure alert, overdue reminder, dan audit trail.
4. Mengonfigurasi GitHub Environment approval untuk semua jalur produksi.

### Fase 2: Workspace dan knowledge governance

1. Menambah task/read model, report audience tier, dokumentasi reminder, dan support intake.
2. Menentukan allowlist dokumen/FAQ serta proses approval untuk setiap konten customer-facing.
3. Menambah domain, SSL, backup, dan billing read-only monitoring.

### Fase 3: AI setelah foundation diterima

1. Menyediakan API project terpisah dengan prepaid budget cap, alert konsumsi, secret terpisah, dan evaluasi data processing.
2. Memulai dari GitHub dan dokumentasi approved yang bersifat read-only serta selalu memberikan source citation.
3. Menjalankan AI sebagai summarizer, classifier, dan pembuat draft; semua write action, ticket creation, dokumentasi publish, dan deploy tetap memerlukan approval sesuai policy.
4. Memperluas ke sumber lain hanya setelah authorization dan data classificationnya selesai diverifikasi.

## Acceptance criteria

- Tidak ada layanan existing pada `31.97.67.241` yang berubah tanpa approval dan change record.
- Workflow dapat dipulihkan dari backup dan gagal dengan aman saat integrasi/sumber data tidak tersedia.
- Event webhook tervalidasi signature, deduplicated, rate-limited, dan tidak membocorkan payload sensitif ke log/notifikasi.
- Akun selain owner tidak dapat mengakses data detail atau action administratif.
- Produksi tidak bisa dijalankan melalui bot ataupun workflow tanpa GitHub approval yang dilakukan Imam.
- Customer bot tidak menjawab di luar FAQ allowlist dan selalu memiliki jalur human handoff.
- Dashboard, Telegram, dan Slack menampilkan status yang konsisten dari audit/read model yang sama.

## Referensi keputusan teknis

- [n8n pricing dan Community Edition](https://n8n.io/pricing/)
- [GitHub deployment environments dan required reviewers](https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments)
- [OpenAI: billing ChatGPT dan API terpisah](https://help.openai.com/en/articles/9039756)
- [Anthropic: Claude plan dan API billing terpisah](https://support.anthropic.com/en/articles/9876003-i-subscribe-to-a-paid-claude-ai-plan-why-do-i-have-to-pay-separately-for-api-usage-on-console)
