#!/bin/sh
# preflight.sh - report which linters are available.
#
# Runs at session start. Reports and exits 0 even when tools are missing: the
# session is still useful for reading code and reviewing pipelines, and failing
# here would block work that does not need a linter. Wrappers exit 3 at the
# point a missing tool actually matters.

set -u

WRAPPER_NAME=preflight
LAB_ROOT=$(cd "$(dirname "$0")/.." && pwd)
# shellcheck source=_lib.sh
. "$LAB_ROOT/scanners/_lib.sh"

CORE_ROOT=$(cd "$LAB_ROOT/../core" && pwd)

if [ -x "$LAB_ROOT/.venv/bin/python3" ]; then
    PY="$LAB_ROOT/.venv/bin/python3"
else
    PY=python3
fi

report() {
    if command -v "$1" >/dev/null 2>&1; then
        printf '  %-12s present  (%s)\n' "$1" "$2"
    else
        printf '  %-12s MISSING  (%s)\n' "$1" "$2"
    fi
}

printf 'generic-devops-agent preflight\n'
printf '\nbuilt-in checks (no external tool):\n'
printf '  %-12s present  (%s)\n' "operability" "OPS-* rules: state locking, pinning, probes, rollback"
if "$PY" -c 'import yaml' 2>/dev/null; then
    printf '  %-12s present  (%s)\n' "PyYAML" "needed for Kubernetes and GitHub Actions checks"
else
    printf '  %-12s MISSING  (%s)\n' "PyYAML" "K8s/Actions checks will report as not run; see requirements.txt"
fi

printf '\nexternal linters:\n'
report hadolint   "Dockerfile"
report actionlint "GitHub Actions workflows"

printf '\ngate (shared, agents/core):\n'
if [ -f "$CORE_ROOT/gate/gate.py" ]; then
    printf '  %-12s present  (%s)\n' "gate.py" "deterministic SARIF gate, no LLM"
else
    printf '  %-12s MISSING  (%s)\n' "gate.py" "expected at $CORE_ROOT/gate"
fi

printf '\nreports:\n'
printf '  %s\n' "$REPORT_DIR"

printf '\nstate-changing commands are blocked by scanners/guard_infra.sh.\n'
printf 'plan and inspect only. see README.md.\n'

exit "$EXIT_OK"
