#!/usr/bin/env bash
# Bundle academy's widget and inject it into a copy of lsp-unified-app.html.
#
#   build-academy-widget.sh <source.html> <dest.html>
#
# Used by BOTH ops/prototypes/refresh.sh (at publish) and the pre-publish test
# run, so what the 92-test suite validates is byte-identical to what ships.
#
# Why a bundle step for a repo that deliberately has no build: the widget
# source is ES modules (widget/core/* is shared verbatim with accreditation),
# but the injected block must be a single inline non-module <script> —
# ES module imports do not load over file://, and README-HANDOFF.md's
# double-click flow is load-bearing. esbuild collapses it to one IIFE.
#
# The committed lsp-unified-app.html is NEVER modified: injection writes to a
# separate destination. AGENTS.md in that repo forbids refactoring the bundle,
# and this keeps the git copy exactly as handed over.
set -euo pipefail

SRC_HTML=${1:?usage: build-academy-widget.sh <source.html> <dest.html>}
DEST_HTML=${2:?usage: build-academy-widget.sh <source.html> <dest.html>}

ACADEMY=/opt/nexora-prototypes/src/academy
ESBUILD=/opt/nexora-prototypes/src/accreditation/nexaccred-react/node_modules/.bin/esbuild

[ -x "$ESBUILD" ] || { echo "build-academy-widget: esbuild not found at $ESBUILD" >&2; exit 1; }
[ -f "$ACADEMY/widget/main.js" ] || { echo "build-academy-widget: widget/main.js missing — run sync-widget.sh academy first" >&2; exit 1; }

tmp_js=$(mktemp /tmp/academy-widget.XXXXXX.js)
trap 'rm -f "$tmp_js"' EXIT

"$ESBUILD" "$ACADEMY/widget/main.js" \
    --bundle --format=iife --minify --target=es2019 \
    --outfile="$tmp_js" >/dev/null

# A literal </script> inside the bundle would close the tag early and inject
# markup into the page. esbuild has no reason to emit one, but check rather
# than assume -- this is the one failure that would deface the published app.
if grep -q '</script' "$tmp_js"; then
    echo "build-academy-widget: bundle contains '</script' — refusing to inject" >&2
    exit 1
fi

# Append-only: insert between the bundle's closing </script> (line 177) and
# </body> (line 178). Nothing above that point is touched, least of all the
# 412,516-character minified line 21.
python3 - "$SRC_HTML" "$tmp_js" "$DEST_HTML" <<'PY'
import sys
src_html, js_path, dest_html = sys.argv[1:4]
html = open(src_html, encoding='utf-8').read()
js = open(js_path, encoding='utf-8').read()

marker = '</script>\n</body>'
if marker not in html:
    sys.exit('build-academy-widget: expected "</script>\\n</body>" not found — bundle shape changed, refusing to inject')
if 'nexreadiness' in html:
    sys.exit('build-academy-widget: source already contains the widget — refusing to double-inject')

block = '</script>\n<script>\n/* AI Assistant review widget — injected at publish by '\
        'ops/prototypes/build-academy-widget.sh. Not part of the committed bundle. */\n' \
        + js + '\n</script>\n</body>'
open(dest_html, 'w', encoding='utf-8').write(html.replace(marker, block, 1))
PY

echo "injected widget: $SRC_HTML -> $DEST_HTML ($(wc -c <"$DEST_HTML") bytes)"
