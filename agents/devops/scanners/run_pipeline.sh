#!/bin/sh
# run_pipeline.sh - lint container builds and CI workflow definitions.
#
# Two linters, one wrapper, because they answer the same question ("will this
# build and deploy behave") and a reviewer wants one report:
#   hadolint    Dockerfile hygiene
#   actionlint  GitHub Actions workflow correctness
#
# Usage: sh run_pipeline.sh [target]    (target defaults to the workspace root)
#
# Exit codes follow scanners/_lib.sh. Findings do not change the exit code.
#
# Neither linter is installed on the development host this was written on, so
# the missing-tool path is the one that has been exercised end to end. That is
# recorded in README.md rather than glossed over.

set -u

WRAPPER_NAME=pipeline
LAB_ROOT=$(cd "$(dirname "$0")/.." && pwd)
# shellcheck source=_lib.sh
. "$LAB_ROOT/scanners/_lib.sh"

TARGET="${1:-$(cd "$LAB_ROOT/../.." && pwd)}"

if [ ! -e "$TARGET" ]; then
    log "target does not exist: $TARGET"
    exit "$EXIT_SCAN_ERROR"
fi

ABS_TARGET=$(abs_target "$TARGET")
ensure_report_dir

# Both linters are optional individually but at least one must exist, otherwise
# this wrapper would report success while checking nothing.
HAVE_HADOLINT=0
HAVE_ACTIONLINT=0
command -v hadolint   >/dev/null 2>&1 && HAVE_HADOLINT=1
command -v actionlint >/dev/null 2>&1 && HAVE_ACTIONLINT=1

if [ "$HAVE_HADOLINT" -eq 0 ] && [ "$HAVE_ACTIONLINT" -eq 0 ]; then
    log "neither hadolint nor actionlint is installed."
    log "Install them with docs/setup-devops-tools.md, then re-run."
    log "Exiting $EXIT_TOOL_MISSING (tool missing), not $EXIT_OK: no linter ran,"
    log "so this is not a clean result and must not be reported as one."
    exit "$EXIT_TOOL_MISSING"
fi

STATUS="$EXIT_OK"

# --- Dockerfile -----------------------------------------------------------

DOCKER_OUT="$REPORT_DIR/hadolint.sarif"
if [ "$HAVE_HADOLINT" -eq 1 ]; then
    # -print0 / xargs -0 would need the file list in one call, but hadolint
    # accepts many paths, and a Dockerfile name is not user input here.
    set -f
    DOCKERFILES=$(find "$ABS_TARGET" \
        -type d \( -name node_modules -o -name .venv -o -name .git \) -prune -o \
        -type f \( -name 'Dockerfile' -o -name 'Dockerfile.*' \) -print)
    set +f

    if [ -z "$DOCKERFILES" ]; then
        write_empty_sarif "$DOCKER_OUT" "hadolint"
        log "no Dockerfile found under $ABS_TARGET"
    else
        log "linting Dockerfiles"
        # shellcheck disable=SC2086
        hadolint --format sarif $DOCKERFILES > "$DOCKER_OUT" 2>/dev/null
        _rc=$?
        # hadolint exits 1 when it reports something. That is a finding, not a
        # failure; only a higher code means the tool itself broke.
        if [ "$_rc" -gt 1 ]; then
            log "hadolint exited $_rc"
            write_empty_sarif "$DOCKER_OUT" "hadolint"
            STATUS="$EXIT_SCAN_ERROR"
        fi
        [ -s "$DOCKER_OUT" ] || write_empty_sarif "$DOCKER_OUT" "hadolint"
    fi
else
    log "hadolint missing: Dockerfile check did NOT run"
    write_empty_sarif "$DOCKER_OUT" "hadolint-not-run"
fi

# --- CI workflows ---------------------------------------------------------

ACTIONS_OUT="$REPORT_DIR/actionlint.sarif"
if [ "$HAVE_ACTIONLINT" -eq 1 ]; then
    if [ -d "$ABS_TARGET/.github/workflows" ]; then
        log "linting GitHub Actions workflows"
        # actionlint has no SARIF writer, so its JSON is converted below.
        actionlint -format '{{json .}}' "$ABS_TARGET/.github/workflows" \
            > "$REPORT_DIR/actionlint.json" 2>/dev/null
        _rc=$?
        if [ "$_rc" -gt 1 ]; then
            log "actionlint exited $_rc"
            write_empty_sarif "$ACTIONS_OUT" "actionlint"
            STATUS="$EXIT_SCAN_ERROR"
        else
            python3 "$LAB_ROOT/scanners/actionlint_to_sarif.py" \
                "$REPORT_DIR/actionlint.json" "$ACTIONS_OUT" || {
                log "conversion of actionlint output failed"
                write_empty_sarif "$ACTIONS_OUT" "actionlint"
                STATUS="$EXIT_SCAN_ERROR"
            }
        fi
    else
        write_empty_sarif "$ACTIONS_OUT" "actionlint"
        log "no .github/workflows under $ABS_TARGET"
    fi
else
    log "actionlint missing: CI workflow check did NOT run"
    write_empty_sarif "$ACTIONS_OUT" "actionlint-not-run"
fi

log "reports: $DOCKER_OUT, $ACTIONS_OUT"
exit "$STATUS"
