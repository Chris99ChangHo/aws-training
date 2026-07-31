#!/bin/sh
# preflight.sh - report which scanners are present on this host.
#
# Usage: preflight.sh [--strict]
#          --strict  exit 3 if any required tool is missing (for CI)
#
# Runs at agent spawn so the operator sees the real capability of the machine
# before asking for a scan. A missing scanner that surfaces mid-conversation
# tends to get read as "nothing found".

set -u

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
LAB_ROOT=$(cd "$SCRIPT_DIR/.." && pwd)

STRICT=0
[ "${1:-}" = "--strict" ] && STRICT=1

MISSING_REQUIRED=0

row() {
    _name="$1"
    _role="$2"
    _required="$3"
    if command -v "$_name" >/dev/null 2>&1; then
        _ver=$("$_name" --version 2>/dev/null | head -1 | cut -c1-28)
        [ -z "$_ver" ] && _ver="present"
        printf '  %-10s %-22s %-9s %s\n' "$_name" "$_role" "OK" "$_ver"
    else
        printf '  %-10s %-22s %-9s %s\n' "$_name" "$_role" "MISSING" "-"
        [ "$_required" = "required" ] && MISSING_REQUIRED=$((MISSING_REQUIRED + 1))
    fi
}

echo "Generic Security Agent - preflight"
echo
printf '  %-10s %-22s %-9s %s\n' "tool" "role" "status" "version"
printf '  %-10s %-22s %-9s %s\n' "----" "----" "------" "-------"
row python3  "gate + MCP runtime"   required
row jq       "hook payload parsing" required
row semgrep  "SAST"                 optional
row trivy    "SCA / IaC / secrets"  optional
row nuclei   "DAST"                 optional
echo

if [ -f "$LAB_ROOT/.sec-scope" ]; then
    SCOPE_COUNT=$(sed -e 's/#.*//' -e 's/[[:space:]]//g' "$LAB_ROOT/.sec-scope" \
                  | grep -cv '^$')
    echo "  DAST scope : $SCOPE_COUNT authorised host(s) in .sec-scope"
else
    echo "  DAST scope : .sec-scope MISSING - active scanning will be refused"
fi

if [ -d "$LAB_ROOT/reports" ]; then
    REPORT_COUNT=$(find "$LAB_ROOT/reports" -name '*.sarif' 2>/dev/null | wc -l | tr -d ' ')
    echo "  reports    : $REPORT_COUNT SARIF file(s) in reports/"
else
    echo "  reports    : none yet"
fi

echo
echo "  A MISSING optional scanner is not a clean scan. Its wrapper exits 3,"
echo "  never 0, so the gate cannot read an absent tool as a pass."
echo "  Install instructions: docs/setup-sec-tools.md"

if [ "$STRICT" -eq 1 ] && [ "$MISSING_REQUIRED" -gt 0 ]; then
    echo
    echo "  strict mode: $MISSING_REQUIRED required tool(s) missing" >&2
    exit 3
fi

exit 0
