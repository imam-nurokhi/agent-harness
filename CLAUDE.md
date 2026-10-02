# CLAUDE.md — working on this workspace

Operational map for a Claude Code session working **on** `~/AI-Workspace`.

This file is for you, the session. It is **not** read by the harness: agents get
`AGENTS.md`, which `jobs.py` injects verbatim into every run. Keep behavioural
rules for agents in `AGENTS.md` and keep them short — every byte there costs
tokens on every single agent run. Detail belongs here or in `agents/reports/`.

---

## 1. You are already on the VPS

`hostname` is `dev-kemenkes`, `eth0` is **31.97.67.241**, and the working
directory is the only copy of the workspace. There is no separate "local" and
"remote" — a 2026-09-17 handoff assumed there was and recorded a blocker
("SSH refused") for a machine it was already sitting on.

Check before assuming: `hostname; ip -4 addr show eth0`.

The VPS is **shared** with `dev-kemenkes`, `dev-support`, `monitoring` and other
vhosts. Anything host-wide (nginx, docker, systemd system units) affects them.

## 2. Services

Everything harness-related runs as **`ahagent` user units**, not system units.
`systemctl is-active ah-dashboard` as root reports `inactive` and is misleading.

```sh
export XDG_RUNTIME_DIR=/run/user/$(id -u ahagent)
sudo -u ahagent XDG_RUNTIME_DIR=$XDG_RUNTIME_DIR systemctl --user status ah-telegram
```

| Unit | What |
|---|---|
| `ah-dashboard` | Command Center on `127.0.0.1:7777` |
| `ah-telegram` | the bot; sole owner of Telegram long-poll |
| `ah-resume.timer` | hourly stalled-task sweep |
| `ah-weekly.timer` | Fri 08:00 WIB management report |
| `com.ah.trigger.standup.timer` | daily 07:00 WIB standup |
| `ah-sprint-daily.timer` | Mon–Thu 07:00 WIB daily-update reminder (Telegram, prep only) — §11 |
| `ah-sprint-weekly.timer` | Fri 07:00 WIB sprint+weekly report reminder (Telegram, prep only) — §11 |
| `ah-channel-telegram` | tmux-wrapped Claude Code session bridged to `@AskNexAIBot` — §13 |
| `ah-channel-health.timer` | every 10 min: is that bridge still *listening*? — §13 |
| `ah-sprint-report.timer` | **Mon–Fri 07:30 WIB** sprint report: reads NEXONE, sends to Telegram — §11 |
| *(monitoring)* | not a unit — `/monitor` reads Prometheus on demand — §15 |
| `nexora-operations-backup.timer` | *system* unit, 02:30 UTC, n8n backup |

Restart the bot after touching anything in `bin/lib/tg*.py`, `weekly.py` or
`slackread.py` — it holds the code in memory and re-registers the slash menu at
startup.

## 3. Tests are the gate

```sh
python3 -m unittest discover -s tests             # 457
python3 -m unittest discover -s ops/harness/tests  # 11
python3 -m unittest discover -s ops/nginx/tests    # 20
python3 -m unittest discover -s ops/n8n/tests      # 10
python3 -m unittest discover -s ops/feedback/tests # 29
```

The two prototype repos carry their own gates on top of these — see §12:
`npm run test:widget` + `npm run test:vanilla-shell` in
`accreditation/nexaccred-react`, and `./run-tests.sh` in `academy`, whose correct
result is **92 passed, 2 skipped** (the two skips are `test_widget_presence.py`
on the un-injected committed HTML — a 94/94 there means you are testing an
injected build).

`test_resume_integration` still flakes occasionally — it races its own detached
child processes, and one run in five failed teardown on 2026-09-19. A single
failure there, with `ResourceWarning: subprocess … is still running`, is the known
race and not your change; re-run before investigating, and look at `_drain_jobs`
if it becomes frequent.

There is **no git repository** for this workspace. No commits, no history, no
`git diff` to review — the owner declined `git init` on 2026-09-17. Reports in
`agents/reports/` are the only change record, so write them.

## 4. Traps that have cost real time

**A `200` is not a verification.** `/automation/assets/*.js` returned `200` with
`Content-Type: text/html` — the SPA catch-all. Status-only checks declared it
healthy while every bundle was broken. Check content type, size, and what the
browser actually does.

**A blank page is usually not CSP.** Three separate times CSP was the suspect
and three times it was innocent. The real causes were rate limiting, then
`/automation/` prefix routing, then `limit_conn`. Do not loosen a security
header because a page looks empty.

