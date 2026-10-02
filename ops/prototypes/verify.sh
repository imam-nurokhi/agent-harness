#!/usr/bin/env bash
# Prove the three review prototypes are actually serving -- not merely
# answering 200.
#
# ops/nginx/README.md records why this exists: /automation/assets/*.js once
# returned 200 with Content-Type: text/html and a status-only check called the
# stack healthy while every bundle was broken. So this checks, per app:
#
#   * 401 without credentials            (auth is really on)
#   * 200 text/html with credentials     (the page is served)
#   * every asset the page references returns its OWN content type
#   * a deliberately absent asset returns 404, not the SPA shell as 200
#   * the prototype credential cannot open the Command Center at /
set -euo pipefail

HOST=${HOST:-https://agents.nexoratech.co}
CREDFILE=${CREDFILE:-/root/prototypes-basic-auth.txt}
USER=$(awk '/^user:/{print $2}' "$CREDFILE")
PASS=$(awk '/^password:/{print $2}' "$CREDFILE")
fail=0

probe() { curl -sS -o /dev/null -w "$2" ${3:+-u "$3"} "$1"; }
check() { # check <label> <actual> <expected>
    if [ "$2" = "$3" ]; then printf '  ok    %-48s %s\n' "$1" "$2"
    else printf '  FAIL  %-48s got %s, want %s\n' "$1" "$2" "$3"; fail=1; fi
}

for app in academy accreditation servicedesk; do
    echo "== /$app/"
    check "401 without credentials" \
          "$(probe "$HOST/$app/" '%{http_code}')" 401
    check "200 with credentials" \
          "$(probe "$HOST/$app/" '%{http_code}' "$USER:$PASS")" 200
    check "served as text/html" \
          "$(probe "$HOST/$app/" '%{content_type}' "$USER:$PASS")" text/html
    check "absent asset 404s, not SPA shell" \
          "$(probe "$HOST/$app/assets/definitely-not-here.js" '%{http_code}' "$USER:$PASS")" 404

    # Every script/style the page actually references must come back as itself.
    page=$(curl -sS -u "$USER:$PASS" "$HOST/$app/")
    while read -r ref; do
        [ -z "$ref" ] && continue
        case "$ref" in http*) continue ;; esac   # third-party origins are not ours to serve
        ct=$(probe "$HOST$ref" '%{content_type}' "$USER:$PASS")
        case "$ct" in
            *javascript*|*css*|*json*|*font*|*image*) printf '  ok    %-48s %s\n' "asset $ref" "$ct" ;;
            *) printf '  FAIL  %-48s %s (SPA catch-all?)\n' "asset $ref" "$ct"; fail=1 ;;
        esac
    done < <(printf '%s' "$page" | grep -oE '(src|href)="[^"]*\.(js|mjs|css)"' | sed 's/.*="//;s/"//')
done

echo "== /widget-feedback/ (feedback collector, additive)"
check "401 without credentials" \
      "$(probe "$HOST/widget-feedback/healthz" '%{http_code}')" 401
check "200 with credentials" \
      "$(probe "$HOST/widget-feedback/healthz" '%{http_code}' "$USER:$PASS")" 200

echo "== isolation"
check "prototype credential cannot open /" \
      "$(probe "$HOST/" '%{http_code}' "$USER:$PASS")" 401

echo "== neighbours untouched"
check "Command Center still challenges" "$(probe "$HOST/" '%{http_code}')" 401
check "n8n still challenges"            "$(probe "$HOST/automation/" '%{http_code}')" 401
check "academy-test still serves"       "$(probe https://academy-test.nexoratech.co/ '%{http_code}')" 200

[ $fail -eq 0 ] && echo && echo "ALL CHECKS PASSED" || { echo; echo "FAILURES ABOVE"; exit 1; }
