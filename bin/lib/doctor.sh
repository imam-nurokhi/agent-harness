#!/usr/bin/env bash
# ah doctor — verify the harness can actually run.

cmd_doctor() {
  local fail=0

  printf '\n%s== Agent Harness doctor ==%s\n\n' "$c_blu" "$c_off"

  printf 'Engines\n'
  for bin in codex claude git gh node; do
    if command -v "$bin" >/dev/null 2>&1; then
      ok "$(printf '%-7s %s' "$bin" "$(command -v "$bin")")"
    else
      warn "$(printf '%-7s not found' "$bin")"
      [ "$bin" = codex ] || [ "$bin" = git ] && fail=1
    fi
  done

  printf '\nAuthentication\n'
  if [ -f "${HOME}/.codex/auth.json" ]; then ok "codex logged in"
  else warn "codex not logged in — run: codex"; fail=1; fi
  if [ -d "${HOME}/.claude" ]; then ok "claude configured"
  else warn "claude not configured — run: claude"; fi

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
