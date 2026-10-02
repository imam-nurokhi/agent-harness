#!/usr/bin/env bash
# Rebuild and republish the three review prototypes from their dev branches.
#
#   ops/prototypes/refresh.sh            # all three
#   ops/prototypes/refresh.sh academy    # just one
#
# Safe to re-run. Each app is staged into a temporary directory and only
# swapped into place once its build has succeeded, so a failed build leaves
# whatever is currently published untouched.
#
# The repos are public, so this needs no credential. If they are ever made
# private again this script stops working and the fix is a read-only token in
# .env -- NOT a deploy key, which NexoraTechTeam policy disables org-wide.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC=/opt/nexora-prototypes/src
WEB=/var/www/prototypes
APPS=("${@:-academy accreditation service-desk}")
read -r -a APPS <<< "${APPS[*]}"

log() { printf '\n== %s\n' "$*"; }

pull() {
    local repo=$1
    if [ -d "$SRC/$repo/.git" ]; then
        git -C "$SRC/$repo" fetch --depth 1 origin dev -q
        git -C "$SRC/$repo" reset --hard -q FETCH_HEAD
    else
        git clone --depth 1 -b dev -q "https://github.com/NexoraTechTeam/$repo.git" "$SRC/$repo"
    fi
    git -C "$SRC/$repo" --no-pager log -1 --format='   %h %ad %s' --date=short
}

publish() {   # publish <target-dir-name> <source-path-or-dir>
    local name=$1 src=$2
    local dest="$WEB/$name"
    rm -rf "$dest.new"
    mkdir -p "$dest.new"
    if [ -d "$src" ]; then cp -r "$src/." "$dest.new/"; else cp "$src" "$dest.new/index.html"; fi
    chown -R www-data:www-data "$dest.new"
    find "$dest.new" -type d -exec chmod 755 {} +
    find "$dest.new" -type f -exec chmod 644 {} +
    rm -rf "$dest.old"
    [ -d "$dest" ] && mv "$dest" "$dest.old"
    mv "$dest.new" "$dest"
    rm -rf "$dest.old"
    echo "   published -> $dest"
}

for app in "${APPS[@]}"; do
  case "$app" in
    academy)
      log "academy"
      pull academy
      # A single self-contained HTML file; nothing to build. It injects a
      # Google Fonts stylesheet at runtime, which is why /academy/ carries a
      # CSP that permits fonts.googleapis.com and fonts.gstatic.com.
      #
      # The AI Assistant review widget is injected HERE, at publish time only —
      # never committed into lsp-unified-app.html. That repo's AGENTS.md
      # forbids refactoring the minified bundle, and leaving the committed file
      # untouched is what keeps README-HANDOFF.md's double-click file:// flow
      # working. The injected copy is written to a temp file; the source is
      # read-only to this step. Verified 2026-09-18: ./run-tests.sh is 92/92
      # both before and after injection.
      "$SCRIPT_DIR/sync-widget.sh" academy
      staged_academy=$(mktemp -d)/lsp-unified-app.html
      "$SCRIPT_DIR/build-academy-widget.sh" \
          "$SRC/academy/lsp-unified-app.html" "$staged_academy"
      publish academy "$staged_academy"
      rm -rf "$(dirname "$staged_academy")"
      ;;

    accreditation)
      log "accreditation"
      pull accreditation
      cd "$SRC/accreditation/nexaccred-react"
      PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 npm install --no-audit --no-fund --silent
      # build:standalone, NOT build. The ordinary build expects nexaccred-api
      # on localhost:3001; the standalone entry point inlines sample data and
      # needs no backend, which is what a review surface should be.
      npm run build:standalone --silent
      publish accreditation "$SRC/accreditation/nexaccred-react/dist-standalone/index.standalone.html"
      ;;

    service-desk)
      log "service-desk"
      pull service-desk
      cd "$SRC/service-desk"
      npm install --no-audit --no-fund --silent
      # The repo pulls Tailwind from cdn.tailwindcss.com. Vendor it, because
      # the vhost CSP is script-src 'self' and an unstyled page is the result
      # otherwise. Re-fetched each run so it tracks the CDN.
      mkdir -p public
      curl -sSfL --max-time 60 -o public/tailwind.js https://cdn.tailwindcss.com
      sed -i 's|<script src="https://cdn.tailwindcss.com"></script>|<script src="/tailwind.js"></script>|' index.html
      # --base is load-bearing: served from /servicedesk/, a default build
      # would reference /assets/... at the server root, where the Command
      # Center answers instead. Same class of failure as the /automation/
      # prefix bug in ops/nginx/README.md.
      npx vite build --base=/servicedesk/
      publish servicedesk "$SRC/service-desk/dist"
      ;;

    *) echo "unknown app: $app" >&2; exit 2 ;;
  esac
done

log "verify"
exec "$SCRIPT_DIR/verify.sh"
