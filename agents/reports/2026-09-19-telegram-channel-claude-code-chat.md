# 2026-09-19 — Free-form chat in Telegram: Channels, not a hand-built bot

**Asked:** can the owner just talk to `@AgentNexoraBot` and get answers, instead
of typing slash commands?

**Answered:** not today — and the right fix is a Claude Code feature that already
exists, not code written here.

**State: live, verified and reboot-safe.** `@AskNexAIBot` bridges Telegram to a
Claude Code session on this host — paired, allowlisted, manual permission mode, on
the Team subscription, and since 18:43 UTC supervised by the `ah-channel-telegram`
user unit (see §12). `@AgentNexoraBot` is untouched and still healthy: zero HTTP
409, all three user units `active`.

Runbook, verified facts and the full setup sequence: `ops/channels/README.md`.

---

## 1. Why plain text does nothing today

`bin/lib/tgbot.py:150`:

```python
if not chat_id or not text.startswith("/"):
    return
```

A message without a leading `/` never reaches the dispatcher. It is not denied
and not logged — it is dropped before any handler sees it.

The nearest existing capability is `/ask <role> <instruction>`, which takes
free-form language but is structurally not a conversation:

- `jobs.spawn()` starts a fresh detached `claude -p` per call — **no memory**
  between messages, so a follow-up question does not connect to the last answer.
- The reply is a job id. The real answer arrives later as a push notification
  containing **one line** (`tgwatch._outcome()` takes the `Scope done:` line);
  the rest needs `/tail` or `/log`.
- The agent runs under `ops/harness/claude-settings.json`: no `curl`/`wget`, no
  `.env`, **no MCP**. So Slack, Notion, NEXONE and the web are all out of reach,
  which is exactly the class of question worth asking from a phone.
- Owner-only, and refused outright when every engine is refused or out of quota.

## 2. What was proposed first, and why it was wrong

Two hand-built options were put to the owner: a keyword router (free, instant,
dumb) and a bot-side LLM loop with per-chat session memory (capable, costs
quota). The owner pushed back — *"Kamu yakin gaada cara lainnya yg jauh lebih
powerful namun gratis? Coba research dulu"* — and was right to. Both options
were designed from this repo's code without checking what Claude Code itself
ships. Research found two first-party features that beat both, for the same
quota and roughly an hour of setup instead of two days of code.

## 3. Channels — the answer

A channel plugin is an MCP server that pushes inbound chat messages into an
**already-running** Claude Code session; Claude replies back through the same
plugin. Telegram, Discord and iMessage plugins ship officially. The session is a
real one: this workspace's files, `CLAUDE.md`, memory, skills, subagents, and
every MCP connector — Slack, Notion, Linear, GitHub, Context7 — plus image
attachments sent from the phone.

Research preview: `--channels` works but is deliberately absent from
`claude --help`, and its syntax may change.

### Verified on this host (2026-09-19)

| Check | Result |
|---|---|
| `--channels` flag | present — 2.1.278 (root) and 2.1.273 (`ahagent`) both answer "argument missing", not "unknown option" |
| Bun | **installed**, `1.4.2` at `/home/ahagent/.bun/bin/bun`, user-scoped |
| Marketplace | **added** for `ahagent`: `claude-plugins-official` |
| Permission relay | **supported** — `server.ts:398` declares `claude/channel/permission`; `:429-448` formats the prompt; `:735-783` handles the inline buttons; `:93` accepts a typed `yes <code>` |
| `tmux` / `screen` | both present |
| Inbound ports | none — outbound HTTPS only |

### Permission relay retires a known trap

`CLAUDE.md` §4 records that headless agents cannot be approved. This plugin
forwards permission prompts to Telegram with Approve/Deny buttons, so a
Telegram-driven session **can** be approved and needs no
`--dangerously-skip-permissions` on this shared host. The flip side, from the
docs: anyone on the allowlist can approve tool use. Allowlist accordingly.

