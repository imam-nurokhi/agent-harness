#!/usr/bin/env bash
# Copy the accreditation repo's widget/core/ (the framework-agnostic
# store/collector/identity/registry + the vanilla DOM shell) into another
# app's source tree, so gate/sign-off/audit semantics can never diverge
# between apps that share this core (docs/ai-assistant-widget-rollout-
# plan.md Fase 3).
#
#   ops/prototypes/sync-widget.sh academy
#
# ACADEMY ONLY, on purpose, this pass. The owner's order is accreditation
# then academy; service-desk is explicitly deferred. Service-desk was also
# meant to be the cheap, 0-test "canary" that shakes out a bad core change
# before it reaches academy's 92-test-guarded bundle -- skipping it means
# academy is the first real consumer, so this script refuses to quietly
# widen scope to service-desk (or "all three") until that work is actually
# scheduled. Lift the allowlist below when it is.
set -euo pipefail

SRC=/opt/nexora-prototypes/src/accreditation/nexaccred-react/src/widget/core
ALLOWED_TARGETS=(academy)

target=${1:-}
if [ -z "$target" ]; then
    echo "usage: sync-widget.sh <app>" >&2
    echo "no app given -- refusing to guess (bare/'all' invocation is not supported)" >&2
    exit 2
fi

allowed=0
for a in "${ALLOWED_TARGETS[@]}"; do
    [ "$a" = "$target" ] && allowed=1
done
if [ "$allowed" -ne 1 ]; then
    echo "sync-widget.sh: '$target' is not synced this pass (deferred, out of scope)." >&2
    echo "Only ${ALLOWED_TARGETS[*]} is allowed until service-desk work is scheduled." >&2
    exit 2
fi

case "$target" in
    academy)
        DEST=/opt/nexora-prototypes/src/academy/widget/core
        ;;
esac

[ -d "$SRC" ] || { echo "sync-widget.sh: source $SRC not found" >&2; exit 1; }

mkdir -p "$DEST"
# Delete first so a file removed from core/ doesn't linger in the copy.
rm -rf "${DEST:?}"/*
cp -r "$SRC"/. "$DEST/"

echo "synced widget/core/ -> $DEST"
find "$DEST" -maxdepth 1 -type f -name '*.js' -exec basename {} \; | sort
