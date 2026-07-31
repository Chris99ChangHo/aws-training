#!/bin/sh
# run_sast.sh - static analysis of source code. Emits SARIF.
#
# Usage: run_sast.sh [target-path]
#        target-path defaults to the current directory.
#
# Ruleset choice: pinned registry packs, never `--config auto`. `auto` resolves
# rules over the network per-run, which makes results non-reproducible, and it
# reports project metadata back to the vendor's service. Pinning keeps the scan
# reproducible and keeps a "vendor-agnostic" agent from quietly depending on
# one vendor's rule service at scan time.
#
# Override with SEC_SAST_CONFIG to scan fully offline against a local ruleset:
#   SEC_SAST_CONFIG=./rules run_sast.sh src

set -u

WRAPPER_NAME="sast"
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
LAB_ROOT=$(cd "$SCRIPT_DIR/.." && pwd)
# shellcheck source=_lib.sh
. "$SCRIPT_DIR/_lib.sh"

TARGET="${1:-.}"
OUT="$REPORT_DIR/sast.sarif"

require_tool semgrep
ensure_report_dir

if [ ! -e "$TARGET" ]; then
    log "target does not exist: $TARGET"
    exit "$EXIT_SCAN_ERROR"
fi

# Default packs: injection/authz/crypto classes, hardcoded secrets, OWASP Top
# Ten mappings. Local rules under rules/ are added when present.
if [ -n "${SEC_SAST_CONFIG:-}" ]; then
    set -- --config "$SEC_SAST_CONFIG"
else
    set -- --config p/security-audit --config p/secrets --config p/owasp-top-ten
    if [ -d "$LAB_ROOT/scanners/rules" ] && \
       [ -n "$(ls -A "$LAB_ROOT/scanners/rules" 2>/dev/null | grep -v '^\.gitkeep$')" ]; then
        set -- "$@" --config "$LAB_ROOT/scanners/rules"
        log "including local rules from scanners/rules"
    fi
fi

log "scanning $TARGET"
log "output   $OUT"

# --metrics=off keeps scan telemetry local. If your semgrep build rejects the
# flag, drop it and record that telemetry is enabled.
semgrep scan "$@" \
    --metrics=off \
    --sarif \
    --output "$OUT" \
    --quiet \
    "$TARGET"
RC=$?

# 0 = no findings, 1 = findings. Both mean the scan worked.
case "$RC" in
    0|1) ;;
    *)
        log "semgrep exited $RC, which is neither 'clean' (0) nor 'findings' (1)."
        log "Treating this as a scan failure so the gate does not read a"
        log "truncated report as a pass."
        [ -s "$OUT" ] || write_empty_sarif "$OUT" "semgrep"
        exit "$EXIT_SCAN_ERROR"
        ;;
esac

[ -s "$OUT" ] || write_empty_sarif "$OUT" "semgrep"

COUNT=$(python3 -c "
import json,sys
try:
    d=json.load(open('$OUT'))
    print(sum(len(r.get('results',[])) for r in d.get('runs',[])))
except Exception:
    print('?')
" 2>/dev/null || echo '?')

log "completed. results in SARIF: $COUNT"
log "exit $EXIT_OK (scan completed; gate.py decides pass/fail)"
exit "$EXIT_OK"
