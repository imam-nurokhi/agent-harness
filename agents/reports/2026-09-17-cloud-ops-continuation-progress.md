# Progress continuation cloud-ops — 2026-09-17

Lanjutan plan `docs/nexora-cbqa-cloud-operations-plan.md` setelah agent sebelumnya
berhenti. Dokumen ini mencatat apa yang benar-benar dikerjakan dan diverifikasi,
bukan klaim target akhir.

## Bagian 1 — Lokal (workspace Mac), selesai & tercommit

### Gap yang ditemukan dan dibereskan sampai root cause

1. **RBAC Telegram belum live.** Service launchd `com.ah.telegram` (PID lama 784)
   berjalan dengan kode 7 jam lebih tua dari perubahan RBAC (file diubah 09:01,
   proses start 01:57). Deploy sesuai prosedur plan:
   - Backup 4 file service ke `archives/tg-deploy-backup-20260917/`
     (`tgcore.py`, `tgbot.py`, `tgcmd.py`, `resumerun.py`).
   - Validasi import + sanity role dengan interpreter service
     (`/opt/homebrew/bin/python3`): chat paired lama resolve ke `owner`,
     chat tak dikenal resolve ke tanpa role.
   - Restart hanya `com.ah.telegram` (`launchctl kickstart -k`), PID baru 27307,
     `state = running`, log bersih, tanpa mengirim pesan Telegram.
   - Rollback: restore 4 file dari backup + kickstart ulang.
2. **Test mati:** `ops/n8n/tests/test_validate_env.py` tidak punya entry point
   `unittest.main()`, sehingga 5 test-nya tidak pernah dieksekusi. Ditambahkan;
   sekarang jalan dan lulus.
3. **Leak temp workspace (root cause):** `tests/test_job_exit_status.py` hanya
   pop `"state"` dan `"jobs"` dari `sys.modules`, tidak `"engine"`. Modul
   `engine` basi membekukan `STATE` dari `state.WORKSPACE` saat import, lalu
   `_locked()` men-`mkdir` + menulis `agents/.engine.lock` ke temp dir yang
   sudah di-cleanup test lain → 1 folder `tmp*` leak per run suite (23 folder
   ditemukan di root repo). Pop list disamakan dengan sibling test; leak
   terverifikasi hilang (3 run berturut-turut, 0 folder baru); sisa folder
   dibersihkan setelah isi diverifikasi hanya `.engine.lock`.
4. **Hygiene git:** `.gitignore` ditambah `agents/.engine.lock`, pola
   `/tmp????????/`, `.commandcode/`, `.playwright-cli/`, `output/`, dan
   `agents/reports/*.pdf`.

### Verifikasi lokal

- Suite `tests/`: 200 test OK (berulang, termasuk pasca-fix).
- Suite `ops/n8n/tests`: 10 test OK.
- `ops/n8n/validate_workflow_templates.py`: valid.
- Working tree bersih setelah commit.

### Commit (repo lokal, tanpa remote → tidak ada push)

| Hash | Isi |
|---|---|
| `0cc34d1` | feat(ops): cloud operations surface — Telegram RBAC, /ops commands, isolated n8n stack artifacts |
| `e28f5d4` | chore(harness): task and report ledger — tasks 030-038 recorded, stale tasks pruned |
| `5e3a2e8` | fix(tests): stop temp-workspace leak at the root; ignore runtime/tooling state |

## Bagian 2 — VPS 31.97.67.241, diagnosis + satu perubahan nginx

Akses: SSH root dengan password yang diberikan owner pada sesi ini
(**wajib dirotasi setelah sesi ini** — credential pernah muncul di chat).
Semua langkah diagnosis read-only.

### Temuan diagnosis (gejala: dashboard "connecting…", /automation/ blank)

- Service & container sehat: `ah-dashboard` active (sejak 16 Sep 19:43 UTC),
  `nexora-operations-n8n-1` Up, `nexora-operations-postgres-1` Up (healthy).
- Loopback sehat: `http://127.0.0.1:7777/api/state` → 200 JSON valid;
  `http://127.0.0.1:5678/healthz` → 200; `.../automation/` → 200.
- nginx vhost `agents.nexoratech.co` aktif; TLS & Basic Auth berfungsi
  (semua endpoint 401 tanpa credential).
- **Root cause kedua gejala: rate limit.** `conf.d/agents-rate-limit.conf`
  mendefinisikan `zone=agents_per_ip rate=60r/m` (1 r/s) dan vhost memakai
  `burst=30 nodelay`. UI n8n memuat ±40+ asset JS paralel sekali buka →
  kelebihan burst → 429 pada semua chunk (`/automation/assets/*.js`), halaman
  blank. Bucket yang sama juga menghabisi request dashboard
  (`/dash.js`, `/api/state` → 429) → chip "connecting…".
  Bukti: `error.log` — `limiting requests, excess: 30.243 by zone "agents_per_ip"`;
  `access.log` — puluhan `429` pada asset `/automation/` dan `/dash.js`
  dari IP owner saat membuka halaman.

### Perubahan yang dibuat (satu-satunya perubahan di VPS)

- File: `/etc/nginx/sites-available/agents.nexoratech.co`
  - `limit_req zone=agents_per_ip burst=30 nodelay;` →
    `limit_req zone=agents_per_ip burst=200 nodelay;`
  - Rate berkelanjutan (60r/m), `limit_conn`, Basic Auth, dan seluruh vhost
    lain tidak diubah.
- Backup: `/etc/nginx/sites-available/agents.nexoratech.co.bak-20260917-ratelimit`
- `nginx -t` lolos; `systemctl reload nginx` (graceful) sukses.
- **Belum diverifikasi pasca-reload** — sesi dihentikan owner tepat setelah
  reload. Tidak ada perubahan lain di VPS.

### Rollback (bila diperlukan)

```sh
cp -p /etc/nginx/sites-available/agents.nexoratech.co.bak-20260917-ratelimit \
      /etc/nginx/sites-available/agents.nexoratech.co
nginx -t && systemctl reload nginx
```

### Tidak disentuh sama sekali

- Container n8n/PostgreSQL dan compose stack-nya; backup timer.
- Service `ah-dashboard`, `ah-telegram`, `ah-resume.timer` di VPS.
- vhost lain (dev-kemenkes, dev-support, monitoring, dll.), port 80/443 umum.
- Credential, user, atau authorized_keys di VPS.

## Langkah berikutnya (belum dikerjakan)

1. Verifikasi pasca-reload: burst test loopback (±60 request cepat tanpa auth
   via `--resolve` ke 127.0.0.1; sebelum fix menghasilkan 429, sesudah fix
   semuanya 401 tanpa 429), lalu hard refresh
   `https://agents.nexoratech.co` dan `/automation/` di browser owner.
2. Rotasi password root VPS (pernah dikirim lewat chat) dan credential
   bootstrap Basic Auth dashboard sesuai plan.
3. Lanjut urutan plan: akun owner n8n via UI, lalu review template
   `ops/n8n/workflow-templates/github-read-only-daily-status.json` dengan
   credential dedicated sebelum import/aktivasi.
4. Push tetap tertahan: repo lokal tidak punya remote; bila remote ditambah,
   push hanya ke `dev`/`staging`.

## Catatan keamanan

- Password root VPS dan credential Basic Auth tidak ditulis ke file repo mana
  pun; hanya dipakai via environment variable pada sesi SSH ini.
- Tidak ada payload sensitif yang dikirim ke Telegram/Slack/log selama sesi.
