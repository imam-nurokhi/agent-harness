# ops/harness — permission surface for unattended agents

The harness starts agents with `claude -p`. That is **headless**: there is no
human to answer a permission prompt. Without a declared policy every tool call
is refused with *"This command requires approval"*, and the agent spends a whole
run discovering it can do nothing.

That is not hypothetical. Job `135157-520a` (2026-09-17) was asked to send one
Telegram message. It ran for **181 seconds** and reported:

> every `python3` invocation (including a plain `print('hello')` sanity check)
> was blocked by this session's permission gate … **No message was sent.**

The run was recorded as `exit: done, code: 0`, so from the dashboard it looked
like a success.

## The files

| File | Role |
|---|---|
| `claude-settings.json` | the allowlist handed to every headless agent |
| `tests/test_agent_permissions.py` | stops it widening into a bypass |

## Why an allowlist and not `--dangerously-skip-permissions`

31.97.67.241 is shared with `dev-kemenkes`, `dev-support` and `monitoring`. An
unattended agent with a blanket bypass can reach all of them as `ahagent`. The
allowlist is narrow, reviewable, and **deny wins over allow**.

Allowed: `Read`, `Grep`, `Glob`, `Task`, `TodoWrite`, and read-only shell verbs
(`ls`, `cat`, `grep`, `find`, `sed`, `awk`, `python3`, `git status|log|diff|show`).

Denied: the workspace `.env` and every `**/.env` (the Telegram bot token and the
Claude OAuth token live there), `~/.ssh`, `/root`, `/etc/nginx`, edits anywhere
under `/etc`, and `sudo`, `curl`, `wget`, `ssh`, `scp`, `rsync`, `docker`,
`systemctl`, `nginx`, `chmod`, `chown`, `rm -rf`, `git push`, `git reset --hard`,
`npm`, `pip`.

Deny rules for files use `Edit(path)`, never `Write(path)`: only `Edit` rules
are matched by the file permission checks, and `Edit` covers every file-editing
tool. The CLI prints a warning on every run otherwise — which is how that was
found.

## Both spawn paths carry it

There are two, and fixing only one is why the first attempt still failed:

| Path | Used by | Wired in |
|---|---|---|
| `_engine_exec_once` | `ah run`, `ah trigger run` | `bin/lib/common.sh` |
| `jobs.spawn` | the dashboard, Telegram `/run` and `/ask` | `bin/lib/jobs.py` |

`ops/harness/tests/` fails if either one drops the flag, or if either acquires
`--dangerously-skip-permissions` or `bypassPermissions`.

## Widening it

Add the rule, add a test that says why, run `python3 -m unittest discover -s
ops/harness/tests`. Never reach for a bypass flag instead.

## Verified

After wiring, the same instruction that had failed twice ran in **59 s** and
returned `ok: true, message_id: 69` — faster precisely because the agent was no
longer fighting the gate.
