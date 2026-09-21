#!/usr/bin/env bash
# ah claims — who is holding a task right now.
#
# More than one agent shares this workspace (a local session, a scheduled
# trigger, someone else's tool). Without an explicit holder they pick the same
# task id or walk into a worktree already in use, and the collision is silent.

claim_owner() { printf '%s' "${AH_OWNER:-$(id -un)@$(hostname -s)}"; }

claim_path() { printf '%s/%s.claim' "$CLAIMS_DIR" "$1"; }

claim_field() {
  local file
  file=$(claim_path "$1")
  [ -f "$file" ] || return 1
  sed -n "s/^$2=//p" "$file" | head -1
}

# A claim bound to a process dies with it. A claim without a pid was made by a
# human and is held until someone releases it on purpose.
claim_is_stale() {
  local pid
  pid=$(claim_field "$1" pid) || return 1
  [ -n "$pid" ] || return 1
  kill -0 "$pid" 2>/dev/null && return 1
  return 0
}

claim_held_by_other() {
  local owner
  owner=$(claim_field "$1" owner) || return 1
  [ -n "$owner" ] || return 1
  [ "$owner" = "$(claim_owner)" ] && return 1
  claim_is_stale "$1" && return 1
  return 0
}

assert_claim_free() {
  local id="$1"
  claim_held_by_other "$id" || return 0
  die "task ${id} is claimed by $(claim_field "$id" owner) since $(claim_field "$id" since)
       note: $(claim_field "$id" note)
       Coordinate with them, or break it with: ah task release ${id} --force"
}

_claim_write() {
  local id="$1" note="$2" pid="$3"
  mkdir -p "$CLAIMS_DIR"
  printf 'owner=%s\npid=%s\nsince=%s\nnote=%s\n' \
    "$(claim_owner)" "$pid" "$(date '+%Y-%m-%d %H:%M')" "$note" > "$(claim_path "$id")"
}

task_claim() {
  local id="${1:-}"
  [ -n "$id" ] || die 'usage: ah task claim <task-id> ["note"]'
  shift
  require_task "$id"
  assert_claim_free "$id"
  _claim_write "$id" "$*" ""
  ok "claimed ${id} as $(claim_owner)"
}

# Held for the lifetime of a process, not forever: used by `ah run`.
claim_bind() {
  local id="$1" note="$2" pid="${3:-$$}"
  assert_claim_free "$id"
  _claim_write "$id" "$note" "$pid"
}

# Drop a claim this very process took. Never touches anyone else's.
claim_release_own() {
  local id="$1"
  [ -f "$(claim_path "$id")" ] || return 0
  [ "$(claim_field "$id" owner)" = "$(claim_owner)" ] || return 0
  [ "$(claim_field "$id" pid)" = "$$" ] || return 0
  rm -f "$(claim_path "$id")"
}

task_release() {
  local id="${1:-}" force="${2:-}"
  [ -n "$id" ] || die 'usage: ah task release <task-id> [--force]'
  [ -f "$(claim_path "$id")" ] || { info "task ${id} is not claimed"; return 0; }
  if claim_held_by_other "$id" && [ "$force" != "--force" ]; then
    die "task ${id} is held by $(claim_field "$id" owner) — use --force to break it"
  fi
  rm -f "$(claim_path "$id")"
  ok "released ${id}"
}
