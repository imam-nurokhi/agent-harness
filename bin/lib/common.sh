#!/usr/bin/env bash
# Shared helpers for the `ah` agent-harness CLI.

WORKSPACE="${AH_WORKSPACE:-${HOME}/AI-Workspace}"
AGENTS_DIR="${WORKSPACE}/agents"
PROJECTS_DIR="${WORKSPACE}/projects"
WORKTREES_DIR="${WORKSPACE}/worktrees"
TASKS_DIR="${AGENTS_DIR}/tasks"
REPORTS_DIR="${AGENTS_DIR}/reports"
CLAIMS_DIR="${AGENTS_DIR}/claims"
ROLES_DIR="${AGENTS_DIR}/roles"
PROMPTS_DIR="${AGENTS_DIR}/prompts"
ARCHIVES_DIR="${WORKSPACE}/archives"
LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

VALID_ROLES="lead frontend backend qa review devops docs"

# Attempts one piece of work may cost across engines. Each one is a real
# quota, so this stays small and is not a loop until something works.
AH_MAX_ATTEMPTS="${AH_MAX_ATTEMPTS:-3}"

c_red=$'\033[31m'; c_grn=$'\033[32m'; c_yel=$'\033[33m'
c_blu=$'\033[34m'; c_dim=$'\033[2m'; c_off=$'\033[0m'

die()  { printf '%serror:%s %s\n' "$c_red" "$c_off" "$*" >&2; exit 1; }
warn() { printf '%swarn:%s  %s\n' "$c_yel" "$c_off" "$*" >&2; }
ok()   { printf '%s ok %s  %s\n' "$c_grn" "$c_off" "$*"; }
info() { printf '%s%s%s\n' "$c_dim" "$*" "$c_off"; }

