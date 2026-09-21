#!/usr/bin/env bash
# ah task — create, list, and show tasks.

# Reserve the next free id by creating its file, not by checking whether the
# file exists: two agents that both look first will both pick the same number.
# `set -C` makes the create fail rather than clobber a racing writer.
#
# An archived task still owns its id. Its reports (agents/reports/task-018.*)
# and its worktree name outlive the task file, so handing 018 to a new task
# would silently graft one task's history onto another.
_task_id_retired() {
  [ -d "$ARCHIVES_DIR" ] || return 1
  find "$ARCHIVES_DIR" -name "${1}.md" -type f -print -quit 2>/dev/null | grep -q .
}

reserve_task_id() {
  local n=1 id
  mkdir -p "$TASKS_DIR"
  while :; do
    id=$(printf 'task-%03d' "$n")
    if _task_id_retired "$id"; then
      n=$((n + 1))
      continue
    fi
    if (set -C; : > "$(task_file "$id")") 2>/dev/null; then
      printf '%s' "$id"
      return
    fi
    n=$((n + 1))
  done
}

cmd_task() {
  case "${1:-list}" in
    new)     shift; task_new "$@" ;;
    list)    shift; task_list "$@" ;;
    show)    shift; require_task "${1:-}"; cat "$(task_file "$1")" ;;
    claim)   shift; task_claim "$@" ;;
    release) shift; task_release "$@" ;;
    *)       die "usage: ah task {new|list|show|claim|release}" ;;
  esac
}

task_new() {
  local title="$*"
  [ -n "$title" ] || die 'usage: ah task new "<title>"'
  case "$title" in
    *$'\n'*|*$'\r'*) die 'task title must be a single line' ;;
  esac

  local id file line
  id=$(reserve_task_id)
  file=$(task_file "$id")

  # Split the template line around the marker instead of using parameter
  # replacement: Bash can treat `&` in a replacement value as the matched
  # text when patsub_replacement is enabled.
  while IFS= read -r line || [ -n "$line" ]; do
    if [[ "$line" == *"<TITLE>"* ]]; then
      line="${line%%<TITLE>*}${title}${line#*<TITLE>}"
    fi
    line=${line//<task-000>/$id}
    printf '%s\n' "$line"
  done < "${AGENTS_DIR}/task-templates/task.md" > "$file"

  ok "created ${id}: ${title}"
  info "  ${file}"
  printf '\nNext: fill in Project, Role, Objective and Acceptance criteria, then:\n'
  printf '  ah wt add %s <project-path>\n  ah run <role> %s\n\n' "$id" "$id"
}

task_list() {
  mkdir -p "$TASKS_DIR"
  local found=0
  printf '\n%-10s %-8s %-8s %-6s %-8s %-16s %s\n' \
    "ID" "ROLE" "STATE" "AC" "WORKTREE" "HELD BY" "TITLE"
  printf '%s\n' "---------- -------- -------- ------ -------- ---------------- -----"
  for f in "$TASKS_DIR"/*.md; do
    [ -e "$f" ] || continue
    found=1
    local id title role wt ac done total state
    id=$(basename "$f" .md)
    title=$(sed -n '1s/^# Task: *//p' "$f")
    role=$(task_field "$id" Role)
    wt="none"
    [ -d "$(worktree_path "$id")" ] && wt="ready"

    total=$(sed -n '/^## Acceptance criteria/,/^## /p' "$f" | grep -c '^- \[' || true)
    done=$(sed -n '/^## Acceptance criteria/,/^## /p' "$f" | grep -ci '^- \[x\]' || true)
    total=${total:-0}
    done=${done:-0}
    ac="${done}/${total}"
    [ "$total" -eq 0 ] && ac="-"

    if [ "$total" -gt 0 ] && [ "$done" -eq "$total" ] && [ -f "${REPORTS_DIR}/${id}.md" ]; then
      state="done"
    elif [ -f "${REPORTS_DIR}/${id}.md" ]; then
      state="reported"
    elif ls "${REPORTS_DIR}/${id}."*.log >/dev/null 2>&1; then
      state="ran"
    elif [ "$wt" = "ready" ]; then
      state="active"
    else
      state="planned"
    fi
    local owner
    owner=$(claim_field "$id" owner 2>/dev/null) || owner=""
    printf '%-10s %-8s %-8s %-6s %-8s %-16s %s\n' \
      "$id" "${role:0:8}" "$state" "$ac" "$wt" "${owner:--}" "$title"
  done
  [ "$found" -eq 1 ] || info "no tasks yet — create one with: ah task new \"<title>\""
  printf '\n'
}