## 4. The trap that would have broken the live bot

`server.ts:33-44` loads `~/.claude/channels/telegram/.env` but lets the real
environment win:

```ts
if (m && process.env[m[1]] === undefined) process.env[m[1]] = m[2]
```

The workspace `.env` already sets `TELEGRAM_BOT_TOKEN` — `@AgentNexoraBot`,
long-polled by `ah-telegram`. Telegram permits one `getUpdates` consumer per
token, so a channel session inheriting that variable would start a second
consumer and knock both bots into **HTTP 409 Conflict**.

Mitigations, both required:

1. **A second bot** from BotFather for the channel — `@AskNexAIBot`, created by
   the owner on 2026-09-19. `@AgentNexoraBot` keeps its 39 commands, so a failed
   experiment breaks nothing.
2. **`UnsetEnvironment=TELEGRAM_BOT_TOKEN`** in any unit that loads the
   workspace `.env`; the channel's own token lives only in
   `~/.claude/channels/telegram/.env`.

The first draft of the runbook told the owner to add `TELEGRAM_CHANNEL_BOT_TOKEN`
to the workspace `.env`. Corrected the same day: the plugin does not read that
name, so it would have needed a launch-time mapping, and it would have put two
live bot tokens in one file. Each token now lives in the file its own process
reads, which is also what makes the `UnsetEnvironment` fallback work.

This was caught by reading `server.ts`, not by testing — no 409 was ever
triggered, and the live bot never went down.

## 5. What was changed on the host

Additive, user-scoped, reversible. Nothing host-wide, no service touched.

| Change | Path | Rollback |
|---|---|---|
| Bun runtime installed | `/home/ahagent/.bun/` (+ a PATH line in `~/.bashrc`) | `rm -rf /home/ahagent/.bun` and drop the `.bashrc` line |
| Plugin marketplace added for `ahagent` | `/home/ahagent/.claude/plugins/marketplaces/claude-plugins-official` | `claude plugin marketplace remove claude-plugins-official` |
| Channel state dir pre-created, `0700 ahagent:ahagent`, empty | `/home/ahagent/.claude/channels/telegram/` | `rm -rf /home/ahagent/.claude/channels` |
| Plugin installed, user scope | `telegram@claude-plugins-official` v0.0.7 | `claude plugin uninstall telegram@claude-plugins-official` |
| `@AskNexAIBot` token written by owner | `~/.claude/channels/telegram/.env`, `0600` | delete the file; revoke the bot in BotFather |
| Pairing + allowlist | `~/.claude/channels/telegram/access.json` | delete the file (re-pairing then required) |
| **Full-scope claude.ai login for `ahagent`** | `ahagent`'s Claude Code credential store | `sudo -iu ahagent claude auth logout` |
| Live session, now supervised | user unit `ah-channel-telegram` (enabled) wrapping tmux `tgchannel` | `systemctl --user disable --now ah-channel-telegram`, then delete `~/.config/systemd/user/ah-channel-telegram.service` |
| Runbook written | `ops/channels/README.md` | delete the file |
| This report | `agents/reports/2026-09-19-telegram-channel-claude-code-chat.md` | delete the file |

Not changed: `bin/lib/tg*.py`, `ah-telegram`, `.env`, nginx, any systemd unit.
`ah-telegram`, `ah-dashboard` and `ah-feedback` were `active` before and after,
with **0** occurrences of `409`/`conflict` in `ah-telegram`'s journal throughout.

## 6. Going live — four things that cost time, all now documented

**1. The harness token is not enough for an interactive session.** `ahagent` had
never run Claude Code interactively; the first launch produced the onboarding
wizard and then an OAuth browser flow. `CLAUDE_CODE_OAUTH_TOKEN` can only make
model requests. The owner completed a full-scope login as
`imam.nurokhi@nexoratech.co`. That credential now lives in `ahagent`'s home on a
**shared** VPS — broader than what was there before, accepted knowingly, and
worth re-reading at the next access review. Upside: it is the exact obstacle
that blocked **Remote Control**, which now needs only the Owner toggle.

