#!/bin/sh
# run_dast.sh - active scanning of a running target. Emits SARIF.
#
# Usage: run_dast.sh <target-url-or-host>
#
# This wrapper re-checks the authorisation scope itself rather than trusting
# that something upstream already did. The PreToolUse hook only sees shell
# commands; when the agent reaches this scanner through the MCP server the hook
# is never invoked, so the hook alone would be a control with a hole in it.
# Both paths call load_scope/in_scope from _scope_lib.sh, so there is one rule
# and two places that enforce it.

set -u

WRAPPER_NAME="dast"
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
LAB_ROOT=$(cd "$SCRIPT_DIR/.." && pwd)
# shellcheck source=_lib.sh
. "$SCRIPT_DIR/_lib.sh"
# shellcheck source=_scope_lib.sh
. "$SCRIPT_DIR/_scope_lib.sh"

SCOPE_FILE="$LAB_ROOT/.sec-scope"
OUT="$REPORT_DIR/dast.sarif"

if [ "$#" -lt 1 ] || [ -z "${1:-}" ]; then
    log "usage: run_dast.sh <target-url-or-host>"
    log "Refusing to scan an unspecified target."
    exit "$EXIT_REFUSED"
fi

TARGET="$1"

# --- authorisation check, before anything touches the network ---------------

SCOPE_HOSTS=$(load_scope "$SCOPE_FILE") || {
    log "authorisation file missing or empty: $SCOPE_FILE"
    log "Refusing to scan without a record of what is permitted."
    exit "$EXIT_REFUSED"
}

HOST=$(normalise_host "$TARGET")

if [ -z "$HOST" ]; then
    log "could not extract a host from target: $TARGET"
    exit "$EXIT_REFUSED"
fi

if ! in_scope "$HOST" "$SCOPE_HOSTS"; then
    log "REFUSED: '$HOST' is not in the authorised scope."
    log "Authorised hosts ($SCOPE_FILE):"
    printf '%s\n' "$SCOPE_HOSTS" | sed 's/^/         - /' >&2
    log "Active scanning of a host you are not authorised to test is unlawful"
    log "in most jurisdictions. A human must add the host to .sec-scope after"
    log "confirming ownership."
    exit "$EXIT_REFUSED"
fi

log "target   $TARGET  (host '$HOST' is in scope)"

require_tool nuclei
ensure_report_dir

log "output   $OUT"

# -exclude-tags dos,intrusive: an authorised target is still a target you have
# to hand back working. Denial-of-service and intrusive templates are excluded
# by default; a human can override by editing this line.
#
# -duc disables the update check that otherwise runs on every invocation. A
# scan should make exactly the network connections the operator asked for, and
# a version ping to the vendor is not one of them.
nuclei \
    -target "$TARGET" \
    -sarif-export "$OUT" \
    -severity critical,high,medium \
    -exclude-tags dos,intrusive \
    -duc \
    -no-color \
    -silent
RC=$?

if [ "$RC" -ne 0 ]; then
    log "nuclei exited $RC; treating as scan failure."
    [ -s "$OUT" ] || write_empty_sarif "$OUT" "nuclei"
    exit "$EXIT_SCAN_ERROR"
fi

[ -s "$OUT" ] || write_empty_sarif "$OUT" "nuclei"

# Normalise invocations[].executionSuccessful.
#
# Measured with nuclei v3.11.0: it writes `executionSuccessful: false` into its
# SARIF export even when the scan completed and produced findings, which makes
# the gate refuse the report. The reasoning and the failure pairing it creates
# are documented in scanners/normalize_sarif.py.
#
# Only reached when nuclei exited 0, so a genuinely failed scan never gets
# marked successful -- that path returned above.
if command -v python3 >/dev/null 2>&1; then
    python3 "$SCRIPT_DIR/normalize_sarif.py" "$OUT" || {
        log "could not normalise $OUT; the gate will refuse it."
        exit "$EXIT_SCAN_ERROR"
    }
else
    log "python3 not found; leaving executionSuccessful as nuclei wrote it."
    log "The gate will refuse this report. See docs/setup-sec-tools.md."
fi

log "completed."
log "exit $EXIT_OK (scan completed; gate.py decides pass/fail)"
exit "$EXIT_OK"
