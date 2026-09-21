#!/usr/bin/env bash
# Supervision, abstracted over the host init system.
#
# The harness is moving off the Mac and onto a Linux VPS, so nothing above this
# file may know what launchd or systemd is. Two shapes of supervised work:
#
#   daemon — stays up, restarts on crash and at boot   (the Telegram bot)
#   timer  — fires on a calendar schedule              (the triggers)
#
# Labels are reverse-DNS (com.ah.telegram, com.ah.trigger.standup) on both
# platforms, so state written by one install is findable by the other commands.

# The PATH a supervised job gets. launchd hands out a bare PATH and systemd's
# user manager is barely better, so both need it spelled out.
_sv_path() {
  printf '%s' "${HOME}/.local/bin:/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
}

sv_platform() {
  case "$(uname -s)" in
    Darwin) printf 'launchd' ;;
    Linux)
      if command -v systemctl >/dev/null 2>&1; then printf 'systemd'
      else printf 'none'; fi ;;
    *) printf 'none' ;;
  esac
}

# One schedule grammar ("daily 09:00", "weekly Mon 09:00"), two renderings.
# Keeping the parser single means a schedule cannot mean two different times
# depending on which machine installed it.
_sv_schedule() {
  python3 - "$1" "$2" <<'PY'
import sys, re
fmt, s = sys.argv[1], sys.argv[2].strip().lower()
days = {"sun": 0, "mon": 1, "tue": 2, "wed": 3, "thu": 4, "fri": 5, "sat": 6}
names = {0: "Sun", 1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri", 6: "Sat"}
m = re.search(r"(\d{1,2}):(\d{2})", s)
hour, minute = (int(m.group(1)), int(m.group(2))) if m else (9, 0)
weekday = next((num for name, num in days.items() if name in s), None)

# "hourly" or "hourly :10" runs every hour: the hour is a wildcard, only the
# minute is pinned. launchd expresses this by omitting the Hour key; systemd by
# a "*" in the hour field.
hourly = "hourly" in s
if hourly:
    mm = re.search(r":(\d{2})", s)
    minute = int(mm.group(1)) if mm else 0

if fmt == "launchd":
    out = [f"    <key>Minute</key><integer>{minute}</integer>"]
    if not hourly:
        out.insert(0, f"    <key>Hour</key><integer>{hour}</integer>")
    if weekday is not None:
        out.append(f"    <key>Weekday</key><integer>{weekday}</integer>")
    print("\n".join(out))
else:
    day = f"{names[weekday]} " if weekday is not None else ""
    hh = "*" if hourly else f"{hour:02d}"
    print(f"{day}*-*-* {hh}:{minute:02d}:00")
PY
}

_sv_plist()   { printf '%s/Library/LaunchAgents/%s.plist' "$HOME" "$1"; }
# XDG_CONFIG_HOME already *is* the config dir, so only "systemd/user" is
# appended. Appending "/.config/systemd/user" put units in a directory systemd
# never reads, and `systemctl --user enable` then failed on a unit it could not
# see -- which is why no trigger was ever scheduled on the VPS.
_sv_unit_dir() { printf '%s/systemd/user' "${XDG_CONFIG_HOME:-$HOME/.config}"; }

# `systemctl --user` needs XDG_RUNTIME_DIR to find the user manager's bus. A
# login shell has it; a script run through sudo, a timer, or the dashboard does
# not -- and without it systemctl exits non-zero, which every caller here reads
# as "not installed" rather than "could not ask". That is how `ah trigger list`
# reported INSTALLED=no for a timer that was enabled and running (2026-09-21).
# Supplying the default is safe: it is exactly what logind would have set.
_sv_user_bus() {
  [ -n "${XDG_RUNTIME_DIR:-}" ] || export XDG_RUNTIME_DIR="/run/user/$(id -u)"
}

# --- is it installed and running? -------------------------------------------

sv_is_managed() {
  local label="$1"
  case "$(sv_platform)" in
    launchd) launchctl list 2>/dev/null | grep -q "[[:space:]]${label}\$" ;;
    systemd)
      _sv_user_bus
      systemctl --user is-enabled "${label}.service" >/dev/null 2>&1 ||
      systemctl --user is-enabled "${label}.timer"   >/dev/null 2>&1 ;;
    *) return 1 ;;
  esac
}

