# Task: Fase 2: bring-up harness di VPS 31.97.67.241 (sandbox saja)

- **ID:** task-032
- **Project:** AI-Workspace (`~/AI-Workspace`)
- **Class:** personal
- **Role:** devops
- **Worktree:** `~/AI-Workspace/worktrees/task-032`
- **Base branch:** main

## Background
Yang menjaga trigger tetap menyala sekarang justru `com.ah.awake.plist` — `caffeinate -dimsu`
yang memaksa Mac melek. Tujuan pindah ke VPS adalah menghapus ketergantungan itu.

Keputusan yang sudah diambil: **VPS jadi satu-satunya rumah harness**, Mac jadi klien.
Engine **Claude (akun kerja `imam.nurokhi@nexoratech.co`) dengan fallback codex** — lihat
`bin/lib/engine.py`; harness memilih claude, jatuh ke codex saat ditolak/limit, dan pause +
lapor Telegram saat keduanya habis. Repo yang dibawa: **`projects/sandbox` saja**, sisanya
menyusul setelah terbukti stabil.

**Host (direvisi 2026-09-16):** `31.97.67.241`. Kredensial bootstrap ada di
`~/.config/nexora/vps-agents.env` (chmod 600, **di luar git**) — host, user, password root,
dan domain monitor. Password itu dibagikan lewat chat, jadi **wajib dirotasi** begitu login
key-based aktif (lihat Constraints).

Prasyarat: task-030 selesai, kalau tidak `ah bot install` dan `ah trigger install` tidak
berfungsi di Linux. (task-030 mem-source `supervise.sh`; itu yang merender systemd user unit.)

## Objective
Mac bisa dimatikan dan harness tetap bekerja: bot menjawab dari HP, trigger tetap menyala,
dan **monitoring Command Center bisa diakses di `https://agents.nexoratech.co`** dengan TLS
dan autentikasi — bukan lagi hanya lewat SSH tunnel.

## Scope
- Survei read-only VPS dulu, tulis ke `agents/reports/vps-recon.md`, sebelum ada yang diubah:
  distro, RAM/disk, ada tidaknya node/python3/git/claude, `systemctl --user` tersedia?,
  apakah 80/443 bebas, apakah ada nginx/caddy terpasang.
- **Rotasi TELEGRAM_BOT_TOKEN via @BotFather** (wajib, lihat Constraints)
- **Rotasi password root VPS** setelah SSH key terpasang, lalu perbarui
  `~/.config/nexora/vps-agents.env`; matikan login password.
- User non-root khusus + `loginctl enable-linger`
- Toolchain: node LTS, python3, git, ripgrep, claude CLI
- Login Claude sekali lewat SSH sebagai akun kerja; set `CLAUDE_CONFIG_DIR` yang benar di
  environment supervisor (jangan andalkan warisan — itu justru bug yang menutup sesi ini);
  trigger `auth` baru yang memperingatkan lewat Telegram saat auth mati
- Clone harness; `.env` baru chmod 600; set `AH_CLAUDE_CONFIG_DIR` ke config akun kerja
- Clone `projects/sandbox` saja; `agents/.scope` mulai dengan `HOLD cbqa/*` dan `HOLD nexora/*`
- Pasang bot + trigger + **auto-resume hourly** (`ah resume install`) lewat `supervise.sh`;
  pairing ulang dari HP
- **Monitoring publik `agents.nexoratech.co`:**
  - reverse proxy (caddy diutamakan — TLS otomatis via Let's Encrypt) di depan dash `127.0.0.1:7777`
  - dash **tidak pernah** bind ke `0.0.0.0`; proxy yang menghadap internet, dash tetap loopback
  - autentikasi di proxy (basic-auth minimal, kredensial di secret store, bukan git) —
    dash sekarang punya token API tapi papan itu sendiri belum berautentikasi
  - DNS A record `agents.nexoratech.co` → `31.97.67.241` (catat siapa yang pegang zona;
    kalau tidak bisa diubah dari sini, hasilkan langkah persisnya di report)
  - firewall: buka 80/443 selain 22; dash tetap tak terjangkau langsung dari luar
- Hardening: SSH key-only, root login mati, fail2ban, unattended-upgrades, header keamanan di proxy
- README dicatat: bot, trigger, dan auto-resume **tidak pernah** dipasang lagi di Mac

## Out of scope
- Clone repo cbqa/nexora — keputusan terpisah, butuh persetujuan eksplisit
- Webhook Telegram (tetap long-poll)
- Menulis rahasia apa pun ke git — kredensial selalu di `~/.config/nexora/` atau `.env` (chmod 600)

## Acceptance criteria
- [ ] `agents/reports/vps-recon.md` ada dan ditulis sebelum perubahan pertama
- [ ] `ah doctor` di VPS hijau, termasuk cek auth claude sebagai akun kerja
- [ ] `ah engine` di VPS menunjukkan `chosen: claude` (akun kerja), bukan ditolak
- [ ] Mac **dimatikan**, lalu dari HP `/status`, `/kanban`, `/ask lead ringkas status` berhasil
- [ ] Trigger `standup` menyala esok paginya dan memo-nya tercatat
- [ ] Auto-resume hourly terpasang (`ah resume status` = installed) dan satu sweep tercatat di log
- [ ] Hanya ada satu long-poller: `/status` dibalas sekali, tidak hilang bergantian
- [ ] `ah run backend <task>` terhadap repo cbqa/nexora ditolak oleh `assert_execution_allowed`
- [ ] `https://agents.nexoratech.co` memuat Command Center dengan sertifikat valid
- [ ] Tanpa kredensial, `agents.nexoratech.co` menolak (401), bukan menampilkan papan
- [ ] `curl http://31.97.67.241:7777` dari luar **gagal** — dash tak pernah menghadap internet langsung

## Constraints
- **Telegram hanya mengizinkan satu proses long-poll per token.** Sebelum bot menyala di VPS:
  unload + hapus `~/Library/LaunchAgents/com.ah.telegram.plist` **dan**
  `com.imamnurokhi.agent-kara.plist` di Mac, serta cabut baris watchdog agent-kara dari crontab.
  Token agent-kara byte-identik dengan yang di `.env` dan tersimpan plaintext mode 644 —
  karena itu rotasi token wajib, bukan opsional.
- **Password root VPS dibagikan lewat chat** dan ada di `~/.config/nexora/vps-agents.env`.
  Rotasi wajib setelah SSH key aktif; setelah itu login password dimatikan total.
- `com.ah.awake.plist` (caffeinate) di-unload setelah bring-up sukses.
- Harness tidak pernah jalan sebagai root; proxy boleh, tapi dash/bot sebagai user non-root.
- Kredensial tidak pernah masuk git.
- Dash menghadap internet hanya lewat proxy berautentikasi + TLS; loopback-only di belakang.

## Required checks
- [ ] Unit test
- [ ] Integration/API test
- [ ] Lint
- [ ] Build
- [ ] Diff reviewed for secrets and stray files

## Progress
- [ ] survei read-only
- [ ] rotasi token + bersihkan Mac
- [ ] user, toolchain, auth (akun kerja + CLAUDE_CONFIG_DIR)
- [ ] clone harness + sandbox, .env, .scope
- [ ] pasang bot + trigger + auto-resume
- [ ] reverse proxy + TLS + auth untuk agents.nexoratech.co
- [ ] rotasi password root, SSH key-only
- [ ] hardening
- [ ] uji Mac-mati + akses domain

## Report
- Scope done:
- Files changed:
- Commands run + results:
- Tests:
- Risks:
- Not done / blocked:
- Suggested next task:
