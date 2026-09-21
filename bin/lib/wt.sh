#!/usr/bin/env bash
# ah wt — isolated git worktree per task. One agent, one worktree, one diff.

cmd_wt() {
  case "${1:-list}" in
    add)  shift; wt_add "$@" ;;
    list) shift; wt_list ;;
    rm)   shift; wt_rm "$@" ;;
    *)    die "usage: ah wt {add|list|rm}" ;;
  esac
}

wt_add() {
  local id="$1" project="$2" base="${3:-}"
  [ -n "$id" ] && [ -n "$project" ] || die 'usage: ah wt add <task-id> <project-path> [base-branch]'
  require_task "$id"
  assert_claim_free "$id"

  project=$(cd "$project" 2>/dev/null && pwd -P) || die "no such directory: $2"
  assert_allowed_path "$project"
  git -C "$project" rev-parse --git-dir >/dev/null 2>&1 || die "not a git repository: $project"

  local dest branch
  dest=$(worktree_path "$id")
  [ -e "$dest" ] && die "worktree already exists: $dest"

  if [ -z "$base" ]; then
    if git -C "$project" show-ref --verify --quiet refs/heads/develop; then base=develop
    else base=$(git -C "$project" symbolic-ref --short HEAD); fi
  fi
  branch="agent/${id}"

  git -C "$project" show-ref --verify --quiet "refs/heads/${branch}" \
    && die "branch ${branch} already exists — pick a new task id or delete it"

  mkdir -p "$WORKTREES_DIR"
  git -C "$project" worktree add "$dest" -b "$branch" "$base" \
    || die "git worktree add failed"

  ok "worktree ${id} -> ${dest}"
  info "  repo:   ${project}"
  info "  branch: ${branch} (from ${base})"
  printf '\nNext: ah run <role> %s\n\n' "$id"
}

wt_list() {
  mkdir -p "$WORKTREES_DIR"
  local found=0
  printf '\n%-12s %-26s %s\n' "TASK" "BRANCH" "DIRTY"
  printf '%s\n' "------------ -------------------------- -----"
  for d in "$WORKTREES_DIR"/*/; do
    [ -d "$d" ] || continue
    found=1
    local id branch dirty
    id=$(basename "$d")
    branch=$(git -C "$d" branch --show-current 2>/dev/null || echo '?')
    if [ -n "$(git -C "$d" status --porcelain 2>/dev/null)" ]; then dirty="yes"; else dirty="no"; fi
    printf '%-12s %-26s %s\n' "$id" "$branch" "$dirty"
  done
  [ "$found" -eq 1 ] || info "no worktrees — create one with: ah wt add <task-id> <project-path>"
  printf '\n'
}

wt_rm() {
  local id="$1"
  [ -n "$id" ] || die 'usage: ah wt rm <task-id>'
  local dest; dest=$(worktree_path "$id")
  [ -d "$dest" ] || die "no worktree for ${id}"

  if pgrep -f "$dest" >/dev/null 2>&1; then
    die "an agent is still running inside ${id}. Stop it first (ah bot /stop, or kill it),
       otherwise its working directory vanishes mid-task."
  fi

  if [ -n "$(git -C "$dest" status --porcelain 2>/dev/null)" ]; then
    warn "worktree ${id} has uncommitted changes:"
    git -C "$dest" status --short | sed 's/^/    /'
    printf 'Remove anyway and lose them? [y/N] '
    read -r reply; [ "$reply" = y ] || { info "kept."; return 0; }
  fi

  local main; main=$(git -C "$dest" rev-parse --path-format=absolute --git-common-dir)
  git -C "${main%/.git}" worktree remove --force "$dest" 2>/dev/null \
    || git -C "$dest" worktree remove --force "$dest" 2>/dev/null \
    || rm -rf "$dest"
  ok "removed worktree ${id} (branch agent/${id} kept — delete it manually if unwanted)"
}