sv_pid() {
  case "$(sv_platform)" in
    launchd) launchctl list 2>/dev/null | awk -v l="$1" '$3==l && $1!="-" {print $1}' ;;
    systemd) systemctl --user show -p MainPID --value "${1}.service" 2>/dev/null \
               | grep -v '^0$' ;;
  esac
}

# --- daemons ----------------------------------------------------------------

sv_install_daemon() {
  local label="$1" logfile="$2"; shift 2
  case "$(sv_platform)" in
    launchd) _sv_launchd_daemon "$label" "$logfile" "$@" ;;
    systemd) _sv_systemd_daemon "$label" "$@" ;;
    *) die "no supported supervisor on this host (need launchd or systemd)" ;;
  esac
}

_sv_launchd_daemon() {
  local label="$1" logfile="$2"; shift 2
  local plist; plist=$(_sv_plist "$label")
  mkdir -p "$(dirname "$plist")" "$(dirname "$logfile")"
  {
    printf '<?xml version="1.0" encoding="UTF-8"?>\n'
    printf '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
    printf '<plist version="1.0"><dict>\n'
    printf '  <key>Label</key><string>%s</string>\n' "$label"
    printf '  <key>ProgramArguments</key>\n  <array>\n'
    for arg in "$@"; do printf '    <string>%s</string>\n' "$arg"; done
    printf '  </array>\n'
    printf '  <key>WorkingDirectory</key><string>%s</string>\n' "$WORKSPACE"
    printf '  <key>EnvironmentVariables</key>\n  <dict>\n'
    printf '    <key>PATH</key><string>%s</string>\n' "$(_sv_path)"
    printf '    <key>HOME</key><string>%s</string>\n' "$HOME"
    printf '  </dict>\n'
    printf '  <key>RunAtLoad</key><true/>\n'
    printf '  <key>KeepAlive</key><true/>\n'
    printf '  <key>ThrottleInterval</key><integer>10</integer>\n'
    printf '  <key>StandardOutPath</key><string>%s</string>\n' "$logfile"
    printf '  <key>StandardErrorPath</key><string>%s</string>\n' "$logfile"
    printf '</dict></plist>\n'
  } > "$plist"
  launchctl unload "$plist" 2>/dev/null || true
  launchctl load "$plist" || die "launchctl load failed for ${plist}"
  printf '%s' "$plist"
}

_sv_systemd_daemon() {
  local label="$1"; shift
  local dir; dir=$(_sv_unit_dir)
  mkdir -p "$dir"
  # Without lingering, the user manager stops at logout and the bot dies with
  # the SSH session — exactly the failure the VPS move is meant to end.
  loginctl enable-linger "$(id -un)" >/dev/null 2>&1 || true
  {
    printf '[Unit]\nDescription=%s\nAfter=network-online.target\n\n' "$label"
    printf '[Service]\nType=simple\n'
    printf 'WorkingDirectory=%s\n' "$WORKSPACE"
    printf 'Environment=PATH=%s\nEnvironment=HOME=%s\n' "$(_sv_path)" "$HOME"
    printf 'Environment=AH_WORKSPACE=%s\n' "$WORKSPACE"
    # The engine credential lives in the workspace .env. Without it a scheduled
    # agent starts and immediately answers "Not logged in", which looks like a
    # working schedule and produces nothing. "-" keeps a workspace with no .env
    # installable.
    printf 'EnvironmentFile=-%s/.env\n' "$WORKSPACE"
    printf 'ExecStart='
    for arg in "$@"; do printf '%q ' "$arg"; done
    printf '\nRestart=always\nRestartSec=10\n\n'
    printf '[Install]\nWantedBy=default.target\n'
  } > "${dir}/${label}.service"
  systemctl --user daemon-reload
  systemctl --user enable --now "${label}.service" \
    || die "systemctl --user enable failed for ${label}.service"
  printf '%s' "${dir}/${label}.service"
}

# --- timers -----------------------------------------------------------------

sv_install_timer() {
  local label="$1" schedule="$2" outlog="$3" errlog="$4"; shift 4
  case "$(sv_platform)" in
    launchd) _sv_launchd_timer "$label" "$schedule" "$outlog" "$errlog" "$@" ;;
    systemd) _sv_systemd_timer "$label" "$schedule" "$@" ;;
    *) die "no supported supervisor on this host (need launchd or systemd)" ;;
  esac
}