**Measure, do not estimate.** Limits sized from a handoff's "40+ chunks" guess
were wrong by more than 10x: one cold load of the n8n editor is **797 requests**.
Two passes shipped a broken fix before anyone counted.

**There are two agent spawn paths.** `bin/lib/common.sh` drives `ah run`;
`bin/lib/jobs.py` builds its own argv and is what the dashboard and Telegram
`/run` and `/ask` use. Fixing one silently leaves the other broken.

**Headless agents cannot be approved.** See `ops/harness/README.md`.

**`ah doctor` lies about credentials unless you source `.env` first.** Bare, it
warns "claude has no credentials on this machine"; with
`set -a; . .env; set +a` it reports them present. The services load `.env`
through `EnvironmentFile`, so the warning is an artefact of how you invoked
doctor, not a real fault. Its old warning about `projects/` and `worktrees/` is
obsolete: both exist since 2026-09-19, with clones of `academy` and
`accreditation` under `projects/` and worktrees created by `ah wt add`.

**"Active" is not "listening".** On 2026-09-21 `@AskNexAIBot` ignored two owner
messages while the unit was `active (running)`, tmux was up and the Claude Code
process had 31 hours of uptime. The channel plugin's `bun` MCP server — the only
path an inbound message takes — had exited, and `Restart=always` never fired
because tmux, the unit's main process, was fine. `bin/channel_health.py` now
classifies the bridge from the processes that actually carry messages
(`healthy`/`deaf`/`down`) and `ah-channel-health.timer` repairs it every 10 min.
Generalise it: when you add a health signal, check the thing that does the work,
not the wrapper around it.

**A status check that cannot ask must not answer "no".** `ah trigger list` showed
every trigger as uninstalled because `systemctl --user` was called without
`XDG_RUNTIME_DIR` and its non-zero exit was read as "not installed" rather than
"could not check" — and separately because `installed` was decided by looking for
a launchd plist on a systemd host. Both fixed 2026-09-21; `standup` now reads
`yes`, which is what §7 always claimed.

**Never work in `/opt/nexora-prototypes/`.** That is the publishing tree: it is
what is live, `refresh.sh` resets it hard, and it is not where changes belong.
Clone or worktree under `projects/`/`worktrees/` instead. When something must be
committed *from* the publishing tree, copy it into a clone and verify the copy
with a sha256 of both trees before committing — that check is what proves the
bytes you tested are the bytes you shipped.

## 5. nginx — `agents.nexoratech.co`

Artefacts in `ops/nginx/` are the source of truth and match the live files
byte-for-byte. Validate before and after any change:

```sh
python3 ops/nginx/validate_vhost.py \
  /etc/nginx/conf.d/agents-rate-limit.conf \
  /etc/nginx/sites-available/agents.nexoratech.co
AUTH=user:pass ./ops/nginx/verify_rate_limit.sh
```

Load-bearing facts, each learned the hard way:

- `proxy_pass http://127.0.0.1:5678/` — **the trailing slash matters.** n8n 2.x
  serves bundles from the server root, so keeping the `/automation/` prefix
  hands back `index.html` for every asset.
- `limit_conn` under HTTP/2 counts **each stream**, not each TCP connection.
  It must exceed `http2_max_concurrent_streams`; both are pinned together.
- `rate=50r/s`, `burst=1200` — derived from the measured 797-request cold load.

Always `nginx -t` then `systemctl reload nginx`. Never restart.

## 6. Harness agent permissions

`ops/harness/claude-settings.json`, handed to both spawn paths. Narrow
allowlist, deny wins. `python3` allowed, `curl`/`wget` denied, `.env` unreadable,
no MCP servers. Since 2026-09-19 agents may `git add` and `git commit` — committing
is local — while `git push`, `gh`, `git remote set-url`, `git config` and reads of
`**/.git/config` stay denied, because publishing is the owner's decision (§14).
Widen it with a test in `ops/harness/tests/`, never with
`--dangerously-skip-permissions` — this host is shared.

There is a **second, narrower** surface: `ops/channels/asknexai-settings.json`, for
the read-only assistant (§13). Do not merge the two — they exist to be different.

## 7. Scheduling

`ah trigger install <id>` goes through `bin/lib/supervise.sh`, which supports
launchd and systemd. Three defects made every scheduled trigger a silent no-op
on Linux until 2026-09-17: the installer was macOS-only, unit files landed in
`~/.config/.config/systemd/user`, and generated units carried no `.env` so the
agent answered "Not logged in".