# Guard: the user has asked that no agent work ever reach ~/Documents.
assert_allowed_path() {
  case "$(cd "$1" 2>/dev/null && pwd -P || echo "$1")" in
    "${HOME}/Documents"|"${HOME}/Documents"/*)
      die "path is inside ~/Documents, which is off-limits for the harness: $1" ;;
  esac
}

# Registered-but-on-hold projects: onboarding is allowed, execution is not.
# The human lifts a hold by editing agents/.scope.
assert_execution_allowed() {
  local target="$1" scope="${AGENTS_DIR}/.scope" real rel pattern common
  [ -f "$scope" ] || return 0
  real=$(cd "$target" 2>/dev/null && pwd -P || echo "$target")

  if common=$(git -C "$real" rev-parse --path-format=absolute --git-common-dir 2>/dev/null); then
    real=$(cd "$(dirname "$common")" 2>/dev/null && pwd -P || echo "$real")
  fi

  while read -r verb pattern; do
    [ "$verb" = "HOLD" ] || continue
    for link in "${PROJECTS_DIR}"/${pattern}; do
      [ -e "$link" ] || continue
      rel=$(cd "$link" 2>/dev/null && pwd -P || echo "$link")
      case "$real" in
        "$rel"|"$rel"/*)
          die "project is registered but ON HOLD: ${link#${PROJECTS_DIR}/}
       No agent may run against it yet. Lift the hold in agents/.scope when ready." ;;
      esac
    done
  done < "$scope"
}

# --- engines ---------------------------------------------------------------
# Claude is preferred, because the VPS runs on the team plan. But installed and
# authorised are different things: an org can disable Claude Code for the
# account whose credentials a launchd-started harness inherits, and then every
# run fails in under a second with the same refusal. bin/lib/engine.py holds
# the one implementation of "which engine, and which has stopped being allowed"
# so the CLI and the dashboard never disagree about it.
_engine_py() { python3 "${LIB_DIR}/engine.py" "$@"; }

engine_for_role() {
  [ -n "${AH_ENGINE:-}" ] && { printf '%s' "$AH_ENGINE"; return; }
  _engine_py pick "${1:-}" 2>/dev/null || printf 'claude'
}

# What a finished run proved: a refusal gets the engine skipped next time, a
# success clears an earlier note so restored access is picked up on its own.
# Records what the run proved and answers one question: was the ENGINE at
# fault? Prints nothing when the failure was the agent's own, which must never
# be retried elsewhere — that spends a second quota to reproduce the same bug.
engine_note_result() {
  local engine="$1" rc="$2" out="$3" kind
  kind=$(head -c 2000 "$out" 2>/dev/null | _engine_py note "$engine" "$rc" 2>/dev/null) || kind=""
  [ -n "$kind" ] && { printf '%s' "$kind"; return 1; }
  return 0
}

# With one vendor, "the reviewer is not the implementer" can no longer be
# guaranteed by provider. It is now enforced by model and by context: reviewers
# get their own model and are handed the diff, never the implementer's session.
model_for_role() {
  case "$1" in
    review|qa) printf '%s' "${AH_MODEL_REVIEW:-}" ;;
    *)         printf '%s' "${AH_MODEL_IMPL:-}" ;;
  esac
}

# The single place that knows how to launch an unattended run. Every caller
# (ah run --exec, triggers, recon) goes through here so the engine is swapped
# in one edit, not five.
# Runs the engine, and if it is refused, switches to the next one and runs
# again. Each refusal removes one candidate, so the loop is bounded by the
# number of engines in AH_ENGINE_ORDER and cannot spin. Without this the first
# job after an admin revokes access fails for no reason the operator can act
# on, and so does every job after it.
engine_exec() {
  local engine="$1" role="$2" prompt="$3"
  local out rc next
  out=$(mktemp "${TMPDIR:-/tmp}/ah-engine.XXXXXX")
  trap 'rm -f "$out"' RETURN

  local attempt=1 kind
  while :; do
    set +e
    _engine_exec_once "$engine" "$role" "$prompt" 2>&1 | tee "$out"
    rc=${PIPESTATUS[0]}
    set -e

    kind=$(engine_note_result "$engine" "$rc" "$out") && return "$rc"

    if [ "$attempt" -ge "$AH_MAX_ATTEMPTS" ]; then
      warn "gave up after ${attempt} attempts — last engine '${engine}' reported: ${kind}"
      engine_report_paused
      return "$rc"
    fi

    next=$(_engine_py next "$engine" 2>/dev/null) || {
      warn "engine '${engine}' reported '${kind}' and no other engine is usable"
      engine_report_paused
      return "$rc"
    }
    attempt=$((attempt + 1))
    warn "engine '${engine}' reported '${kind}' — attempt ${attempt}/${AH_MAX_ATTEMPTS} on '${next}'"
    engine="$next"
    : > "$out"
  done
}

# The harness has nothing left to run with. Say so where it will be read: the
# terminal here, and the Telegram bot, which notices the shared state file on
# its next poll and announces it without this needing a token of its own.
engine_report_paused() {
  if _engine_py paused 2>/dev/null; then
    warn "harness paused — no engine can run:"
    _engine_py status 2>/dev/null | sed 's/^/    /' >&2
  fi
}

# Unattended runs have nobody to answer a permission prompt, so the policy has
# to be declared up front or every tool call is refused and the run is wasted
# reporting that it was blocked. The file is a narrow, reviewed allowlist --
# see ops/harness/README.md. Never replace it with a bypass flag.
AH_AGENT_SETTINGS="${AH_WORKSPACE:-$HOME/AI-Workspace}/ops/harness/claude-settings.json"

_engine_exec_once() {
  local engine="$1" role="$2" prompt="$3" model settings=()
  model=$(model_for_role "$role")
  [ -f "$AH_AGENT_SETTINGS" ] && settings=(--settings "$AH_AGENT_SETTINGS")
  case "$engine" in
    claude)
      if [ -n "$model" ]; then
        claude -p "${settings[@]}" --model "$model" "$prompt" < /dev/null
      else
        claude -p "${settings[@]}" "$prompt" < /dev/null
      fi ;;
    codex)
      local gitflag=""
      [ -d ".git" ] || gitflag="--skip-git-repo-check"
      codex exec $gitflag "$prompt" < /dev/null ;;
    *) die "unknown engine: ${engine}" ;;
  esac
}

# Attended run: the human is watching, so the engine keeps its own UI.
engine_interactive() {
  local engine="$1" role="$2" prompt="$3" model
  model=$(model_for_role "$role")
  case "$engine" in
    claude)
      if [ -n "$model" ]; then claude --model "$model" "$prompt"; else claude "$prompt"; fi ;;
    codex)
      local gitflag=""
      [ -d ".git" ] || gitflag="--skip-git-repo-check"
      codex $gitflag "$prompt" ;;
    *) die "unknown engine: ${engine}" ;;
  esac
}

require_role() {
  local role="$1"
  [ -n "$role" ] || die "role is required (one of: ${VALID_ROLES})"
  case " ${VALID_ROLES} " in
    *" ${role} "*) : ;;
    *) die "unknown role '${role}'. Valid: ${VALID_ROLES}" ;;
  esac
  [ -f "${ROLES_DIR}/${role}.md" ] || die "missing role file: ${ROLES_DIR}/${role}.md"
}

task_file() { printf '%s/%s.md' "$TASKS_DIR" "$1"; }

require_task() {
  local id="$1"
  [ -n "$id" ] || die "task id is required (see: ah task list)"
  [ -f "$(task_file "$id")" ] || die "no such task: ${id} (see: ah task list)"
}

# Read "- **Key:** value" out of a task file.
task_field() {
  sed -n "s/^- \*\*$2:\*\* *//p" "$(task_file "$1")" | head -1 \
    | sed 's/^`//; s/`$//' | tr -d '\r'
}