_sv_launchd_timer() {
  local label="$1" schedule="$2" outlog="$3" errlog="$4"; shift 4
  local plist; plist=$(_sv_plist "$label")
  mkdir -p "$(dirname "$plist")"
  {
    printf '<?xml version="1.0" encoding="UTF-8"?>\n'
    printf '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
    printf '<plist version="1.0"><dict>\n'
    printf '  <key>Label</key><string>%s</string>\n' "$label"
    printf '  <key>ProgramArguments</key>\n  <array>\n'
    for arg in "$@"; do printf '    <string>%s</string>\n' "$arg"; done
    printf '  </array>\n'
    printf '  <key>EnvironmentVariables</key>\n  <dict>\n'
    printf '    <key>PATH</key><string>%s</string>\n' "$(_sv_path)"
    printf '    <key>HOME</key><string>%s</string>\n' "$HOME"
    printf '  </dict>\n'
    printf '  <key>WorkingDirectory</key><string>%s</string>\n' "$WORKSPACE"
    printf '  <key>StartCalendarInterval</key>\n  <dict>\n'
    _sv_schedule launchd "$schedule"
    printf '  </dict>\n'
    printf '  <key>StandardOutPath</key><string>%s</string>\n' "$outlog"
    printf '  <key>StandardErrorPath</key><string>%s</string>\n' "$errlog"
    printf '  <key>RunAtLoad</key><false/>\n'
    printf '</dict></plist>\n'
  } > "$plist"
  launchctl unload "$plist" 2>/dev/null || true
  launchctl load "$plist" || die "launchctl load failed for ${plist}"
  printf '%s' "$plist"
}

_sv_systemd_timer() {
  local label="$1" schedule="$2"; shift 2
  local dir; dir=$(_sv_unit_dir)
  mkdir -p "$dir"
  loginctl enable-linger "$(id -un)" >/dev/null 2>&1 || true
  {
    printf '[Unit]\nDescription=%s\n\n' "$label"
    printf '[Service]\nType=oneshot\n'
    printf 'WorkingDirectory=%s\n' "$WORKSPACE"
    printf 'Environment=PATH=%s\nEnvironment=HOME=%s\n' "$(_sv_path)" "$HOME"
    printf 'Environment=AH_WORKSPACE=%s\n' "$WORKSPACE"
    # The engine credential lives in the workspace .env. Without it a scheduled
    # agent starts and immediately answers "Not logged in", which looks like a
    # working schedule and produces nothing. "-" keeps a workspace with no .env
    # installable.
    printf 'EnvironmentFile=-%s/.env\n' "$WORKSPACE"
    printf 'ExecStart='
    for arg in "$@"; do printf '%q ' "$arg"; done
    printf '\n'
  } > "${dir}/${label}.service"
  {
    printf '[Unit]\nDescription=%s schedule\n\n' "$label"
    # launchd reads its calendar in the machine's local time, so the same
    # triggers.json entry meant 07:00 WIB on the team's Mac and 07:00 UTC --
    # 14:00 WIB -- on this server. Pin the timezone so a schedule means one
    # time everywhere. Override with AH_SCHEDULE_TZ.
    printf '[Timer]\nOnCalendar=%s %s\n' \
      "$(_sv_schedule systemd "$schedule")" "${AH_SCHEDULE_TZ:-Asia/Jakarta}"
    # A VPS that was down at 07:00 should still run the standup when it comes
    # back, rather than skipping the day in silence.
    printf 'Persistent=true\n\n'
    printf '[Install]\nWantedBy=timers.target\n'
  } > "${dir}/${label}.timer"
  systemctl --user daemon-reload
  systemctl --user enable --now "${label}.timer" \
    || die "systemctl --user enable failed for ${label}.timer"
  printf '%s' "${dir}/${label}.timer"
}

# --- removal ----------------------------------------------------------------

sv_uninstall() {
  local label="$1"
  case "$(sv_platform)" in
    launchd)
      local plist; plist=$(_sv_plist "$label")
      [ -f "$plist" ] || return 1
      launchctl unload "$plist" 2>/dev/null || true
      rm -f "$plist" ;;
    systemd)
      local dir; dir=$(_sv_unit_dir)
      [ -f "${dir}/${label}.service" ] || [ -f "${dir}/${label}.timer" ] || return 1
      systemctl --user disable --now "${label}.timer"   >/dev/null 2>&1 || true
      systemctl --user disable --now "${label}.service" >/dev/null 2>&1 || true
      rm -f "${dir}/${label}.service" "${dir}/${label}.timer"
      systemctl --user daemon-reload ;;
    *) return 1 ;;
  esac
}