**Schedules are pinned to `Asia/Jakarta`** (`AH_SCHEDULE_TZ` to override). The
server clock is UTC; without pinning, `daily 07:00` meant 07:00 WIB on the
team's Mac and 14:00 WIB here.

Installed: `standup` only. `health`, `drift` and `sweep` are still uninstalled —
they each run a Claude agent and the owner has not approved the quota.

## 8. n8n — what the owner asked for, and where it stands

From `docs/nexora-cbqa-cloud-operations-plan.md`, *Next implementation order*:

| # | Item | Status |
|---|---|---|
| 1 | n8n owner account + rotate bootstrap host credential | account **done**; rotation **deferred by owner** |
| 2 | Owner RBAC for the Telegram surface | **done**; dashboard-side RBAC still open |
| 3 | GitHub read-only + one manual daily engineering-status workflow | **blocked** — needs a dedicated token and repo names |
| 4 | Slack notification credential, approved channel, reviewed output only | **not started** |
| 5 | Monitor-only workflows: uptime, SSL, backup freshness, capacity | **not started in n8n** |
| 6 | NEXONE authentication review before any connection | **not started** |
| 7 | Notion + support intake, after allowlist/audience/retention policy | **not started** |
| 8 | AI, last, with separate API project and budget cap | **deferred by design** |

Do not confuse #4 with `/daily`: that command reads Slack **into Telegram** via
the harness. Item #4 is the opposite direction — n8n notifying Slack.
`/ops` covers three of the four monitors in #5 but deterministically in the
harness, not as n8n workflows, and uptime and SSL are not covered at all.

**Standing constraints while no workflow is active:** no GitHub/Slack/Notion/
NEXONE ingestion, no n8n-generated report/alert/ticket/response, **no Telegram
webhook in n8n** (the bot keeps sole long-poll ownership), and no deploy, DNS,
billing, shell, SSH, filesystem or custom-code action from n8n. Enforced in
`ops/n8n/compose.yaml`: `code`, `executeCommand`, `readWriteFile` and `ssh`
nodes excluded, community packages off, public API off.

Per-workflow protocol: one at a time, synthetic data first, a dedicated
least-privilege credential per integration, tested from manual run through
notification delivery, then **explicit owner approval** before any schedule or
webhook is enabled.

### Known gap

`/var/backups/nexora-operations/<stamp>/` holds `database.dump`,
`n8n-data.tar.gz` and `stack.env` **unencrypted**, and `stack.env` contains
`N8N_ENCRYPTION_KEY` and `POSTGRES_PASSWORD` — the key sits beside the data it
protects. Permissions are `0600` root-only so it is contained today, but the
plan requires encrypted, restore-tested backups, and off-host backup is still
pending. Restore has never been tested.

Egress is **not** restricted to an endpoint allowlist as the plan requires;
only `N8N_SSRF_PROTECTION_ENABLED` is set, which is not the same thing.

## 9. Credentials

Three have passed through chat transcripts and **await rotation** (the owner
deferred it on 2026-09-17): the VPS root password, the `agents.nexoratech.co`
Basic Auth for user `imam`, and the n8n owner account password.

Do not ask for a new credential in chat. Have the owner paste it into
`/home/ahagent/AI-Workspace/.env` on the server. `SLACK_BOT_TOKEN` is the one
currently missing; its channel id is already set and is not a secret.

## 10. Reports

`agents/reports/` holds the detail behind everything above, with the exact
commands, measurements and rollback for each change:

- `2026-09-17-cloud-ops-nginx-ratelimit-fix.md` — the outage, all five causes
- `2026-09-17-weekly-report-and-help-coverage.md` — `/weekly`, `/help`,
  permissions, scheduling
- `2026-09-17-slack-daily-updates-capability.md` — `/daily` and why it is not
  an agent task
- `2026-09-18-sprint2-3-reconciliation-nexone-notion.md` — the §11 SOP, run once
- `2026-09-19-widget-fase6-academy-firstaccess-collector.md` — widget Fase 6
- `2026-09-19-telegram-channel-claude-code-chat.md` — Channels, the two-bot split
- `2026-09-19-asknexai-assistant-and-github-pr-flow.md` — read-only assistant,
  the branch→PR→approve chain, and the end-to-end run that proved it

