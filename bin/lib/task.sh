#!/usr/bin/env bash
# ah task — create, list, and show tasks.

next_task_id() {
  local n=1 id
  while :; do
    id=$(printf 'task-%03d' "$n")
    [ -f "$(task_file "$id")" ] || { printf '%s' "$id"; return; }
    n=$((n + 1))
  done
}

cmd_task() {
  case "${1:-list}" in
    new)  shift; task_new "$@" ;;
    list) shift; task_list "$@" ;;
    show) shift; require_task "${1:-}"; cat "$(task_file "$1")" ;;
    *)    die "usage: ah task {new|list|show}" ;;
  esac
}

task_new() {
  local title="$*"
  [ -n "$title" ] || die 'usage: ah task new "<title>"'

  local id file
  id=$(next_task_id)
  file=$(task_file "$id")
  mkdir -p "$TASKS_DIR"

  sed -e "s|<TITLE>|${title}|" -e "s|<task-000>|${id}|" \
      -e "s|~/AI-Workspace/worktrees/<task-000>|~/AI-Workspace/worktrees/${id}|" \
      "${AGENTS_DIR}/task-templates/task.md" > "$file"

  ok "created ${id}: ${title}"
  info "  ${file}"
  printf '\nNext: fill in Project, Role, Objective and Acceptance criteria, then:\n'
  printf '  ah wt add %s <project-path>\n  ah run <role> %s\n\n' "$id" "$id"
}

task_list() {
  mkdir -p "$TASKS_DIR"
  local found=0
  printf '\n%-10s %-8s %-22s %s\n' "ID" "ROLE" "WORKTREE" "TITLE"
  printf '%s\n' "---------- -------- ---------------------- -----"
  for f in "$TASKS_DIR"/*.md; do
    [ -e "$f" ] || continue
    found=1
    local id title role wt state
    id=$(basename "$f" .md)
    title=$(sed -n '1s/^# Task: *//p' "$f")
    role=$(task_field "$id" Role)
    wt="none"
    [ -d "$(worktree_path "$id")" ] && wt="ready"
    state=""
    [ -f "${REPORTS_DIR}/${id}.md" ] && state=" *reported"
    printf '%-10s %-8s %-22s %s%s\n' "$id" "${role:0:8}" "$wt" "$title" "$state"
  done
  [ "$found" -eq 1 ] || info "no tasks yet — create one with: ah task new \"<title>\""
  printf '\n'
}
