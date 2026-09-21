#!/usr/bin/env bash
# ah resume — carry stalled task work forward, once now or on an hourly timer.
#
# The judgement of which task is safe to resume lives in bin/lib/resume.py, and
# the loop that acts on it in bin/lib/resumerun.py. This is only the operator
# surface: run one sweep, or install the timer that runs one every hour.

RESUME_LABEL="com.ah.resume"

cmd_resume() {
  case "${1:-run}" in
    run)       shift; resume_run "$@" ;;
    once)      shift; resume_run "$@" ;;
    install)   shift; resume_install "$@" ;;
    uninstall) shift; resume_uninstall "$@" ;;
    status)    shift; resume_status ;;
    *) die 'usage: ah resume [run|install|uninstall|status]' ;;
  esac
}

# One sweep, right now, in the foreground. Prints what it did.
resume_run() {
  cd "$WORKSPACE" || die "cannot enter ${WORKSPACE}"
  python3 "${LIB_DIR}/resumerun.py"
}

resume_install() {
  command -v python3 >/dev/null 2>&1 || die "python3 not found"
  mkdir -p "$REPORTS_DIR"
  local out="${REPORTS_DIR}/resume.out.log" err="${REPORTS_DIR}/resume.err.log"
  local py; py=$(command -v python3)
  local path
  # Runs at ten past every hour, offset from the 07:00 standup so the two never
  # start in the same minute.
  path=$(sv_install_timer "$RESUME_LABEL" "hourly :10" "$out" "$err" \
           "$py" "${LIB_DIR}/resumerun.py")
  ok "auto-resume installed — hourly, via $(sv_platform)"
  info "  unit: ${path}"
  info "  logs: ${out}"
}

resume_uninstall() {
  if sv_uninstall "$RESUME_LABEL"; then
    ok "auto-resume timer removed"
  else
    info "auto-resume was not installed"
  fi
}

resume_status() {
  if sv_is_managed "$RESUME_LABEL"; then
    ok "auto-resume installed (hourly) via $(sv_platform)"
  else
    info "auto-resume not installed — enable with: ah resume install"
  fi
  printf '\nNext sweep would '
  cd "$WORKSPACE" || return 0
  local pick
  if pick=$(python3 "${LIB_DIR}/resume.py" 2>/dev/null); then
    printf 'resume: %s\n' "$pick"
  else
    printf 'do nothing (no stalled task, or the harness is busy/paused).\n'
  fi
}
