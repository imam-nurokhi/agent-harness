#!/usr/bin/env bash
# Prove, from outside and without credentials, that agents.nexoratech.co no
# longer rate-limits a normal browser page load.
#
# The host answers 401 for a failed Basic Auth and 429 for a rate-limit
# rejection, so the two are distinguishable with no secret in hand. That makes
# this script safe to re-run and safe to hand to the owner.
#
# Four waves of 60 parallel asset requests approximate four page loads in quick
# succession -- roughly what opening the dashboard and the n8n editor costs.
# PASS means every response was 401. A single 429 is a failure.
set -uo pipefail

HOST="${1:-agents.nexoratech.co}"
WAVES="${WAVES:-4}"
PER_WAVE="${PER_WAVE:-60}"
OUT="$(mktemp -d)"
trap 'rm -rf "$OUT"' EXIT

echo "probing https://${HOST}/automation/assets/ -- ${WAVES} waves x ${PER_WAVE} parallel"

total_429=0
total=0
for wave in $(seq 1 "$WAVES"); do
    : > "$OUT/wave"
    for n in $(seq 1 "$PER_WAVE"); do
        curl -s -o /dev/null -w '%{http_code}\n' --max-time 20 \
            "https://${HOST}/automation/assets/probe-${wave}-${n}-$$.js" >> "$OUT/wave" &
    done
    wait
    got_429=$(grep -c '^429$' "$OUT/wave" || true)
    got_401=$(grep -c '^401$' "$OUT/wave" || true)
    other=$(grep -vc -e '^429$' -e '^401$' "$OUT/wave" || true)
    total_429=$((total_429 + got_429))
    total=$((total + PER_WAVE))
    printf 'wave %d: %3d x 401  %3d x 429  %3d other\n' "$wave" "$got_401" "$got_429" "$other"
done

# Second defect, independent of the rate limit: n8n 2.x serves its bundles from
# the server root, so if the /automation/ proxy_pass keeps the prefix every
# asset comes back as the SPA catch-all (200 text/html) and the editor renders
# blank. Needs credentials, so it only runs when AUTH is set:
#   AUTH=user:pass ./ops/nginx/verify_rate_limit.sh
asset_fail=0
if [ -n "${AUTH:-}" ]; then
    echo "---"
    echo "checking that /automation/ assets are served as assets, not as index.html"
    html=$(curl -s -u "$AUTH" --max-time 20 "https://${HOST}/automation/")
    refs=$(printf '%s' "$html" | grep -oE '(src|href)="/automation/(assets|static)/[^"]+"' \
           | sed 's/.*="//;s/"//' | sort -u | head -8)
    if [ -z "$refs" ]; then
        echo "  WARN: no asset references found in /automation/ -- is the login page loading?"
        asset_fail=1
    fi
    for ref in $refs; do
        read -r code ctype <<<"$(curl -s -u "$AUTH" -o /dev/null \
            -w '%{http_code} %{content_type}' --max-time 20 "https://${HOST}${ref}")"
        case "$ctype" in
            text/html*) printf '  BLANK-PAGE SIGNATURE %s %s %s\n' "$code" "$ctype" "$ref"; asset_fail=1 ;;
            *)          printf '  ok %s %-28s %s\n' "$code" "$ctype" "$ref" ;;
        esac
    done
else
    echo "---"
    echo "(set AUTH=user:pass to also check that assets are not served as index.html)"
fi

echo "---"
if [ "$total_429" -eq 0 ] && [ "$asset_fail" -eq 0 ]; then
    echo "PASS: 0/${total} rate-limited${AUTH:+, assets served with real content types}"
    exit 0
fi
[ "$total_429" -gt 0 ] && \
    echo "FAIL: ${total_429}/${total} rate-limited (429) -- sustained rate is still too low"
[ "$asset_fail" -ne 0 ] && \
    echo "FAIL: /automation/ assets come back as text/html -- the proxy_pass is keeping the prefix"
exit 1
