#!/usr/bin/env bash
# ah run — launch an engine in a task's worktree with the role contract loaded.

build_prompt() {
  local role="$1" id="$2" cwd="$3"
  local ROLE_UC
  ROLE_UC=$(printf '%s' "$role" | tr '[:lower:]' '[:upper:]')
  cat <<EOF
You are the ${ROLE_UC} agent in a multi-agent harness. Your contract follows.
Read it fully before you touch anything.

Working directory: ${cwd}
Never operate outside it. ~/Documents is off-limits at all times.

===== WORKSPACE RULES (~/AI-Workspace/AGENTS.md) =====
$(cat "${WORKSPACE}/AGENTS.md")

===== COMMON ROLE PREAMBLE =====
$(cat "${ROLES_DIR}/_common.md")

===== ROLE: ${role} =====
$(cat "${ROLES_DIR}/${role}.md")

===== TASK =====
$(cat "$(task_file "$id")")

===== BEGIN =====
Restate the objective and acceptance criteria in two sentences, state any
ASSUMPTION you must make, then proceed. Finish with the Report block exactly as
specified in the common preamble.
EOF
}

cmd_run() {
  local exec_mode=0
  while [ $# -gt 0 ]; do
    case "$1" in
      --exec) exec_mode=1; shift ;;
      *) break ;;
    esac
  done

  local role="$1" id="$2"
  require_role "$role"
  require_task "$id"

  # Hold the task for as long as this run lives, so a second agent cannot start
  # inside the same worktree. The claim dies with the process, not with the task.
  claim_bind "$id" "run/${role}" $$
  trap 'claim_release_own "$id"' EXIT

  local cwd
  cwd=$(worktree_path "$id")
  if [ ! -d "$cwd" ]; then
    if [ "$role" = lead ] || [ "$role" = docs ]; then
      cwd="$WORKSPACE"   # planning roles do not need a worktree
    else
      die "no worktree for ${id}. Run: ah wt add ${id} <project-path>"
    fi
  fi
  assert_allowed_path "$cwd"
  assert_execution_allowed "$cwd"

  local engine prompt
  engine=$(engine_for_role "$role")
  command -v "$engine" >/dev/null 2>&1 || die "engine '${engine}' not installed"
  prompt=$(build_prompt "$role" "$id" "$cwd")

  mkdir -p "$REPORTS_DIR"
  local log="${REPORTS_DIR}/${id}.${role}.log"

  printf '\n%s== %s / %s via %s ==%s\n' "$c_blu" "$id" "$role" "$engine" "$c_off"
  info "  cwd: ${cwd}"
  info "  log: ${log}"
  printf '\n'

  cd "$cwd" || die "cannot enter ${cwd}"

  if [ "$exec_mode" -eq 1 ]; then
    engine_exec "$engine" "$role" "$prompt" 2>&1 | tee "$log"
    ok "finished — transcript at ${log}"
  else
    engine_interactive "$engine" "$role" "$prompt"
  fi
}

# ah recon — read-only first pass on an unfamiliar repository.
cmd_recon() {
  local project="$1"
  [ -n "$project" ] || die 'usage: ah recon <project-path>'
  project=$(cd "$project" 2>/dev/null && pwd -P) || die "no such directory: $1"
  assert_allowed_path "$project"
  assert_execution_allowed "$project"

  mkdir -p "$REPORTS_DIR"
  local name out
  name=$(basename "$project")
  out="${REPORTS_DIR}/recon-${name}.md"

  printf '\n%s== recon: %s ==%s\n' "$c_blu" "$name" "$c_off"
  info "  report: ${out}"
  printf '\n'

  cd "$project" || die "cannot enter ${project}"
  engine_exec "$(engine_for_role docs)" docs "$(cat "${PROMPTS_DIR}/01-recon.md")

Target repository: ${project}
You are strictly read-only." 2>&1 | tee "$out"

  ok "recon saved to ${out}"
}
