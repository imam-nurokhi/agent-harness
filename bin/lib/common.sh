#!/usr/bin/env bash
# Shared helpers for the `ah` agent-harness CLI.

WORKSPACE="${AH_WORKSPACE:-${HOME}/AI-Workspace}"
AGENTS_DIR="${WORKSPACE}/agents"
PROJECTS_DIR="${WORKSPACE}/projects"
WORKTREES_DIR="${WORKSPACE}/worktrees"
TASKS_DIR="${AGENTS_DIR}/tasks"
REPORTS_DIR="${AGENTS_DIR}/reports"
ROLES_DIR="${AGENTS_DIR}/roles"
PROMPTS_DIR="${AGENTS_DIR}/prompts"

VALID_ROLES="lead frontend backend qa review devops docs"

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
