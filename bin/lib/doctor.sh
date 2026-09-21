#!/usr/bin/env bash
# ah doctor — verify the harness can actually run.

# Where Claude keeps its login differs by platform: macOS uses the Keychain,
# Linux writes a claudeAiOauth block into ~/.claude/.credentials.json. On the
# VPS nobody is watching for a login prompt, so this has to be checkable.
_claude_authed() {
  [ -n "${ANTHROPIC_API_KEY:-}" ] && return 0
  # A long-lived OAuth token (claude setup-token) authenticates via the
  # environment, not the credential store — this is how the VPS runs claude as
  # the work account without an interactive login. Without this check `doctor`
  # cried "no credentials" while runs were completing fine.
  [ -n "${CLAUDE_CODE_OAUTH_TOKEN:-}" ] && return 0
  if [ "$(uname -s)" = "Darwin" ]; then
    security find-generic-password -s "Claude Code-credentials" -w >/dev/null 2>&1 && return 0
  fi
  [ -f "${HOME}/.claude/.credentials.json" ] \
    && grep -q 'claudeAiOauth' "${HOME}/.claude/.credentials.json" 2>/dev/null
}

cmd_doctor() {
  local fail=0

  printf '\n%s== Agent Harness doctor ==%s\n\n' "$c_blu" "$c_off"

  printf 'Engines\n'
  # claude and git are required; codex is optional since the harness runs
  # Claude-only on the VPS and codex is reachable only via AH_ENGINE.
  for bin in claude git node gh codex; do
    if command -v "$bin" >/dev/null 2>&1; then
      ok "$(printf '%-7s %s' "$bin" "$(command -v "$bin")")"
    else
      warn "$(printf '%-7s not found' "$bin")"
      case "$bin" in claude|git) fail=1 ;; esac
    fi
  done

  printf '\nAuthentication\n'
  # Credentials being present is not the same as being allowed to use them.
  # This check used to report "claude logged in" on a machine where every
  # single run was refused by the org, so it now reports both facts.
  if _claude_authed; then
    ok "claude credentials present"
  else
    warn "claude has no credentials on this machine"
    info "  fix: run 'claude' once and complete the login"
  fi
  if command -v codex >/dev/null 2>&1; then
    [ -f "${HOME}/.codex/auth.json" ] && ok "codex logged in" \
      || info "  codex present but not logged in"
  fi

  local chosen blockedj
  chosen=$(engine_for_role backend)
  blockedj=$(_engine_py status 2>/dev/null || printf '{}')
  if [ "$blockedj" != "{}" ]; then
    warn "an engine has been refused by this account and is being skipped:"
    printf '%s\n' "$blockedj" | sed 's/^/    /'
    info "  clear it after fixing access: ah engine clear <name>"
  fi
  if command -v "$chosen" >/dev/null 2>&1; then
    ok "runs will use: ${chosen}"
  else
    warn "runs would use '${chosen}', which is not installed"
    fail=1
  fi

  printf '\nWorkspace layout\n'
  for d in "$AGENTS_DIR" "$PROJECTS_DIR" "$WORKTREES_DIR" "$TASKS_DIR" \
           "$REPORTS_DIR" "$ROLES_DIR" "$PROMPTS_DIR"; do
    if [ -d "$d" ]; then ok "${d#$HOME/}"
    else warn "missing ${d#$HOME/}"; fail=1; fi
  done

  printf '\nRole definitions\n'
  for role in $VALID_ROLES; do
    if [ -s "${ROLES_DIR}/${role}.md" ]; then ok "$role"
    else warn "role '${role}' missing or empty"; fail=1; fi
  done

  printf '\nRules\n'
  [ -s "${WORKSPACE}/AGENTS.md" ] && ok "AGENTS.md" || { warn "AGENTS.md missing"; fail=1; }

  printf '\nGuardrails\n'
  if grep -qs 'Documents' "${WORKSPACE}/AGENTS.md"; then ok "~/Documents exclusion documented"
  else warn "~/Documents exclusion not in AGENTS.md"; fi

  printf '\nDisk\n'
  local avail pct
  avail=$(df -h "$HOME" | awk 'NR==2{print $4}')
  pct=$(df -h "$HOME" | awk 'NR==2{print $5}' | tr -d '%')
  if [ "$pct" -ge 95 ]; then warn "only ${avail} free (${pct}% used) — worktrees need room"
  else ok "${avail} free"; fi

  printf '\nActive work\n'
  info "  tasks:     $(ls -1 "$TASKS_DIR"/*.md 2>/dev/null | wc -l | tr -d ' ')"
  info "  worktrees: $(find "$WORKTREES_DIR" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l | tr -d ' ')"
  info "  reports:   $(ls -1 "$REPORTS_DIR"/*.md 2>/dev/null | wc -l | tr -d ' ')"

  printf '\n'
  if [ "$fail" -eq 0 ]; then
    printf '%sHarness is ready.%s\n\n' "$c_grn" "$c_off"
  else
    printf '%sHarness has gaps — see warnings above.%s\n\n' "$c_yel" "$c_off"
    return 1
  fi
}