Reader-facing documents live in `docs/`, not here: `nexora-platform-e2e.md` is the
full platform documentation and `nexora-ringkasan-eksekutif.md` its non-technical
summary. Both are **living documents** — undated filenames, a "Terakhir diperbarui"
line inside, updated in place rather than re-issued per date. Update them before
sending: they were renamed from dated names on 2026-09-20 precisely because a dated
copy invites sending a stale one. `bin/md2pdf.py`
renders either to PDF with **no dependencies** — this host has no pandoc,
weasyprint or reportlab, and installing one on a shared VPS for a recurring
summary costs more than the 300 lines it replaces. Deliverables are staged in
`output/<date>/` and sent with `tgfiles.send_document`, which refuses anything
outside the workspace or anything that looks like a secret.

## 11. Sprint report / daily update reconciliation (owner SOP)

When the owner asks for anything about a **sprint report**, **daily update**, or
**weekly report**, process it with this exact flow. It is an **orchestrator-session
capability**, not a headless-agent task: it needs the session's Slack/Notion MCP
connectors, Playwright, and the NEXONE login. A `claude -p` agent has none of these
(`AGENTS.md`), so never dispatch it as an agent run.

1. **Slack** — read `#daily-updates` (`C0BPCCAQ8KC`) and `#developments`
   (`C0C027W19DE`), **last 2 weeks**, via the session's Slack connector (not the
   harness — `SLACK_BOT_TOKEN` is still unset). `#developments` is mostly GitHub +
   integration-bot signal; group and attribute, do not paraphrase into invented status.
2. **Reconcile** the attached file/MoM against **live NEXONE** and dedup. A `200`/an
   existing card is not proof — check the real task, project, and status.
3. **NEXONE via Playwright** (owner preference — drive the live UI, not raw API):
   - Login form is duplicated (responsive) → target `:visible`. Token lives in
     **sessionStorage**, so `storageState` won't persist a session — log in per script.
   - "Internal Project" is a **module**, not one project. Put each task in its correct
     **product project** ("sesuaikan seperti yg sudah ada"). "Sprint" is the task
     **`category`** field; Kanban status = per-project **columns**.
   - Link tasks to a sprint through the **Sprints module** ("Add tasks" picker: pick
     project → search → check → "Add N task").
   - **Unlink from the sprint before deleting a task** — delete does **not** cascade the
     SprintTask link and leaves orphan rows (only the API `DELETE
     /internal-projects/sprints/{sid}/tasks/{taskId}` clears those). Better: create in
     the right project first so no move/delete is needed.
   - **Never touch Sprint 1** unless told. OneAlpha-v2 / rebuild work → project
     **`OneAlpha - Superapp`** (id 26). Full API/UI map: `agents/reports/` +
     the `nexone-api-map` memory. Reverse-engineered REST is a **fallback only**, and
     only when browser automation is unavailable — say so and confirm first.
4. **Notion** — *check the block quota first:* since 2026-09-19 the workspace has
   **used all its free blocks**, so `notion-create-pages` fails for any page, even a
   one-block one (verified — it is not a size problem). Say so up front and stage the
   content in a file instead of composing and then discovering it. Reads still work.
   Once there is room: create the report page in the **Doc Hub** database
   (`collection://3cee4d6d-1d64-80b8-9ee2-000b45368095`) following the
   "Nexora August Sprint-1 Report" pattern (`Kategori=["Guideline Docs and Reports"]`,
   `Sumber="Manual"`), then add its link under the **Reports** section of
   "Guideline, Manual Book, Reports Docs".
5. **Telegram** — notify the owner (chat `6687943152`). Token is in
   `/home/ahagent/AI-Workspace/.env`, but `state.WORKSPACE` resolves to
   `/root/AI-Workspace`, so `tgcore.token()` cannot find it — read that `.env` path
   directly and send via `urllib` (or fix `state.WORKSPACE`).
6. **Report** — write an `agents/reports/<date>-…md` change record: every task id
   created/changed and the rollback.

Confirm placement/scope when genuinely ambiguous — these are production,
Director-visible writes. Precedent run: `agents/reports/2026-09-18-sprint2-3-reconciliation-nexone-notion.md`.

### Scheduled reminders
Two `ahagent` user timers send a **Telegram reminder only** and then stop — they do
**not** write to NEXONE/Notion, and cannot: an unattended timer has no Slack token
(harness `SLACK_BOT_TOKEN` is unset), no MCP, and no browser. The reminder nudges the
owner; the actual Slack-read + reconciliation + Notion + report runs in the
**orchestrator session** when the owner asks (the SOP above). Both run
`bin/sprint_reminder.py {daily|weekly}` and load `.env` via `EnvironmentFile`.

- `ah-sprint-daily.timer` — **Mon–Thu 07:00 WIB** → daily-update reminder.
- `ah-sprint-weekly.timer` — **Fri 07:00 WIB** → sprint + weekly report reminder.