worktree_path() { printf '%s/%s' "$WORKTREES_DIR" "$1"; }

# launchd gives a job a bare PATH, so engines in ~/.local/bin are invisible.
# Rebuild it once, here, for every code path that shells out to an engine.
export PATH="${HOME}/.local/bin:/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:${PATH}"

# Run the engine as the account that is actually authorised. See agent_env() in
# jobs.py for the full why: launchd does not inherit CLAUDE_CONFIG_DIR, so
# without this the engine falls back to the org-disabled team account.
if [ -n "${AH_CLAUDE_CONFIG_DIR:-}" ] && [ -d "${AH_CLAUDE_CONFIG_DIR}" ]; then
  export CLAUDE_CONFIG_DIR="${AH_CLAUDE_CONFIG_DIR}"
elif [ -z "${CLAUDE_CONFIG_DIR:-}" ] && [ -d "${HOME}/.claude-work" ]; then
  export CLAUDE_CONFIG_DIR="${HOME}/.claude-work"
fi

# ah engine — what the harness will launch, and what it has stopped launching.
cmd_engine() {
  case "${1:-status}" in
    status)
      printf 'chosen: %s\n' "$(engine_for_role backend)"
      printf 'order:  %s\n' "${AH_ENGINE_ORDER:-claude codex}"
      [ -n "${AH_ENGINE:-}" ] && printf 'override AH_ENGINE=%s\n' "$AH_ENGINE"
      printf 'refused:\n'
      _engine_py status | sed 's/^/  /' ;;
    clear)  [ -n "${2:-}" ] || die 'usage: ah engine clear <name>'
            _engine_py clear "$2" && ok "engine '${2}' may be chosen again" ;;
    block)  [ -n "${2:-}" ] || die 'usage: ah engine block <name> [reason]'
            _engine_py block "$2" "${3:-marked by hand}" && ok "engine '${2}' will be skipped" ;;
    *) die 'usage: ah engine [status|clear <name>|block <name> [reason]]' ;;
  esac
}
