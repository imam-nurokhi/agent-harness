#!/usr/bin/env bash
# ah trigger — scheduled work that starts without you typing.

TRIGGERS_FILE="${AGENTS_DIR}/triggers.json"

_trg_get() {
  python3 - "$TRIGGERS_FILE" "$1" "$2" <<'PY'
import json, sys
path, tid, field = sys.argv[1], sys.argv[2], sys.argv[3]
try:
    data = json.load(open(path))
except Exception:
    sys.exit(1)
for t in data.get("triggers", []):
    if t.get("id") == tid:
        print(t.get(field, ""))
        sys.exit(0)
sys.exit(1)
PY
}

cmd_trigger() {
  case "${1:-list}" in
    list)      shift; trg_list ;;
    run)       shift; trg_run "$@" ;;
    install)   shift; trg_install "$@" ;;
    uninstall) shift; trg_uninstall "$@" ;;
    *) die "usage: ah trigger {list|run|install|uninstall}" ;;
  esac
}

trg_list() {
  [ -f "$TRIGGERS_FILE" ] || { info "no triggers defined (${TRIGGERS_FILE})"; return; }
  python3 - "$TRIGGERS_FILE" "$HOME" <<'PY'
import json, sys
from pathlib import Path
data = json.load(open(sys.argv[1]))
home = Path(sys.argv[2])
print()
print(f"{'ID':<10} {'SCHEDULE':<18} {'ROLE':<8} {'INSTALLED':<10} LABEL")
print("-" * 74)
for t in data.get("triggers", []):
    tid = t.get("id", "?")
    plist = home / "Library" / "LaunchAgents" / f"com.ah.trigger.{tid}.plist"
    print(f"{tid:<10} {t.get('schedule',''):<18} {t.get('role',''):<8} "
          f"{'yes' if plist.exists() else 'no':<10} {t.get('label','')}")
print()
PY
}

trg_run() {
  local id="$1"
  [ -n "$id" ] || die 'usage: ah trigger run <id>'
  local role prompt
  role=$(_trg_get "$id" role) || die "no such trigger: ${id}"
  prompt=$(_trg_get "$id" prompt)
  require_role "$role"

  mkdir -p "$REPORTS_DIR"
  local log="${REPORTS_DIR}/trigger-${id}.$(date +%Y%m%d-%H%M).log"

  printf '\n%s== trigger %s / %s ==%s\n' "$c_blu" "$id" "$role" "$c_off"
  info "  log: ${log}"
  printf '\n'

  cd "$WORKSPACE" || die "cannot enter ${WORKSPACE}"
  local ROLE_UC
  ROLE_UC=$(printf '%s' "$role" | tr '[:lower:]' '[:upper:]')
  codex exec --skip-git-repo-check "You are the ${ROLE_UC} agent. Read-only reporting run, no file changes.

$(cat "${ROLES_DIR}/_common.md")

$(cat "${ROLES_DIR}/${role}.md")

TASK:
${prompt}" 2>&1 | tee "$log"

  python3 - "$TRIGGERS_FILE" "$id" <<'PY'
import json, sys, datetime
path, tid = sys.argv[1], sys.argv[2]
data = json.load(open(path))
for t in data.get("triggers", []):
    if t.get("id") == tid:
        t["last_run"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
json.dump(data, open(path, "w"), indent=2)
PY
  ok "trigger ${id} finished — ${log}"
}

# Translate "daily 09:00" / "weekly Mon 09:00" into launchd StartCalendarInterval.
_trg_calendar() {
  python3 - "$1" <<'PY'
import sys, re
s = sys.argv[1].strip().lower()
days = {"sun":0,"mon":1,"tue":2,"wed":3,"thu":4,"fri":5,"sat":6}
m = re.search(r"(\d{1,2}):(\d{2})", s)
hour, minute = (int(m.group(1)), int(m.group(2))) if m else (9, 0)
out = [f"    <key>Hour</key><integer>{hour}</integer>",
       f"    <key>Minute</key><integer>{minute}</integer>"]
for name, num in days.items():
    if name in s:
        out.append(f"    <key>Weekday</key><integer>{num}</integer>")
        break
print("\n".join(out))
PY
}

trg_install() {
  local id="$1"
  [ -n "$id" ] || die 'usage: ah trigger install <id>'
  local schedule label
  schedule=$(_trg_get "$id" schedule) || die "no such trigger: ${id}"
  label=$(_trg_get "$id" label)

  local plist="${HOME}/Library/LaunchAgents/com.ah.trigger.${id}.plist"
  mkdir -p "${HOME}/Library/LaunchAgents"
  cat > "$plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.ah.trigger.${id}</string>
  <key>ProgramArguments</key>
  <array>
    <string>${WORKSPACE}/bin/ah</string>
    <string>trigger</string>
    <string>run</string>
    <string>${id}</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict>
$(_trg_calendar "$schedule")
  </dict>
  <key>StandardOutPath</key><string>${REPORTS_DIR}/trigger-${id}.out</string>
  <key>StandardErrorPath</key><string>${REPORTS_DIR}/trigger-${id}.err</string>
  <key>RunAtLoad</key><false/>
</dict></plist>
EOF
  launchctl unload "$plist" 2>/dev/null || true
  launchctl load "$plist" || die "launchctl load failed for ${plist}"
  ok "installed trigger '${id}' (${schedule}) — ${label}"
  info "  ${plist}"
}

trg_uninstall() {
  local id="$1"
  [ -n "$id" ] || die 'usage: ah trigger uninstall <id>'
  local plist="${HOME}/Library/LaunchAgents/com.ah.trigger.${id}.plist"
  [ -f "$plist" ] || die "trigger ${id} is not installed"
  launchctl unload "$plist" 2>/dev/null || true
  rm -f "$plist"
  ok "uninstalled trigger ${id}"
}