(Friday is covered by the weekly one, so the daily timer skips Fri to avoid a double
ping.) Inspect/restart like any user unit (section 2); to widen the daily cadence to
all seven days, change `OnCalendar` in `ah-sprint-daily.timer`.

## 12. AI Assistant widget + feedback collector

`docs/ai-assistant-widget-rollout-plan.md` is the rollout plan;
`docs/widget-readiness-ai-assistant.md` is the widget's own citation doc (reconstructed
2026-09-18 — the original was never found anywhere, despite three knowledge intents
citing it). Rollout order per owner: **accreditation first (self-knowledge, feedback
collector), then academy. Service-desk is deferred — not touched.**

**Feedback collector** — `ops/feedback/collector.py`, a standalone stdlib
`ThreadingHTTPServer` on `127.0.0.1:7788`, unit `ah-feedback` (same hardening as
`ah-dashboard.service`: `NoNewPrivileges`, `PrivateTmp`, `ProtectSystem=full`).
**Not** part of `bin/lib/dash.py` — that's the control-plane that spawns agent
processes; this is passive browser ingest and must stay separate. Append-only NDJSON,
one file per app per UTC day, under `/var/lib/nexora-feedback/<app>/`, `fsync()`'d per
line, `0640 ahagent:ahagent`. `remote_user` and `received_at` are server-asserted —
never trust what a client sends for either. Nginx: one additive `location ^~
/widget-feedback/` block in `agents.nexoratech.co.conf`, same `.prototypes.htpasswd`,
all 6 headers restated (an `add_header` anywhere in a location replaces the whole
inherited set). `ah feedback [app] [--since DAYS]` summarizes questions, findings, and
— the actual point — **`CLARIFICATION_NEEDED` counts, which are the knowledge base's
gap list**. `ah-feedback-digest.timer` sends a read-only weekly summary to Telegram,
Fri 07:30 WIB (30 min after `ah-sprint-weekly`, same offset trick, same reason).

