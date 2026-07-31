#!/bin/sh
# run_sca.sh - dependency, secret and infrastructure-as-code scanning. Emits
# SARIF.
#
# Usage: run_sca.sh [path-or-image-ref]
#        A path that exists is scanned as a filesystem tree.
#        Anything else is treated as a container image reference.
#
# Trivy needs its vulnerability database. The first run downloads it, so the
# first run needs network access even though every later run can work from
# cache.

set -u

WRAPPER_NAME="sca"
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
LAB_ROOT=$(cd "$SCRIPT_DIR/.." && pwd)
# shellcheck source=_lib.sh
. "$SCRIPT_DIR/_lib.sh"

TARGET="${1:-.}"
OUT="$REPORT_DIR/sca.sarif"

require_tool trivy
ensure_report_dir

if [ -e "$TARGET" ]; then
    MODE="fs"
else
    MODE="image"
    log "'$TARGET' is not a path; scanning it as a container image reference."
fi

log "mode     $MODE"
log "target   $TARGET"
log "output   $OUT"

# Vendored and generated directories are skipped by default.
#
# The first real scan of this repository returned 63 findings, of which 51 were
# inside node_modules and .cache: Dockerfiles and Kubernetes manifests bundled
# as examples inside the AWS CDK package. They are not this repository's code
# and cannot be fixed here. Excluding them left 12 findings, all of them real
# and all in dependency files the repository owns.
#
# That ratio is the actual problem a gate has to solve. A gate that reports 20
# blocking findings a developer cannot act on gets switched off, and then the
# 5 that mattered are lost with it.
#
# The skip list is printed rather than applied silently. A scanner that quietly
# narrows its own scope is the same failure mode as a scanner that is not
# installed: the report looks clean because nothing looked.
#
# The patterns are made absolute on purpose. Trivy resolves a relative
# --skip-dirs glob against the *current working directory*, not against the
# scan target, so `**/node_modules` silently matched nothing when this wrapper
# was invoked from inside the repository being scanned. Same command, different
# cwd, 12 findings versus 63. Anchoring the pattern to the resolved target
# removes cwd from the equation.
SKIP_NAMES="node_modules .venv venv .cache vendor site-packages"

set --
if [ "$MODE" = "fs" ]; then
    if [ -d "$TARGET" ]; then
        ABS_TARGET=$(cd "$TARGET" && pwd)
    else
        ABS_TARGET=$(cd "$(dirname "$TARGET")" && pwd)/$(basename "$TARGET")
    fi

    if [ -n "${SEC_SCA_NO_SKIP:-}" ]; then
        log "skip     DISABLED by SEC_SCA_NO_SKIP - scanning vendored code too"
    else
        log "skip     $SKIP_NAMES (anchored to the scan target)"
        log "         (set SEC_SCA_NO_SKIP=1 to scan these as well)"
        for name in $SKIP_NAMES; do
            set -- "$@" --skip-dirs "$ABS_TARGET/**/$name" \
                        --skip-dirs "$ABS_TARGET/$name"
        done
    fi
    TARGET="$ABS_TARGET"
fi

# vuln    - known CVEs in dependencies and OS packages
# secret  - credentials committed into the tree
# misconfig - IaC misconfiguration (Terraform, K8s, Dockerfile, CloudFormation)
trivy "$MODE" \
    --format sarif \
    --output "$OUT" \
    --scanners vuln,secret,misconfig \
    --quiet \
    "$@" \
    "$TARGET"
RC=$?

if [ "$RC" -ne 0 ]; then
    log "trivy exited $RC."
    log "Trivy returns 0 even when it finds vulnerabilities unless --exit-code"
    log "is set, which this wrapper deliberately does not set. A non-zero exit"
    log "here therefore means the scan itself failed, not that findings exist."
    [ -s "$OUT" ] || write_empty_sarif "$OUT" "trivy"
    exit "$EXIT_SCAN_ERROR"
fi

[ -s "$OUT" ] || write_empty_sarif "$OUT" "trivy"

COUNT=$(python3 -c "
import json
try:
    d=json.load(open('$OUT'))
    print(sum(len(r.get('results',[])) for r in d.get('runs',[])))
except Exception:
    print('?')
" 2>/dev/null || echo '?')

log "completed. results in SARIF: $COUNT"
log "exit $EXIT_OK (scan completed; gate.py decides pass/fail)"
exit "$EXIT_OK"
