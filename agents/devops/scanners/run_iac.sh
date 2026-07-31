#!/bin/sh
# run_iac.sh - scan infrastructure-as-code for misconfiguration.
#
# Engine: Trivy in `config` mode. It covers Terraform, CloudFormation, Helm,
# Kubernetes manifests and Dockerfiles from one binary, which keeps the tool
# count down without tying the agent to a cloud vendor.
#
# Usage: sh run_iac.sh [target]     (target defaults to the workspace root)
#
# Exit codes follow scanners/_lib.sh. Findings do not change the exit code.

set -u

WRAPPER_NAME=iac
LAB_ROOT=$(cd "$(dirname "$0")/.." && pwd)
# shellcheck source=_lib.sh
. "$LAB_ROOT/scanners/_lib.sh"

TARGET="${1:-$(cd "$LAB_ROOT/../.." && pwd)}"

if [ ! -e "$TARGET" ]; then
    log "target does not exist: $TARGET"
    exit "$EXIT_SCAN_ERROR"
fi

require_tool trivy
ensure_report_dir

ABS_TARGET=$(abs_target "$TARGET")
OUT="$REPORT_DIR/trivy-config.sarif"

# Anchor skip patterns to the resolved target. Trivy interprets --skip-dirs
# globs against the current working directory, so an unanchored pattern matches
# nothing when the wrapper is invoked from elsewhere -- the security agent
# measured the same command yielding 12 findings versus 63 for this reason.
SKIP_NAMES="node_modules .venv venv .cache vendor site-packages cdk.out .terraform"

set --
for name in $SKIP_NAMES; do
    set -- "$@" --skip-dirs "$ABS_TARGET/**/$name"
done

log "scanning $ABS_TARGET for IaC misconfiguration"

trivy config "$ABS_TARGET" \
    --format sarif \
    --output "$OUT" \
    --exit-code 0 \
    "$@"
STATUS=$?

if [ "$STATUS" -ne 0 ]; then
    log "trivy exited $STATUS"
    # A failed run must not leave a stale or absent report that the gate would
    # read as a clean result.
    write_empty_sarif "$OUT" "trivy-config"
    exit "$EXIT_SCAN_ERROR"
fi

if [ ! -s "$OUT" ]; then
    # Trivy writes nothing when it finds no IaC files at all. The gate needs a
    # well-formed document either way.
    write_empty_sarif "$OUT" "trivy-config"
    log "no IaC files found under $ABS_TARGET"
fi

log "report: $OUT"
exit "$EXIT_OK"
