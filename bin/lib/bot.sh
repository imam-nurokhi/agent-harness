#!/usr/bin/env bash
# ah bot — Telegram control surface for the harness.

BOT_PID="${AGENTS_DIR}/.telegram/bot.pid"
BOT_LOG="${AGENTS_DIR}/.telegram/bot.log"
BOT_CFG="${AGENTS_DIR}/.telegram/config.json"

_bot_running() {
  if [ -f "$BOT_PID" ] && kill -0 "$(cat "$BOT_PID")" 2>/dev/null; then
    return 0
  fi
  pgrep -f "${LIB}/tgbot.py" >/dev/null 2>&1
}

_bot_managed_by_launchd() {
  launchctl list 2>/dev/null | grep -q com.ah.telegram
}

_bot_pid_now() {
  if [ -f "$BOT_PID" ] && kill -0 "$(cat "$BOT_PID")" 2>/dev/null; then
    cat "$BOT_PID"
  else
    pgrep -f "${LIB}/tgbot.py" | head -1
  fi
}

cmd_bot() {
  case "${1:-status}" in
    start)  shift; bot_start "$@" ;;
    stop)   shift; bot_stop ;;
    status) shift; bot_status ;;
    pair)   shift; bot_pair ;;
    log)    shift; tail -n "${1:-40}" "$BOT_LOG" 2>/dev/null || info "no log yet" ;;
    install)   shift; bot_install ;;
    uninstall) shift; bot_uninstall ;;
    *) die "usage: ah bot {start|stop|status|pair|log|install|uninstall}" ;;
  esac
}

bot_start() {
  [ -f "${WORKSPACE}/.env" ] || die "missing ${WORKSPACE}/.env — add TELEGRAM_BOT_TOKEN"
  if _bot_running; then
    ok "bot already running (pid $(cat "$BOT_PID"))"
    return 0
  fi
  mkdir -p "$(dirname "$BOT_PID")"

  if [ "${1:-}" = "--foreground" ]; then
    exec python3 "${LIB}/tgbot.py"
  fi

  nohup python3 "${LIB}/tgbot.py" >> "$BOT_LOG" 2>&1 &
  echo $! > "$BOT_PID"
  sleep 2
  if _bot_running; then
    ok "bot started (pid $(cat "$BOT_PID"))"
    info "  log: ${BOT_LOG}"
    grep -q '"allowed": \[\]' "$BOT_CFG" 2>/dev/null && bot_pair
  else
    warn "bot failed to start — last lines:"
    tail -n 15 "$BOT_LOG" 2>/dev/null
    return 1
  fi
}

bot_stop() {
  if _bot_managed_by_launchd; then
    warn "bot is supervised by launchd and would restart immediately."
    info "  stop it for good with: ah bot uninstall"
    return 1
  fi
  if _bot_running; then
    kill "$(_bot_pid_now)" 2>/dev/null
    rm -f "$BOT_PID"
    ok "bot stopped"
  else
    rm -f "$BOT_PID"
    info "bot is not running"
  fi
}

bot_status() {
  printf '\n'
  if _bot_running; then
    if _bot_managed_by_launchd; then
      ok "running under launchd (pid $(_bot_pid_now)) — restarts on crash and at login"
    else
      ok "running (pid $(_bot_pid_now)) — stops when you log out; use: ah bot install"
    fi
  else
    warn "not running — start it with: ah bot start (or: ah bot install)"
  fi
  if [ -f "$BOT_CFG" ]; then
    python3 - "$BOT_CFG" <<'PY'
import json, sys
cfg = json.load(open(sys.argv[1]))
allowed = cfg.get("allowed") or []
print(f"  paired chats: {allowed if allowed else 'none — run: ah bot pair'}")
print(f"  pending pair code: {cfg.get('pair_code') or '-'}")
PY
  else
    info "  not configured yet"
  fi
  printf '\n'
}

bot_pair() {
  mkdir -p "$(dirname "$BOT_CFG")"
  python3 - "$BOT_CFG" <<'PY'
import json, random, os, sys
path = sys.argv[1]
try:
    cfg = json.load(open(path))
except Exception:
    cfg = {"allowed": [], "pair_code": None, "offset": 0, "seen_jobs": []}
cfg["pair_code"] = f"{random.randint(0, 999999):06d}"
json.dump(cfg, open(path, "w"), indent=2)
os.chmod(path, 0o600)
print()
print("  Open Telegram, find @KaraImamiBot, and send:")
print()
print(f"      /pair {cfg['pair_code']}")
print()
print("  The code works once. Only paired chats can control the harness.")
print()
PY
}

# Keep the bot alive across logouts and reboots, so the phone stays in control
# even when no terminal session is open.
BOT_PLIST="${HOME}/Library/LaunchAgents/com.ah.telegram.plist"

bot_install() {
  [ -f "${WORKSPACE}/.env" ] || die "missing ${WORKSPACE}/.env — add TELEGRAM_BOT_TOKEN"
  bot_stop >/dev/null 2>&1 || true
  mkdir -p "${HOME}/Library/LaunchAgents" "$(dirname "$BOT_LOG")"

  cat > "$BOT_PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.ah.telegram</string>
  <key>ProgramArguments</key>
  <array>
    <string>$(command -v python3)</string>
    <string>${LIB}/tgbot.py</string>
  </array>
  <key>WorkingDirectory</key><string>${WORKSPACE}</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key><string>${HOME}/.local/bin:/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    <key>HOME</key><string>${HOME}</string>
  </dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>10</integer>
  <key>StandardOutPath</key><string>${BOT_LOG}</string>
  <key>StandardErrorPath</key><string>${BOT_LOG}</string>
</dict></plist>
EOF

  launchctl unload "$BOT_PLIST" 2>/dev/null || true
  launchctl load "$BOT_PLIST" || die "launchctl load failed"
  sleep 2
  if launchctl list | grep -q com.ah.telegram; then
    ok "bot installed — it now starts at login and restarts if it crashes"
    info "  ${BOT_PLIST}"
    grep -q '"allowed": \[\]' "$BOT_CFG" 2>/dev/null && bot_pair
  else
    warn "installed but not running — check: ah bot log"
  fi
}

bot_uninstall() {
  [ -f "$BOT_PLIST" ] || die "bot is not installed"
  launchctl unload "$BOT_PLIST" 2>/dev/null || true
  rm -f "$BOT_PLIST"
  ok "bot uninstalled — it will no longer start at login"
}
