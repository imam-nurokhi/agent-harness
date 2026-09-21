# Telegram channel — a real Claude Code session in Telegram

Status on 2026-09-19: **live, verified and reboot-safe.** `@AskNexAIBot` is
paired to the owner's chat and bridged to a Claude Code session on this host,
supervised by the `ah-channel-telegram` user unit — see
[Keeping it alive](#keeping-it-alive).

Since 2026-09-19 it is the **AI Assistant for NexAccred and DeAcademy**: read-only,
auto mode, answering non-developers in plain Indonesian.

```
Claude Code v2.1.278 · Sonnet 5 · Claude Team · ~/ask-nexai
▎ Channels: plugin:telegram@claude-plugins-official injects into this session
⏵⏵ auto mode on  (read-only: asknexai-settings.json)
access.json: dmPolicy=allowlist, allowFrom=[6687943152]
tmux session: tgchannel (ahagent), owned by ah-channel-telegram.service
```

Reattach with `sudo -u ahagent -H tmux attach -t tgchannel`, and leave with
`Ctrl-b` then `d`. Typing `exit`, `Ctrl-D` or `/exit` in that pane ends the
session — the unit restarts it within ~10s and Telegram gets a 🔴 then a 🟢.
Closing the terminal tab does nothing.

## What this is, and why it is not the existing bot

`@AgentNexoraBot` (`bin/lib/tgbot.py`, unit `ah-telegram`) is a deterministic
command surface: 39 slash commands, no model in the loop, plain text silently
ignored (`tgbot.py:150`). Free-form question answering there means `/ask <role>
<text>`, which spawns a one-shot headless `claude -p` agent with the narrow
`ops/harness/claude-settings.json` allowlist — no memory between messages, no
MCP, no Slack/Notion/NEXONE, and the answer arrives later as a one-line
notification rather than a reply.

**Channels** is Claude Code's own feature for this. A channel plugin is an MCP
server that pushes inbound chat messages into an already-running Claude Code
session, and Claude replies back out through the same plugin. The session is a
full one: this workspace's files, `CLAUDE.md`, memory, skills, subagents, and
every MCP connector the session has (Slack, Notion, Linear, GitHub, Context7).
That is the capability `/ask` structurally cannot reach.

Feature is a **research preview**. `--channels` works but is deliberately absent
from `claude --help`, and the flag syntax may change.

- Docs: <https://code.claude.com/docs/en/channels>
- Plugin source: <https://github.com/anthropics/claude-plugins-official/tree/main/external_plugins/telegram>

## Verified on this host

| Check | Result |
|---|---|
| `claude` version | 2.1.278 (root), **2.1.273** (`ahagent`, `~/.local/bin/claude`) |
| `--channels` flag | present on both builds (errors with "argument missing", not "unknown option") |
| Bun runtime | **installed 2026-09-19** — `1.4.2` at `/home/ahagent/.bun/bin/bun`, user-scoped, nothing host-wide |
| Marketplace | **added 2026-09-19** for `ahagent` — `claude-plugins-official`, cloned to `~/.claude/plugins/marketplaces/` |
| Plugin install | **done** — `telegram@claude-plugins-official` v0.0.7, user scope, enabled |
| Permission relay | **supported** by the plugin (`server.ts:398-448`, `:735-783`) |
| `tmux` / `screen` | both present |
| Outbound network | fine; channels open **no inbound port** |

### Permission relay is the reason this is worth doing

`CLAUDE.md` §4 records that headless agents cannot be approved — a permission
prompt in a `claude -p` run has nobody to answer it. This plugin declares
`claude/channel/permission` and forwards prompts to Telegram as a message with
inline Approve/Deny buttons, and also accepts a typed `yes <code>` / `no <code>`
reply. So a session driven from Telegram **can** be approved, and does not need
`--dangerously-skip-permissions` on this shared host.

Note the flip side, from the docs: anyone on the allowlist can approve tool use
in the session. Allowlist only people trusted with that authority.

## The trap that will break the existing bot

`server.ts:33-44` loads `~/.claude/channels/telegram/.env` but lets the **real
environment win** (`if (m && process.env[m[1]] === undefined)`).

The workspace `.env` already defines `TELEGRAM_BOT_TOKEN` — `@AgentNexoraBot`,
which `ah-telegram` long-polls. Telegram allows exactly one `getUpdates`
consumer per token. So a channel session that inherits that variable starts a
second consumer and both bots begin failing with **HTTP 409 Conflict**.

Two consequences, both load-bearing:

1. **Use a second bot.** `@AskNexAIBot` was created for the channel on
   2026-09-19. `@AgentNexoraBot` keeps its 39 commands untouched, so a failed
   experiment breaks nothing.
2. **Never source the workspace `.env` for this session.** Dropping just this
   one variable is not enough — `CLAUDE_CODE_OAUTH_TOKEN` in the same file
   causes a second, quieter fault. See
   [The workspace `.env` is poison here](#the-workspace-env-is-poison-here).

### Where the channel token goes — and why not the workspace `.env`

`@AskNexAIBot`'s token belongs in **`/home/ahagent/.claude/channels/telegram/.env`**
as `TELEGRAM_BOT_TOKEN`, not in the workspace `.env`.

An earlier draft of this file said to add `TELEGRAM_CHANNEL_BOT_TOKEN` to the
workspace `.env` instead. That was worse on both counts: the plugin does not
read that name, so it would need a mapping at launch, and it puts two live bot
tokens in one file where a copy-paste slip swaps them. Keeping each token in the
file its own process reads means the channel session can ignore the workspace
`.env` entirely — which is what it must do anyway.

The directory was pre-created `0700 ahagent:ahagent` on 2026-09-19. The file
itself must be `0600`:

```sh
# run on the server, NOT through a chat session — CLAUDE.md §9
sudo -u ahagent tee /home/ahagent/.claude/channels/telegram/.env >/dev/null <<'EOF'
TELEGRAM_BOT_TOKEN=<token-from-botfather>
EOF
sudo -u ahagent chmod 600 /home/ahagent/.claude/channels/telegram/.env
```

`/telegram:configure <token>` from inside a session writes the same file, but it
puts the token in the session transcript. Writing the file directly avoids that.

## Blockers — all cleared 2026-09-19

1. ~~**Team-plan admin toggle.**~~ **Done.** The Owner enabled claude.ai → Admin
   settings → Claude Code → **Channels**. Proof is negative and easy to miss:
   the startup notice names the plugin with **no warning line under it**. With
   the toggle off, the MCP server still connects and its tools still work, but
   no message is ever delivered — so "the plugin loaded" is not evidence.
2. ~~**`@AskNexAIBot`'s token.**~~ **Done.** In
   `/home/ahagent/.claude/channels/telegram/.env`, `0600 ahagent:ahagent`,
   distinct from `@AgentNexoraBot`'s. Never passed through a chat transcript.
3. ~~**Plugin install.**~~ **Done** — `telegram@claude-plugins-official` v0.0.7,
   user scope, enabled. The owner ran it after the classifier refused it.

Still refused, and still not needed for the bridge to work:

- Writing/installing the **systemd unit** (`Create Unsafe Agents`), and
  **launching the session** (same). Every launch in this setup was therefore
  typed by the assistant and submitted by the owner. The unit is documented
  below as a code block only.

### An auth step nobody predicted

`ahagent` had never run Claude Code interactively, so the first launch dropped
into the onboarding wizard and then an **OAuth browser flow** — the harness's
`CLAUDE_CODE_OAUTH_TOKEN` is not sufficient for an interactive session. The
owner completed a full-scope login as `imam.nurokhi@nexoratech.co`.

Two consequences:

- A full-scope claude.ai session credential for the owner's account now sits in
  `ahagent`'s home on this **shared** VPS. Broader than the token that was there
  before. Accepted knowingly; worth re-reading when access is reviewed.
- **Remote Control is no longer blocked.** Its only obstacle here was that
  limited-scope token. It now needs just the Owner toggle in admin settings.

### tmux sockets are per user

`tmux attach -t tgchannel` as `root` answers `no session` — root's server is
`/tmp/tmux-0/default` and the session belongs to `ahagent`. Use
`sudo -u ahagent -H tmux attach -t tgchannel`, or `sudo -iu ahagent` first.

## Setup, once the blockers clear

Run as `ahagent`, from `/home/ahagent/AI-Workspace`.

```sh
sudo -u ahagent -H bash -lc '
  export PATH=$HOME/.bun/bin:$PATH
  cd /home/ahagent/AI-Workspace
  claude plugin install telegram@claude-plugins-official --scope user
'
```

With the token already in `~/.claude/channels/telegram/.env`, no
`/telegram:configure` step is needed. Start the session with the channel on,
inside tmux so it survives an SSH disconnect:

```sh
sudo -u ahagent -H bash -lc '
  export PATH=$HOME/.bun/bin:$PATH
  cd /home/ahagent/AI-Workspace
  tmux new -s tgchannel "claude --channels plugin:telegram@claude-plugins-official"
'
```

Watch the startup notice. It should say messages from
`plugin:telegram@claude-plugins-official` inject into this session. A warning
line under it names the problem instead — most likely the Team-plan
`channelsEnabled` toggle still being off.

Message `@AskNexAIBot` from Telegram; it replies with a 6-character pairing
code. Back in the session:

```
/telegram:access pair <code>
/telegram:access policy allowlist
```

`allowlist` is not optional here. The default `pairing` policy answers **any**
stranger who finds the bot username with a pairing code; `allowlist` drops
unknown senders silently. State lives in
`~/.claude/channels/telegram/access.json`, re-read per message, so changes need
no restart.

### Keeping it alive

The docs are explicit: the session must stay running, and to survive an SSH
disconnect it belongs in `tmux` or `screen`. A systemd user unit that wraps
tmux is the house style (`CLAUDE.md` §2).

**Installed and enabled 2026-09-19** as
`~/.config/systemd/user/ah-channel-telegram.service`. `Linger=yes` is already set
for `ahagent`, so the unit starts at boot without an active login session. Drive
it like any other user unit (§2):

```sh
export XDG_RUNTIME_DIR=/run/user/1004
sudo -u ahagent XDG_RUNTIME_DIR=$XDG_RUNTIME_DIR systemctl --user status ah-channel-telegram
```

Three things the install taught, all measured:

- **Kill the old tmux server before the first `start`.** `tmux new-session` talks
  to whatever server already owns `/tmp/tmux-1004/default`; if one exists, the
  command returns immediately without forking, and `Type=forking` then has no
  main process to adopt. `sudo -u ahagent -H tmux kill-server` first.
- **`ExecStartPre=-/usr/bin/tmux kill-session -t tgchannel`** (leading `-`, so a
  missing session is not a failure) makes `restart` idempotent.
- **The pane's own process lands in a sibling cgroup**, `tmux-spawn-<uuid>.scope`,
  not in the service cgroup — tmux 3.4+ does this deliberately. The unit's main
  PID is therefore the tmux *server*. `Restart=on-failure` caught a crash but not
  a clean `/exit`, which exits 0 — so the unit now uses `Restart=always`, which is
  exactly the case the owner asked to recover from.

Live unit (2026-09-19), reproduced here verbatim:

```ini
[Unit]
Description=AH Telegram channel — AI Assistant (@AskNexAIBot)
Documentation=https://code.claude.com/docs/en/channels
After=network-online.target
Wants=network-online.target
# Restart=always would otherwise loop forever on a broken config and notify on
# every cycle. Five tries in five minutes, then stay failed.
StartLimitIntervalSec=300
StartLimitBurst=5

[Service]
# Deliberately NO EnvironmentFile. The workspace .env contributes exactly two
# variables and this session must have neither — see "The workspace .env is
# poison here" below.
Type=forking
WorkingDirectory=/home/ahagent/ask-nexai
Environment=HOME=/home/ahagent
Environment=PATH=/home/ahagent/.bun/bin:/home/ahagent/.local/bin:/usr/local/bin:/usr/bin:/bin
ExecStartPre=-/usr/bin/tmux kill-session -t tgchannel
ExecStart=/usr/bin/tmux new-session -d -s tgchannel -x 200 -y 50 -c /home/ahagent/ask-nexai \
claude --channels plugin:telegram@claude-plugins-official \
--permission-mode auto \
--settings /home/ahagent/AI-Workspace/ops/channels/asknexai-settings.json \
--add-dir /opt/nexora-prototypes/src/accreditation /opt/nexora-prototypes/src/academy
ExecStartPost=-/usr/bin/python3 /home/ahagent/AI-Workspace/bin/channel_notify.py up
ExecStop=/usr/bin/tmux kill-session -t tgchannel
ExecStopPost=-/usr/bin/python3 /home/ahagent/AI-Workspace/bin/channel_notify.py down
Restart=always
RestartSec=10

[Install]
WantedBy=default.target
```

Three things in that unit are load-bearing:

- **`--add-dir` is variadic**, so it must be last. Put a prompt or another flag
  after it and the flag is swallowed as a directory name — which is how an
  earlier probe failed with "Input must be provided either through stdin or as a
  prompt argument".
- **`--permission-mode auto` is safe only with the settings file.** See
  [The assistant is read-only](#the-assistant-is-read-only).
- **A new `WorkingDirectory` must be pre-trusted.** Claude Code asks "Do you trust
  this folder?" on first use of a directory, and an unattended session simply
  stops there: unit `active`, tmux alive, Telegram silent. Add the directory to
  `projects` in `~/.claude.json` with `hasTrustDialogAccepted: true` before
  starting. Do not answer the dialog by sending keys into the pane.

### The assistant is read-only

`@AskNexAIBot` answers accreditation and academy questions for **non-developers**.
They must never see an Approve/Deny button — the channel plugin relays permission
prompts to Telegram, and a manager has no basis to judge one. So the session runs
in auto mode with `ops/channels/asknexai-settings.json`, where `deny` (which wins
in every mode) removes everything that could act: all `Bash`, `Write`, `Edit`,
`WebFetch`, `WebSearch`, `Task`, every Slack/Notion/Linear/GitHub connector, and
reads of `.env`, `~/.claude`, `~/.ssh`, `/root`, `/etc`, `/var` and the workspace.
`plugin:telegram` is *not* denied — it is how the bridge replies.

Measured on 2026-09-19, not assumed: asked to run `echo HALO` and write
`/tmp/bukti.txt`, the session answered that no shell or file-write tool exists in
it, and the file was never created.

The persona is `~/ask-nexai/CLAUDE.md`: Bahasa Indonesia, short enough for a
phone, no file names or code, honest when the product docs do not cover something,
and it points action requests at `@AgentNexoraBot`.

### It tells you when it dies

`bin/channel_notify.py up|down` runs from `ExecStartPost`/`ExecStopPost` and sends
🟢/🔴 to the channel allowlist. It reads the token from
`~/.claude/channels/telegram/.env` — never `bin/lib/tgcore.py`, which speaks for
the other bot — and exits 0 on every error path so a failed notice can never fail
the unit. Tests: `tests/test_channel_notify.py`.

### The workspace `.env` is poison here

An earlier draft of this unit had `EnvironmentFile=…/.env` plus
`UnsetEnvironment=TELEGRAM_BOT_TOKEN`. Both lines are gone, because the file
contributes only two variables and **this session must have neither**:

| Variable | Why it must not reach the channel session |
|---|---|
| `TELEGRAM_BOT_TOKEN` | `@AgentNexoraBot`'s token. Real env beats the plugin's own `.env` (`server.ts:40`), so the plugin would poll the wrong bot and knock both into HTTP 409. |
| `CLAUDE_CODE_OAUTH_TOKEN` | **Overrides the stored claude.ai login.** Measured 2026-09-19: with it, `claude auth status` reports `authMethod: oauth_token` and the header reads `Claude API`; without it, `authMethod: claude.ai`, `subscriptionType: team`, `orgName: NexoraTech`. The harness token is limited-scope — it is also why Remote Control was refused. |

So the rule is simply: **do not source `.env`** for this session. Verify before
launching, never after:

```sh
claude auth status | grep -E 'authMethod|subscriptionType'
# want: "claude.ai" and "team"
```

### The permission mode belongs on the command line

On 2026-09-19 the first launch drifted into **auto mode** by accident: the first
permission prompt offers `1. Yes` and `2. Yes, and switch to auto mode`, and a
stray Enter took option 2. The session then spent minutes approving its own tool
calls on a shared production host — a posture change nobody chose. The fix was to
pass the mode as a flag, so it is a launch decision rather than a keystroke away.

That reasoning still holds, and is why the *current* auto mode is not a
regression: it is declared on the command line and paired with a settings file
that leaves nothing dangerous to approve. `manual` protects a session that can
act; a read-only session has nothing to protect and would only hand a
non-technical user a button they cannot judge. **Never run auto mode here without
`--settings asknexai-settings.json`.**

## What to weigh before enabling

- **Blast radius.** An allowlisted sender steers a session with full read/write
  access to this production VPS and to Slack, Notion, Linear and GitHub through
  MCP. That is far more than `@AgentNexoraBot` can do, by design.
- **Transcript residency.** While a channel or Remote Control session is
  connected, the transcript is stored on Anthropic servers to keep devices in
  sync. Execution and filesystem access stay local.
- **Quota.** Every answer is a model call against the Team plan's usage. No
  separate bill; the plan limit is the limit.
- **Preview risk.** Flag syntax and protocol may change without notice.
- **Shared host.** Do not use `--dangerously-skip-permissions`
  (`CLAUDE.md` §6). Permission relay exists precisely so you do not have to.

## Remote Control — the alternative, and why it is parked

`claude remote-control` would give the same power from the Claude mobile app
instead of Telegram, plus push notifications. Two obstacles here:

- This host authenticates with `CLAUDE_CODE_OAUTH_TOKEN`. The docs are explicit
  that a `setup-token`/`CLAUDE_CODE_OAUTH_TOKEN` credential **cannot** establish
  Remote Control ("Remote Control requires a full-scope login token"); it needs
  an interactive `claude auth login`.
- On Team, an Owner must enable the Remote Control toggle first, and Trusted
  Devices may add a per-device enrolment step.

Worth revisiting after the channel works, since the admin toggle and the login
are the same class of action.
