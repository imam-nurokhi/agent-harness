# VPS recon — 31.97.67.241 (task-032)

**Date:** 2026-09-16
**Access:** SSH as root (password, out-of-band). Read-only survey; nothing changed.

## Headline: this is not a sandbox

The host identifies itself as **`dev-kemenkes.nexoratech.co`** (banner on the
`AI` user). It is a **shared production host**, not the clean sandbox VPS
task-032 assumed. nginx is already serving live sites and the box carries a
government-health (Kemenkes) dev environment.

## System

| | |
|---|---|
| OS | Ubuntu 24.04.4 LTS, x86_64 |
| CPU / RAM | 2 cores / 7.8 GiB (2.5 used, ~1.3 free) |
| Disk | 96 G root, 23 G used, 73 G free (24%) |
| python3 | 3.12.3 ✓ |
| git | 2.43.0 ✓ |
| docker | 29.1.3 ✓ |
| ufw | present |
| node / npm | **absent** |
| ripgrep | **absent** |
| claude / codex | **absent** |
| certbot | 2.9.0 ✓ |
| caddy | absent (nginx is the web server — do **not** add caddy) |
| fail2ban | absent |

## Web server — already live, shared

nginx owns 80/443. Existing `sites-available`:
`deacademy`, `dev-support.nexoratech.co`, `monitoring.nexoratech.co`, `one`,
`training`, `validation`. These are live; touching nginx touches them.

`monitoring.nexoratech.co` is a clean model to copy for `agents.`: TLS via
certbot, `location / { proxy_pass http://127.0.0.1:3000; ... }`, port-80 block
returns 404. An `agents.` vhost would proxy to `127.0.0.1:7777` the same way,
plus `auth_basic`.

- `agents.nexoratech.co` vhost: **not configured yet**.
- DNS `agents.nexoratech.co` → `31.97.67.241`: **already resolves.** ✓
- Port 7777: **free.** ✓

## Users

| user | uid | note |
|---|---|---|
| ubuntu | 1000 | default admin |
| **AI** | 1001 | **read-only analyst**, `rbash`, banner "READ ONLY" — deliberately locked down; NOT a harness account |
| viewonly | 1002 | |
| github-runner | 1003 | CI runner |

No user has `linger` enabled. SSH still allows password auth (default).

## What this means for task-032

The plan was written for a dedicated sandbox. On a shared prod host the risk
profile is different in three ways that need a decision before any change:

1. **The harness executes code.** It spawns Claude/codex agents that run
   commands in a worktree. Putting that on the same box as `dev-kemenkes` and
   other live sites widens the blast radius well beyond a sandbox.
2. **nginx fronts live sites.** Adding the `agents.` vhost and running
   `certbot` is low-risk if done as an additive vhost + `nginx -t` before
   reload, but it is still a change to the server that serves production.
3. **A public dashboard.** `agents.nexoratech.co` would expose the Command
   Center. It must sit behind `auth_basic` + TLS with the dash bound to
   loopback only — never `0.0.0.0`.

## Recommended safe split

- **Now, low-risk (no prod surface touched):** create a dedicated non-root user
  (e.g. `ahagent`) with linger, install node + claude CLI in its home, clone the
  harness + `projects/sandbox`, `.env` with the **new** `@AgentNexoraBot` token,
  `.scope` holding cbqa/nexora, and start the bot + triggers + hourly
  auto-resume. The bot is an **outbound long-poll** — it binds no port and does
  not touch nginx. This alone gives Telegram control from the phone.
- **Confirm before doing:** the `agents.nexoratech.co` nginx vhost + certbot on
  this shared prod host, and whether an autonomous code-executing harness
  belongs on the same box as `dev-kemenkes` at all. A separate small VPS for the
  harness would keep the two apart.

## Not done / blocked
- No changes made — this is the read-only survey task-032 requires first.
- Awaiting a decision on the prod-host questions above before installing.

---

## Bring-up executed 2026-09-16 (option: bot-first, no nginx)

Owner chose "bot dulu, tanpa nginx". Done, all additive and isolated — nothing
running on the shared host was touched:

- User `ahagent` (non-root) created, linger enabled. NOT the locked `AI` user.
- `apt install ripgrep` (new package; no service touched).
- Harness code rsynced to `/home/ahagent/AI-Workspace` (5.2M; no `.env`, no
  worktrees, no state, no `.git`).
- `.env` (0600) with the **new** `@AgentNexoraBot` token; owner chat 6687943152
  pre-allowed; `.scope` holds `cbqa/*` and `nexora/*`.
- claude CLI 2.1.273 installed in `ahagent`'s `~/.local/bin` (user-scoped).
- systemd **user** units (isolated under ahagent's linger session, bind no port):
  - `ah-telegram.service` — active, 0 restarts, long-poll (no webhook), sole poller.
  - `ah-resume.timer` — hourly at :10; manual sweep returned `idle` (no spam).
- Verified end-to-end: bot delivered a live-summary message to the owner chat.

### Not touched (as promised)
- nginx and every existing vhost (dev-kemenkes, dev-support, monitoring, …).
- ports 80/443; no new listeners except the bot's outbound long-poll.
- the `AI` read-only user; root SSH/password (untouched pending owner's rotation).

### The one remaining step — interactive, owner-only
claude is **not logged in** on the VPS (`Not logged in · Please run /login`).
Until then the bot answers but agents cannot run (engine pauses). To finish:
`ssh root@31.97.67.241` → `sudo -iu ahagent` → `claude setup-token`.

### Still held for explicit go
- `agents.nexoratech.co` nginx vhost + certbot (touches the shared prod server).
- token rotation for the old agent-kara plist on the Mac (not migrated here).