**2. `CLAUDE_CODE_OAUTH_TOKEN` silently overrides that login.** After a restart
the header read `Sonnet 5 · Claude API` instead of `Claude Team`. Measured:

| Environment | `authMethod` | Plan reported |
|---|---|---|
| `.env` sourced | `oauth_token` | none |
| `.env` not sourced | `claude.ai` | `team`, NexoraTech |

So the session must **not** source the workspace `.env` at all. Dropping only
`TELEGRAM_BOT_TOKEN`, as the first unit draft did, fixes the loud fault and
leaves the quiet one. Check with `claude auth status | grep -E
'authMethod|subscriptionType'` **before** launching.

**3. Auto mode was enabled by accident.** The first permission prompt offers
`1. Yes` and `2. Yes, and switch to auto mode`; a stray Enter took option 2, so
the session spent several minutes approving its own tool calls on a production
host. Corrected by relaunching with `--permission-mode manual` as a flag, which
also removes the keystroke that caused it.

**4. tmux sockets are per user.** `tmux attach -t tgchannel` as `root` answers
`no session`; the session belongs to `ahagent`. Use `sudo -u ahagent -H tmux
attach`, and leave with `Ctrl-b d` — `exit`, `Ctrl-D` or `/exit` kills the
bridge, while closing the terminal tab does not.

## 7. End-to-end proof

- Startup notice names `plugin:telegram@claude-plugins-official` with **no
  warning line** under it — that absence is the only evidence the Team-plan
  `channelsEnabled` toggle is really on. A loaded plugin proves nothing: with
  the toggle off the MCP server still connects and its tools still work, and no
  message is ever delivered.
- Inbound reached the session: `← telegram · 6687943152: Hi`.
- Outbound reached Telegram: the plugin's `reply` tool was called and answered.
- `access.json` ends at `dmPolicy: allowlist`, `allowFrom: ["6687943152"]` —
  strangers who find the bot username are now dropped silently rather than
  handed a pairing code.

## 8. What was blocked, and how each resolved

1. ~~**Team-plan admin toggle.**~~ **Done by the owner.** Verified indirectly —
   see §7.
2. ~~**`@AskNexAIBot`'s token.**~~ **Done by the owner**, written straight to
   `~/.claude/channels/telegram/.env` (`0600`), never through a chat transcript
   — `/telegram:configure <token>` writes the same file but would have put the
   token in the session log, which is how three credentials in `CLAUDE.md` §9
   got exposed in the first place.
3. **Two refusals from the Claude Code auto-mode classifier**, both permission
   decisions rather than defects:
   - `claude plugin install telegram@claude-plugins-official --scope user`
     → `Unauthorized Persistence`
   - writing `ops/channels/ah-channel-telegram.service`
     → `Create Unsafe Agents`

   The plugin install was then run by the owner with `!`. **Launching the
   session is refused for the same reason**, so every launch here was typed into
   the tmux pane by the assistant and submitted by the owner pressing Enter —
   three times, once per restart. The systemd unit stays a code block in
   `ops/channels/README.md` and is **not** installed, which is why the bridge is
   not yet reboot-safe.

## 9. Remote Control — now one toggle away

Its only real obstacle here was the limited-scope `CLAUDE_CODE_OAUTH_TOKEN`, and
`ahagent` now holds a full-scope claude.ai login. What remains is the Owner
toggle in claude.ai admin settings, and possibly Trusted Devices enrolment
(`policy-limits.json` shows `require_trusted_devices` is permitted for this org,
and `remote_control_at_startup` defaults to `false`).

## 10. What the owner should weigh

