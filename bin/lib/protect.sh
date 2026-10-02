#!/usr/bin/env bash
# ah protect — branch guardrail. Installs a pre-push hook into every workable
# repo so an agent cannot push to main/master/production/prod.

PROTECT_MARKER="ah-protect-hook-v1"
# dev joined the list on 2026-09-19: the owner's rule is that work reaches dev
# only as a pull request approved in Telegram, so a direct push to dev is now
# just as wrong as a push to main. bin/lib/ghflow.py enforces the same rule on
# the API side; this hook is the backstop on the git side.
PROTECTED_BRANCHES="main master production prod dev"

cmd_protect() {
  case "${1:-status}" in
    install)   shift; protect_install ;;
    status)    shift; protect_status ;;
    uninstall) shift; protect_uninstall ;;
    *) die "usage: ah protect {install|status|uninstall}" ;;
  esac
}

# One "<class>/<name><TAB><path>" line per project an agent may currently work on.
_protect_projects() {
  python3 - "$LIB" <<'PY'
import sys
sys.path.insert(0, sys.argv[1])
import state  # noqa: E402

for p in state.workable_projects():
    if p["git"]:
        print(f"{p['klass']}/{p['name']}\t{p['path']}")
PY
}

# Where git actually looks for hooks: core.hooksPath wins, otherwise the common
# git dir — which is shared by every worktree of the repo.
_protect_hooks_dir() {
  local repo="$1" custom common
  custom=$(git -C "$repo" config --get core.hooksPath 2>/dev/null || true)
  if [ -n "$custom" ]; then
    case "$custom" in
      /*) printf '%s\n' "$custom" ;;
      *)  printf '%s/%s\n' "$(git -C "$repo" rev-parse --show-toplevel)" "$custom" ;;
    esac
    return 0
  fi
  common=$(git -C "$repo" rev-parse --path-format=absolute --git-common-dir 2>/dev/null) \
    || return 1
  printf '%s/hooks\n' "$common"
}

_protect_write_hook() {
  local dest="$1"
  cat > "$dest" <<EOF
#!/usr/bin/env bash
# ${PROTECT_MARKER} — installed by \`ah protect\`. Do not edit by hand.
# Refuses any push whose destination branch is owner-controlled.
set -euo pipefail

PROTECTED_BRANCHES="${PROTECTED_BRANCHES}"

# git feeds one line per ref on stdin:
#   <local ref> <local sha> <remote ref> <remote sha>
# The remote ref is the destination, so this stays correct from a worktree too.
remote_name="\${1:-origin}"

blocked=""
stale=""
while read -r _local_ref local_sha remote_ref remote_sha; do
  [ -n "\${remote_ref:-}" ] || continue
  branch=\${remote_ref#refs/heads/}

  case " \${PROTECTED_BRANCHES} " in
    *" \${branch} "*) blocked="\${blocked} \${branch}"; continue ;;
  esac

  # Pull before push. Deleting a ref, or creating one that does not exist
  # upstream, has nothing to integrate.
  case "\$local_sha" in *[!0]*) : ;; *) continue ;; esac

  # Ask the remote what it actually has now, rather than trusting a possibly
  # stale remote-tracking ref. A failed fetch must not block the push.
  actual=\$(git ls-remote "\$remote_name" "\$remote_ref" 2>/dev/null | awk '{print \$1}' | head -1)
  [ -n "\$actual" ] || continue
  case "\$actual" in *[!0]*) : ;; *) continue ;; esac

  if ! git merge-base --is-ancestor "\$actual" "\$local_sha" 2>/dev/null; then
    stale="\${stale} \${branch}"
  fi
done

if [ -n "\$stale" ]; then
  cat >&2 <<MSG

  PUSH BLOCKED by ah protect — behind the remote
    branch(es):\${stale}

  The remote has commits your branch does not contain, so this push would
  either be rejected or clobber someone else's work. Integrate first:

      git pull --rebase \${remote_name} \${stale## }
      # resolve anything that conflicts, run the tests, then push again

MSG
  exit 1
fi

[ -n "\$blocked" ] || exit 0

cat >&2 <<MSG

  PUSH BLOCKED by ah protect
    protected branch(es):\${blocked}

  main, master, production and prod are owner-controlled and must never be
  pushed to by an agent. Push to dev or staging instead, for example:

      git push origin HEAD:dev

  A human can lift this with: ah protect uninstall

MSG
exit 1
EOF
  chmod 755 "$dest"
}

_protect_state() {
  local hook="$1"
  if [ ! -e "$hook" ]; then
    printf 'missing\n'
  elif grep -q "$PROTECT_MARKER" "$hook" 2>/dev/null; then
    printf 'installed\n'
  else
    printf 'foreign\n'
  fi
}

protect_install() {
  local slug path hooks hook found=0
  while IFS=$'\t' read -r slug path; do
    [ -n "$slug" ] || continue
    found=1
    assert_allowed_path "$path"
    if ! hooks=$(_protect_hooks_dir "$path"); then
      warn "${slug}: cannot resolve hooks directory — skipped"
      continue
    fi
    mkdir -p "$hooks"
    hook="${hooks}/pre-push"
    case "$(_protect_state "$hook")" in
      foreign)
        warn "${slug}: a pre-push hook already exists and is NOT ours — left untouched"
        info "  ${hook}"
        ;;
      *)
        _protect_write_hook "$hook"
        ok "${slug}: pre-push guard installed"
        info "  ${hook}"
        ;;
    esac
  done < <(_protect_projects)
  [ "$found" -eq 1 ] || info "no workable git projects — see agents/.scope"
}

protect_status() {
  local slug path hooks hook state found=0
  printf '\n%-24s %-10s %s\n' "PROJECT" "GUARD" "HOOK"
  printf '%s\n' "------------------------ ---------- ----"
  while IFS=$'\t' read -r slug path; do
    [ -n "$slug" ] || continue
    found=1
    if ! hooks=$(_protect_hooks_dir "$path"); then
      printf '%-24s %-10s %s\n' "$slug" "unknown" "(no git dir)"
      continue
    fi
    hook="${hooks}/pre-push"
    state=$(_protect_state "$hook")
    printf '%-24s %-10s %s\n' "$slug" "$state" "$hook"
  done < <(_protect_projects)
  [ "$found" -eq 1 ] || info "no workable git projects — see agents/.scope"
  printf '\nprotected branches: %s\n\n' "$PROTECTED_BRANCHES"
}

protect_uninstall() {
  local slug path hooks hook found=0
  while IFS=$'\t' read -r slug path; do
    [ -n "$slug" ] || continue
    found=1
    hooks=$(_protect_hooks_dir "$path") || continue
    hook="${hooks}/pre-push"
    case "$(_protect_state "$hook")" in
      installed) rm -f "$hook"; ok "${slug}: pre-push guard removed" ;;
      foreign)   warn "${slug}: pre-push hook is not ours — left in place" ;;
      *)         info "${slug}: no guard installed" ;;
    esac
  done < <(_protect_projects)
  [ "$found" -eq 1 ] || info "no workable git projects — see agents/.scope"
}
