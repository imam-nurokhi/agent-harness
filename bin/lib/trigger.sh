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
    memo)      shift; trg_memo "$@" ;;
    install)   shift; trg_install "$@" ;;
    uninstall) shift; trg_uninstall "$@" ;;
    *) die "usage: ah trigger {list|run|memo|install|uninstall}" ;;
  esac
}

trg_list() {
  [ -f "$TRIGGERS_FILE" ] || { info "no triggers defined (${TRIGGERS_FILE})"; return; }

  local ids
  ids=$(python3 -c '
import json, sys
for t in json.load(open(sys.argv[1])).get("triggers", []):
    print(t.get("id", "?"))' "$TRIGGERS_FILE")

  # "installed" is whatever the supervisor reports, on either platform.
  # Deciding it from a launchd path said "no" on Linux no matter what was
  # actually scheduled.
  local installed=""
  for tid in $ids; do
    if sv_is_managed "com.ah.trigger.${tid}"; then installed="${installed}${tid}=yes "
    else installed="${installed}${tid}=no "; fi
  done

  python3 - "$TRIGGERS_FILE" "$installed" <<'PY'
import json, sys
data = json.load(open(sys.argv[1]))
state = dict(pair.split("=", 1) for pair in sys.argv[2].split() if "=" in pair)
print()
print(f"{'ID':<10} {'SCHEDULE':<18} {'ROLE':<8} {'INSTALLED':<10} LABEL")
print("-" * 74)
for t in data.get("triggers", []):
    tid = t.get("id", "?")
    print(f"{tid:<10} {t.get('schedule',''):<18} {t.get('role',''):<8} "
          f"{state.get(tid, '?'):<10} {t.get('label','')}")
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

  local per_project allowed="" stamp log status=0
  per_project=$(_trg_get "$id" per_project)
  if [ "$per_project" = "True" ] || [[ "$prompt" == *"{PROJECTS}"* ]]; then
    allowed=$(python3 "${LIB}/scope.py") || return 1
  fi
  mkdir -p "$REPORTS_DIR"
  stamp="$(date +%Y%m%d-%H%M%S)-$$"
  log="${REPORTS_DIR}/trigger-${id}.${stamp}.log"
  local ROLE_UC contract
  ROLE_UC=$(printf '%s' "$role" | tr '[:lower:]' '[:upper:]')
  contract="You are the ${ROLE_UC} agent. Read-only reporting run, no source changes.

$(cat "${ROLES_DIR}/_common.md")

$(cat "${ROLES_DIR}/${role}.md")"

  # A scheduled run has no session history. Hand it what the last runs learned,
  # and ask it to leave one line behind for the next one.
  local memory
  memory=$(python3 "${LIB}/trigmem.py" recall "$id" 2>/dev/null) || memory=""
  [ -z "$memory" ] || contract="${contract}

===== PREVIOUS RUNS =====
${memory}"
  contract="${contract}

Akhiri output dengan SATU baris terakhir berformat:
MEMO: <ringkas apa yang berubah sejak run sebelumnya dan apa yang butuh perhatian>
Baris itu yang dibaca run berikutnya, jadi tulis isi, bukan basa-basi."

  info "trigger ${id} / ${role} — log: ${log}"
  if [ "$per_project" = "True" ]; then
    local line project real name project_log project_prompt rc
    : > "$log"
    while IFS= read -r line; do
      [ "$line" != "- (tidak ada project yang boleh dikerjakan)" ] || continue
      [[ "$line" == "- "*"  (branch "*")" ]] || { warn "invalid scope row"; return 1; }
      project=${line#- }
      project=${project%  (branch *}
      case "$project" in
        /*) ;;
        *) project="${WORKSPACE}/${project}" ;;
      esac
      if ! real=$(cd "$project" && pwd -P); then
        printf 'Project unavailable: %s\n' "$project" | tee -a "$log"
        status=1
        continue
      fi
      case "$real" in
        "${HOME}/Documents"|"${HOME}/Documents/"*) return 1 ;;
      esac
      name=$(printf '%s' "${project#${WORKSPACE}/projects/}" | tr -c '[:alnum:]_.-' '_')
      project_log="${REPORTS_DIR}/trigger-${id}-${name}.${stamp}.log"
      project_prompt=${prompt//\{PROJECTS\}/$line}
      rc=0
      (
        cd "$real" || exit 1
        engine_exec "$(engine_for_role "$role")" "$role" "${contract}

RUN SCOPE: Only this project: ${real}.
This task authorizes working in this real project directory. Read its AGENTS.md and README.
Do not inspect other projects or secrets. No commits, pushes, installs, or source edits.
Running existing tests is authorized, including disposable test caches. For health, run the documented test command (npm test when defined) and quote actual output; report blockers honestly.

TASK:
${project_prompt}"
      ) > "$project_log" 2>&1 || rc=$?
      printf '\n== %s | cwd=%s | exit=%s | log=%s ==\n' "$line" "$real" "$rc" "$project_log" | tee -a "$log"
      cat "$project_log" | tee -a "$log"
      [ "$rc" -eq 0 ] || status=1
    done <<< "$allowed"
    [ -s "$log" ] || printf 'No workable projects; no agents launched.\n' | tee -a "$log"
  else
    prompt=${prompt//\{PROJECTS\}/$allowed}
    (
      cd "$WORKSPACE" || exit 1
      engine_exec "$(engine_for_role "$role")" "$role" "${contract}

TASK:
${prompt}"
    ) 2>&1 | tee "$log" || status=$?
  fi

  python3 - "$TRIGGERS_FILE" "$id" <<'PY'
import json, sys, datetime
path, tid = sys.argv[1], sys.argv[2]
data = json.load(open(path))
for t in data.get("triggers", []):
    if t.get("id") == tid:
        t["last_run"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
json.dump(data, open(path, "w"), indent=2)
PY
  python3 "${LIB}/trigmem.py" record "$id" "$status" "$log" || \
    warn "could not record trigger memory for ${id}"
  if [ "$status" -eq 0 ]; then
    ok "trigger ${id} finished — ${log}"
  else
    warn "trigger ${id} had failures — ${log}"
  fi
  return "$status"
}

trg_memo() {
  local id="$1"
  [ -n "$id" ] || die 'usage: ah trigger memo <id>'
  _trg_get "$id" role >/dev/null || die "no such trigger: ${id}"
  printf '\n'
  python3 "${LIB}/trigmem.py" show "$id"
  printf '\n'
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

  # Scheduling is the supervisor's job, not this file's. Writing a launchd
  # plist directly meant `ah trigger install` silently did nothing on Linux:
  # triggers.json showed four schedules enabled while the VPS had none of them.
  local unit
  unit=$(sv_install_timer "com.ah.trigger.${id}" "$schedule" \
           "${REPORTS_DIR}/trigger-${id}.out" "${REPORTS_DIR}/trigger-${id}.err" \
           "${WORKSPACE}/bin/ah" trigger run "$id") \
    || die "could not schedule trigger ${id}"
  ok "installed trigger '${id}' (${schedule}) -- ${label}"
  info "  ${unit}"
}

trg_uninstall() {
  local id="$1"
  [ -n "$id" ] || die 'usage: ah trigger uninstall <id>'
  sv_uninstall "com.ah.trigger.${id}" || die "trigger ${id} is not installed"
  ok "uninstalled trigger ${id}"
}

