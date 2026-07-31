#!/bin/sh
# run_operability.sh - check infrastructure definitions for operability gaps.
#
# Replaces an earlier run_iac.sh that shelled out to `trivy config`. That was
# measured to be a duplicate: on the same fixture it produced the same 13 rule
# IDs as the security agent's run_sca.sh, which already runs Trivy with
# --scanners misconfig. Two agents reporting identical findings is not coverage,
# it is confusion about which one owns the check.
#
# This wrapper asks a different question. The security agent asks "is this
# vulnerable"; this asks "can this be deployed and operated" -- state locking,
# version pinning, readiness probes, replica counts, rollback paths, pipeline
# reproducibility. No security scanner reports those.
#
# Usage: sh run_operability.sh [target]   (target defaults to the workspace root)
#
# Exit codes follow scanners/_lib.sh. Findings do not change the exit code.

set -u

WRAPPER_NAME=operability
LAB_ROOT=$(cd "$(dirname "$0")/.." && pwd)
# shellcheck source=_lib.sh
. "$LAB_ROOT/scanners/_lib.sh"

TARGET="${1:-$(cd "$LAB_ROOT/../.." && pwd)}"

if [ ! -e "$TARGET" ]; then
    log "target does not exist: $TARGET"
    exit "$EXIT_SCAN_ERROR"
fi

ensure_report_dir
ABS_TARGET=$(abs_target "$TARGET")
OUT="$REPORT_DIR/operability.sarif"

# Prefer the agent's own environment. Kubernetes manifests and GitHub Actions
# workflows are YAML, and Python has no YAML parser in its standard library, so
# the Terraform checks run anywhere while the YAML checks need requirements.txt
# installed. The checker reports exit 3 when YAML files are present but
# unparseable, rather than counting them as clean.
if [ -x "$LAB_ROOT/.venv/bin/python3" ]; then
    PY="$LAB_ROOT/.venv/bin/python3"
else
    PY=python3
    log "using system python3; if YAML checks report as not run, install:"
    log "  python3 -m venv $LAB_ROOT/.venv"
    log "  $LAB_ROOT/.venv/bin/pip install -r $LAB_ROOT/requirements.txt"
fi

log "checking $ABS_TARGET for operability gaps"

"$PY" "$LAB_ROOT/scanners/operability_check.py" "$ABS_TARGET" "$OUT"
STATUS=$?

case "$STATUS" in
    0)
        log "report: $OUT"
        exit "$EXIT_OK"
        ;;
    "$EXIT_TOOL_MISSING")
        # The report still holds whatever could be checked; the caller is told
        # that part of the target was skipped.
        log "report: $OUT (incomplete)"
        exit "$EXIT_TOOL_MISSING"
        ;;
    *)
        log "operability check failed (exit $STATUS)"
        write_empty_sarif "$OUT" "operability-check"
        exit "$EXIT_SCAN_ERROR"
        ;;
esac