**Widget-side identity + collector** live in the accreditation repo
(`nexaccred-react/src/widget/{identity,collector}.js`), hooked into `store.js`'s
single `appendEvent()` funnel — nothing else in the widget talks to the network.
Outbox buffers in `localStorage` and retries on a 5s timer + `sendBeacon` on
`pagehide`; **never `console.error`s**, since academy's 92-test suite fails the whole
run on one console error once the widget ships there too. `FEEDBACK_APP` in
`version.js` is the ops-level app name (`accreditation`) — **not** the same namespace
as `PROJECT_ID` (`nexaccred`, the widget's own localStorage/context key). Mixing these
up sends data to the wrong NDJSON directory silently; this happened once already
during Fase 1 and was caught by checking the actual file path, not by inspecting logs.

**Academy** (`/academy/`) carries the same widget since 2026-09-18, via a vanilla
DOM shell (`widget/core/rr-vanilla.js`) in its own shadow root — the bundle is a
closed IIFE with zero globals, so there is no React to reuse. Two facts that cost
real time, both now proven by measurement:

- **Academy has no class-based active-nav signal.** Every `aside nav button` has an
  identical `className` that never changes on navigation, no `aria-current`, no
  `data-*`. The real signal is the **inline style** (`background-color: transparent`
  = inactive). The rollout plan §5.1 claims otherwise and is wrong; reading a class
  would silently always report the first menu item, and no existing test catches it.
- **A failed collector request is logged to the console by the BROWSER**, before any
  JS sees it — no try/catch suppresses it. Injecting the widget with a POST to a
  non-existent collector turned academy's 92 Playwright tests into 36 failures. Hence
  `collectorEnabled`: queue to localStorage everywhere, transmit only where a
  collector exists (academy checks `location.pathname.startsWith('/academy/')`), plus
  backoff after 3 consecutive failures.

Academy injection is **append-only at publish time**: `ops/prototypes/refresh.sh`
calls `build-academy-widget.sh`, which esbuilds `widget/main.js` into one inline
non-module IIFE (ES modules don't load over `file://`, and README-HANDOFF.md's
double-click flow is load-bearing) and inserts it between `</script>` and `</body>`.
`lsp-unified-app.html` in git is **never** modified — that repo's AGENTS.md forbids
refactoring the bundle. Gate before and after any academy change:
`./run-tests.sh` must be **92/92**, and the published bytes should sha256-match what
you tested.

**The widget tree is in git since 2026-09-19.** `NexoraTechTeam/academy` **#2**
(20 files) and `NexoraTechTeam/accreditation` **#1** (30 files) were gated, verified
sha256-identical to the tested tree, and **merged to `dev`** on the owner's Telegram
approval. The live site is reproducible from git again and `refresh.sh` is safe.

One loose end: `/opt/nexora-prototypes/src/{academy,accreditation}` still shows those
files as dirty/untracked, because the commits were made from clones under `projects/`.
Every one of them was verified byte-identical to `origin/dev`, so nothing is at risk —
`git reset --hard origin/dev` there (or the next `refresh.sh`, which does it anyway)
cleans it up. The auto-mode classifier refuses that command as a production deploy, so
the owner runs it.

A manual publish (`build:standalone` + copy to `/var/www/prototypes/<app>/`) bypasses
`refresh.sh`'s git pull and reintroduces the exact "live ≠ what git can reproduce"
defect Fase 0 fixed. Every manual publish must snapshot the current live
tree to `/var/backups/accreditation/` (or `/var/backups/academy/`) first
(`refresh.sh`'s own `publish()` deletes the previous tree with no retained backup),
and the report must say so plainly rather than implying the site is
git-reproducible when it is not. This also covered academy's entire
`widget/` directory, which existed only as untracked local files — it survives
`refresh.sh` (`git reset --hard` leaves untracked files alone) but **not** a fresh
clone of the repo.

### Update 2026-09-19 — first-access, Fase 6 intelligence, collector, and the git-push wall

Live now on both apps (manual publish, owner-approved, backed up; report
`agents/reports/2026-09-19-widget-fase6-academy-firstaccess-collector.md`):

- **Academy shows the AI Assistant from first access.** `academy/widget/main.js` no longer
  tears the widget down on the signed-out landing page — it mounts once and stays (shadow root →
  still **0 `aside nav button`**, so the 92-suite landing DOM is unchanged). Gate:
  `academy/tests/test_widget_presence.py` (skips on the un-injected committed file, asserts the
  landing FAB on the injected build). Injected suite **94/94**; default `run-tests.sh` still 92+2skip.
- **Accreditation "kecerdasan penuh" (Fase 6 interactivity).** New pure `src/widget/core/guidance.js`
  (`screenSuggestions`/`buildTour`/`gateGuidance`) + `AREA_GUIDE` in `app.config.js` (each of the 9
  review areas → a real screen route + a **KB-answerable** prompt; `SCREEN_LABELS` moved here from
  `contextAdapter.js`). `ReadinessWidget.jsx` gained screen-aware Ask chips, a guided per-area tour
  (answer-driven navigation via a new `onNavigate` prop = host `navigate`), and a guiding gate
  (jump-to-screen + the exact `signOff()` refusal string). Gate `guidance.smoke.mjs` **44/44** (every
  route real, **every prompt ANSWERED_FROM_SOURCE** — the anti-mismatch guarantee); added to `test:widget`.
- **Collector hardened.** `ops/feedback/collector.py` `_send_json` swallows
  `BrokenPipeError`/`ConnectionResetError` (client hangup after `store.append()` already persisted =
  lossless; was journal noise). `ops/feedback/tests` **29/29**; `ah-feedback` restarted, healthz 200.

**Two walls learned the hard way (see memories `github-connector-readonly`, `prototype-e2e-cors-ipv6-blocker`):**

- **The claude.ai GitHub connector is READ-ONLY here.** It authenticates as the owner and reads fine,
  but `create_branch`/`create_or_update_file` return `403 Resource not accessible by integration`. That is
  still true — write through `bin/lib/ghflow.py` and the `.env` PATs (§14), never through the connector.
  `refresh.sh` is safe again now that both PRs merged; before that it would have wiped the only copy.
  The rule generalises: **check whether the publishing tree holds anything git does not** before
  running it, because `git reset --hard origin/dev` answers that question destructively.
- **`nexaccred-react` backend e2e (`roles`/`readiness-visibility`) is unrunnable here.** The API is
  IPv4-only (`127.0.0.1:3001`) but the browser resolves `localhost`→IPv6, and pointing at `127.0.0.1`
  trips the API's CORS (only `localhost:5173` allowed) → login never completes → every nav test times out.
  Purely environmental. Verify widget work via `test:widget` + `test:vanilla-shell` + a headless probe of
  the **published standalone PRE-LOGIN** (FAB + engine are client-side), as this session and the prior fases did.

**KB coverage (2026-09-19b).** A reviewer asking "Ada menu/modul apa saja?" got
`CLARIFICATION_NEEDED`; real collector data showed **7 unanswered vs 1 answered**. Two structural
causes: academy generated **no per-module rules** (accreditation has one per screen), and "modul"/
"fitur" were keywords nowhere. Fixed in the **generators** (`widget/gen-knowledge.mjs`,
`scripts/gen-knowledge.mjs`) — academy 43→84 rules. Measure with a realistic question battery:
academy 63%→100%, accreditation 92%→100%, with the regression smokes green so a closed gap doesn't
become a mismatch. The collector now also records the **question text** (`store.js`,
`MAX_RECORDED_TEXT=500`) so `ah feedback` prints the real KB backlog instead of a bare count — that
is what the widget's transparency notice already promised. A real LLM behind the widget stays
**deferred by owner decision**; if it is ever approved, use a **same-origin `/widget-ai/` proxy**
(no CSP change needed — the plan's CSP objection only applies to calling the model from the browser).

## 13. Two bots, two jobs — do not confuse them

| Bot | Unit | Audience | Can it change anything? |
|---|---|---|---|
| `@AskNexAIBot` | `ah-channel-telegram` | **non-developers** (manajemen, asesor) asking about NexAccred and DeAcademy | **No.** Read-only by construction |
| `@AgentNexoraBot` | `ah-telegram` | the owner | Yes — development work, and GitHub through §14 |

**The AI Assistant *widget* inside accreditation/academy uses neither**, and has no
model at all: it is a generated rule base (§12). If someone asks "which bot does the
widget use", the answer is none.

`@AskNexAIBot` bridges Telegram into a live Claude Code session via the official
`telegram@claude-plugins-official` channel plugin. Runbook and rollback:
`ops/channels/README.md`; decision records
`agents/reports/2026-09-19-telegram-channel-claude-code-chat.md` and
`agents/reports/2026-09-19-asknexai-assistant-and-github-pr-flow.md`.

Since 2026-09-19 that session runs **`--permission-mode auto` in `~/ask-nexai`**,
which is safe only because `ops/channels/asknexai-settings.json` denies everything
that could change state: all of `Bash`, `Write`, `Edit`, `WebFetch`, `WebSearch`,
`Task`, every Slack/Notion/Linear/GitHub connector, and reads of `.env`, `~/.claude`,
`~/.ssh`, `/root`, `/etc`, `/var` and this workspace. Deny wins in every mode —
measured, not assumed. Auto mode is the *point*: a non-technical user must never be
handed an Approve/Deny button, because the channel plugin would relay one and they
have no basis to judge it.

Its persona lives in `~/ask-nexai/CLAUDE.md` (Bahasa Indonesia, short, no technical
detail, honest when the docs do not cover something). Changing `WorkingDirectory`
for an unattended session means **pre-trusting the new directory** in
`~/.claude.json` — otherwise it stops at "Do you trust this folder?" and Telegram
just goes quiet.

`Restart=always` (not `on-failure`: `/exit` exits 0), capped by
`StartLimitBurst=5`/`StartLimitIntervalSec=300`, and `bin/channel_notify.py` sends
🔴/🟢 to the channel allowlist from `ExecStopPost`/`ExecStartPost` so a dead bridge
is never mistaken for a slow answer.

Three rules, each learned by measurement:

- **Two bots, two tokens, two files.** One `getUpdates` consumer per token, so the
  channel's token lives *only* in `~/.claude/channels/telegram/.env` (`0600`).
  `@AgentNexoraBot`'s stays in the workspace `.env`, owned by `ah-telegram`.
- **Never give this session the workspace `.env`.** It contributes exactly two
  variables and both break it: `TELEGRAM_BOT_TOKEN` → HTTP 409 on both bots, and
  `CLAUDE_CODE_OAUTH_TOKEN` → silently downgrades the session from the claude.ai
  Team login to the limited-scope API token. The unit has no `EnvironmentFile` by
  design. Check the header: it must read `Claude Team`, not `Claude API`.
- **Blast radius is real.** An allowlisted sender drives a session with read/write
  on this production VPS plus Slack/Notion/Linear/GitHub over MCP, and can approve
  its tool calls. `dmPolicy=allowlist` is mandatory — the default `pairing` policy
  hands a pairing code to any stranger who finds the username.

## 14. GitHub writes — branch, PR to dev, merge only on a Telegram tap

The owner's rule, 2026-09-19: *commit+push ke branch baru, PR hanya ke `dev`, merge
hanya setelah owner approve lewat Telegram.* `bin/lib/ghflow.py` is the single place
it is expressed; `bin/lib/tggh.py` is how it looks in chat (`/push <task> <org/repo>`,
`/pr`, `/prs`, `/merge` with ✅/✖️ buttons). Orgs are limited to `Nexora-Tech-Team`
and `NexoraTechTeam`.

Facts that will bite if forgotten:

- **`pushgate` no longer pushes to dev or staging.** That rule was replaced, and its
  test file was rewritten to assert the opposite of what it used to. Work reaches dev
  as a reviewed PR or not at all; `protect.sh` now lists `dev` as protected too.
- **An approval is bound to the head SHA** the owner was shown, so a PR that changes
  after the tap needs a fresh approval. The button carries a short staged token, not
  the repo name — Telegram caps `callback_data` at 64 bytes.
- **The button re-checks the tapper's role.** A message can be tapped by anyone it
  reaches, so `/merge`'s owner check is not enough on its own.
- **Agents may `git add`/`git commit`, never publish.** `git push`, `gh`,
  `git remote set-url`, `git config` and reads of `**/.git/config` are denied in
  `ops/harness/claude-settings.json`. `~/.gitconfig` gives commits a machine identity
  ("Nexora Agent Harness"); without it an agent's commit fails and `/push` would
  quietly publish an older HEAD. `pushgate.plan()` refuses a dirty worktree for the
  same reason.
- **Never let a token into `.git/config`.** `git clone` with a credentialed URL
  writes it there; `projects/` was cleaned immediately after cloning. `ghflow` builds
  the push URL in memory and redacts it from every output.
- **Two tokens, and sending the wrong one looks like a broken token.** A
  fine-grained PAT serves one resource owner, and there are two here:
  `GITHUB_ORGS_PAT` writes to the organisation `NexoraTechTeam`, `GITHUB_PAT`
  writes to the personal account `Nexora-Tech-Team`, and each gets
  `403 "Resource not accessible by personal access token"` on the other's repos.
  `ghflow.token(repo)` routes by owner (`GITHUB_PAT_<OWNER>` override →
  `GITHUB_ORGS_PAT` for `ORG_OWNERS` → `GITHUB_PAT`). Both verified writable on
  2026-09-19 with `git push --dry-run` and a PR-create probe that creates nothing.
- **Probe write permission without writing.** `git push --dry-run` and a
  `POST /pulls` with a nonexistent head (422 = allowed, 403 = not) both answer the
  question while leaving the repo untouched. `GET /repos` reporting
  `"push": true` does **not** — that is the account's role, not the token's scope.

Plain text (no slash) sent to `@AgentNexoraBot` is now a development request
(`bin/lib/tgchat.py`, owner-only, last 4 turns replayed for context) instead of being
silently dropped. It spawns the same `jobs.spawn()` agent with the same narrow
permissions — free-form input, not free-form authority.


## 15. Monitoring — Prometheus now, Grafana when a token lands

The observability stack runs on this very host and the harness ignored it for
weeks: **Grafana 13.2 on :3000, Prometheus on :9090, Loki on :3100**, fronted by
`monitoring.nexoratech.co`. §8 item #5 still called uptime and SSL "not covered
at all"; they were being scraped the whole time by 17 blackbox probes nobody
read.

`bin/lib/metrics.py` + `/monitor` (viewer level) now report uptime, SSL expiry,
disk, memory and scrape health. Facts worth keeping:

- **Prometheus needs no credential; Grafana does.** Every number in `/monitor`
  comes from Prometheus, so the feature works today. Grafana is consulted only
  for what only it knows — dashboards and its own alert rules — via
  `GRAFANA_TOKEN` (a service-account token, Administration → Service accounts).
  Without it the report says so instead of pretending.
- **Prometheus has zero alert rules.** Alerting lives in Grafana, so alert state
  is unreadable until that token exists.
- **Unreachable is not healthy.** `metrics.render` prints "status tidak
  diketahui" when the query fails. A monitor whose failure mode is a green tick
  is worse than no monitor.
- **Instance labels are prose**, not hostnames: `Server Production
  audit-q.cbqaglobal.co.id (148.230.96.117)`, `Server Development OneAlpha`.
  `_short_host` strips the environment word as a class — matching the literal
  "Server Production" left every Development host unshortened.
- Thresholds are deliberately quiet: SSL 21 days, disk 85%, memory 90%. One host
  sat at 84.2% on 2026-09-21, i.e. the disk warning is close to real.
- Read-only, always. The monitoring stack belongs to a shared vhost (§1); the
  harness is a reader there, never an author.