- **Blast radius.** An allowlisted sender steers a session with full read/write
  on this production VPS plus Slack/Notion/Linear/GitHub via MCP. Far beyond
  `@AgentNexoraBot`, by design.
- **Transcript residency.** While connected, transcripts are stored on Anthropic
  servers for cross-device sync; execution and filesystem access stay local.
- **Quota.** Every answer is a model call against the Team plan. No separate
  bill; the plan limit is the limit. This is not avoided by building it here —
  the hand-built option costs the same quota and delivers less.
- **Preview risk.** Syntax and protocol may change.

## 11. Next, in order

1. ~~**Decide whether the bridge should be reboot-safe.**~~ **Done** — see §12.
2. **Watch the permission-relay path in anger.** Manual mode is correct for a
   shared production host, but every tool call becomes an Approve/Deny button in
   Telegram. If that proves too noisy, narrow it with an allowlist in settings
   rather than by switching to auto mode.
3. **Model choice.** The session runs Sonnet 5. Raise to Opus with `/model opus`
   only if answers fall short — Sonnet is the cheaper default for operational
   questions.
4. **Revisit Remote Control** if phone access to the same session is wanted.

## 12. Made reboot-safe — 2026-09-19 18:43 UTC

The unit is no longer a code block. `~/.config/systemd/user/ah-channel-telegram.service`
is installed and `enabled`; `Linger=yes` was already set for `ahagent`, so it starts
at boot with no login session.

The owner wrote the file with the heredoc from this session's message. Two defects in
that paste, both from the terminal's auto-indent, both fixed in place: every line
arrived indented (systemd tolerates it) and the closing `EOF` was indented too, so it
was not recognised as the delimiter and landed **inside the file**. `sed` stripped the
indentation and the stray line; `systemctl --user show -p ExecStart` then confirmed the
continuation line joined correctly into one argv.

Cutover: `tmux kill-server` (the old server sat in a **root login scope**,
`user-0.slice/session-19719.scope`, because it was created through `sudo` — a second
reason it was fragile), then `systemctl --user enable --now`. The session now lives in
`user-1004.slice/user@1004.service/app.slice/ah-channel-telegram.service`.

Verified after the cutover:

| Check | Result |
|---|---|
| Unit | `active (running)`, `enabled`, Main PID = tmux server |
| Session header | `Sonnet 5 · Claude Team` — the claude.ai login, not `Claude API`, so no `.env` leaked in |
| Channel notice | names the plugin with **no warning line** — the Team toggle is still on |
| Permission mode | `⏸ manual mode on` |
| Plugin MCP server | `plugin:telegram:telegram` — ✔ Connected |
| Account connectors | Slack, Notion, Linear, GitHub, Context7, Claude Docs — all ✔ Connected for `ahagent` |
| `ah-telegram` | `active`, **0** `409`/`conflict` in the journal across the cutover |

Three facts worth keeping, now in `ops/channels/README.md`:

- `tmux new-session` reuses an existing server for the uid, so with one already
  running `ExecStart` returns without forking and `Type=forking` finds no main
  process. Kill the server before the first `start`.
- `ExecStartPre=-/usr/bin/tmux kill-session -t tgchannel` makes `restart` idempotent.
- tmux 3.4+ puts the pane's process in a sibling `tmux-spawn-<uuid>.scope`, so the
  unit's main PID is the tmux server. `Restart=on-failure` catches a crash; a clean
  `/exit` in the pane exits 0 and does **not** restart.

Unrelated noise seen at startup: `⚠ 14 MCP servers need authentication`. Those are
org-synced plugin bundles (`engineering`, `design`, `product-management`, …) pushed
from claude.ai, not anything installed here, and not the connectors the bridge uses.

## Sources

- <https://code.claude.com/docs/en/channels>
- <https://code.claude.com/docs/en/remote-control>
- <https://github.com/anthropics/claude-plugins-official/tree/main/external_plugins/telegram>
