#!/bin/sh
# _lib.sh - shared plumbing for the scanner wrappers.
#
# Exit code convention. This is the whole reason the wrappers exist:
#
#   0  the scan ran to completion. Findings may or may not exist.
#   2  the wrapper refused to run (authorisation scope violation).
#   3  a required scanner is not installed.
#   4  the scanner itself failed (bad flags, unreadable target, no DB).
#
# Findings never change the exit code. Scanners disagree here — Semgrep exits 1
# when it finds something, Trivy exits 0 unless you ask otherwise — so a caller
# that treats non-zero as failure will report a clean repo as a broken build,
# and a `set -e` pipeline will abort after the first scanner that finds
# anything and silently skip the rest. Deciding whether findings are
# acceptable is gate.py's job, and it reads the SARIF to do it.

EXIT_OK=0
EXIT_REFUSED=2
EXIT_TOOL_MISSING=3
EXIT_SCAN_ERROR=4

# Reports live next to the lab, not next to the caller's cwd, so that repeated
# runs from different directories do not scatter SARIF files across the repo.
REPORT_DIR="${SEC_REPORT_DIR:-$LAB_ROOT/reports}"

log() {
    printf '[%s] %s\n' "${WRAPPER_NAME:-sec}" "$*" >&2
}

die_missing() {
    log "$1 is not installed."
    log "Install it with docs/setup-sec-tools.md, then re-run."
    log "Exiting $EXIT_TOOL_MISSING (tool missing), not $EXIT_OK: an absent"
    log "scanner is not a clean scan result and must not be reported as one."
    exit "$EXIT_TOOL_MISSING"
}

require_tool() {
    command -v "$1" >/dev/null 2>&1 || die_missing "$1"
}

ensure_report_dir() {
    mkdir -p "$REPORT_DIR" || {
        log "cannot create report directory: $REPORT_DIR"
        exit "$EXIT_SCAN_ERROR"
    }
}

# Emit a valid empty SARIF run so downstream merging and gating always have
# something well-formed to read, even when a scanner produced nothing.
write_empty_sarif() {
    _out="$1"
    _tool="$2"
    cat > "$_out" <<EOF
{
  "\$schema": "https://json.schemastore.org/sarif-2.1.0.json",
  "version": "2.1.0",
  "runs": [
    {
      "tool": { "driver": { "name": "$_tool", "rules": [] } },
      "results": [],
      "invocations": [ { "executionSuccessful": true } ]
    }
  ]
}
EOF
}
