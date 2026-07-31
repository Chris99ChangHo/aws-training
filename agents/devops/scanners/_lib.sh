#!/bin/sh
# _lib.sh - shared plumbing for the DevOps linter wrappers.
#
# Exit code convention. Identical to the security agent's, because the shared
# gate in agents/core reads it and CI callers should not need to learn two
# contracts:
#
#   0  the linter ran to completion. Findings may or may not exist.
#   2  the wrapper refused to run (a state-changing command was requested).
#   3  a required linter is not installed.
#   4  the linter itself failed (bad flags, unreadable target).
#
# Findings never change the exit code. Linters disagree here -- hadolint and
# actionlint exit 1 when they find something, Trivy exits 0 unless asked
# otherwise -- so a caller that treats non-zero as failure would report a clean
# repository as a broken build. Deciding whether findings are acceptable is
# agents/core/gate/gate.py's job, and it reads the SARIF to do it.
#
# AGENT_REPORT_DIR, not SEC_REPORT_DIR: this agent has its own reports. The two
# libraries are still separate copies -- see the seam table in agents/README.md
# for why extraction is deferred.

EXIT_OK=0
EXIT_REFUSED=2
EXIT_TOOL_MISSING=3
EXIT_SCAN_ERROR=4

# Reports live next to the agent, not next to the caller's cwd, so that repeated
# runs from different directories do not scatter SARIF files across the repo.
REPORT_DIR="${AGENT_REPORT_DIR:-$LAB_ROOT/reports}"

log() {
    printf '[%s] %s\n' "${WRAPPER_NAME:-devops}" "$*" >&2
}

die_missing() {
    log "$1 is not installed."
    log "Install it with docs/setup-devops-tools.md, then re-run."
    log "Exiting $EXIT_TOOL_MISSING (tool missing), not $EXIT_OK: an absent"
    log "linter is not a clean result and must not be reported as one."
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

# Emit a valid empty SARIF run so the merge and gate steps always have something
# well-formed to read, even when a linter produced nothing. Without this, "no
# file" and "no findings" look the same to the gate, and absence gets reported
# as cleanliness.
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

# Resolve a target to an absolute path. Linter path filters are interpreted
# against the target, not the caller's cwd -- the security agent measured the
# same command producing 12 findings versus 63 depending on where it ran.
abs_target() {
    if [ -d "$1" ]; then
        (cd "$1" && pwd)
    else
        printf '%s/%s\n' "$(cd "$(dirname "$1")" && pwd)" "$(basename "$1")"
    fi
}
