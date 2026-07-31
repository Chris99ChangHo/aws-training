#!/usr/bin/env python3
"""Convert actionlint JSON output into SARIF 2.1.0.

actionlint has no SARIF writer, so the wrapper asks for JSON and converts here.
The conversion exists so the gate stays format-agnostic: every scanner in this
family speaks SARIF, and adding a tool must not mean teaching the gate a new
shape.

Usage:
    actionlint_to_sarif.py <actionlint.json> <out.sarif>

Exit codes: 0 converted (including an empty input), 1 the input was unreadable
or not the shape actionlint produces. A conversion that quietly emits an empty
report would be indistinguishable from a clean workflow.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

SARIF_SCHEMA = "https://json.schemastore.org/sarif-2.1.0.json"

# actionlint reports one flat severity. SARIF wants a level, and the gate maps
# levels onto severities, so anchor everything at "warning" rather than
# inventing a severity the tool never claimed.
DEFAULT_LEVEL = "warning"


def to_result(item: dict[str, Any]) -> dict[str, Any]:
    """Convert one actionlint finding into a SARIF result."""
    message = item.get("message") or "actionlint reported an issue"
    kind = item.get("kind") or "actionlint"
    path = item.get("filepath") or "unknown"
    line = item.get("line")
    column = item.get("column")

    region: dict[str, Any] = {}
    if isinstance(line, int) and line > 0:
        region["startLine"] = line
    if isinstance(column, int) and column > 0:
        region["startColumn"] = column

    location: dict[str, Any] = {
        "physicalLocation": {"artifactLocation": {"uri": path}}
    }
    if region:
        location["physicalLocation"]["region"] = region

    return {
        "ruleId": f"actionlint/{kind}",
        "level": DEFAULT_LEVEL,
        "message": {"text": message},
        "locations": [location],
    }


def main() -> int:
    """Read actionlint JSON, write SARIF, return an exit code."""
    if len(sys.argv) != 3:
        print(__doc__, file=sys.stderr)
        return 1

    src = Path(sys.argv[1])
    dst = Path(sys.argv[2])

    try:
        raw = src.read_text(encoding="utf-8").strip()
    except OSError as exc:
        print(f"error: cannot read {src}: {exc}", file=sys.stderr)
        return 1

    if not raw:
        items: list[Any] = []
    else:
        try:
            items = json.loads(raw)
        except json.JSONDecodeError as exc:
            print(f"error: {src} is not JSON: {exc}", file=sys.stderr)
            return 1

    if not isinstance(items, list):
        print(
            f"error: expected a JSON array from actionlint, got "
            f"{type(items).__name__}",
            file=sys.stderr,
        )
        return 1

    results = [to_result(i) for i in items if isinstance(i, dict)]
    rule_ids = sorted({r["ruleId"] for r in results})

    report = {
        "$schema": SARIF_SCHEMA,
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "actionlint",
                        "rules": [{"id": rid} for rid in rule_ids],
                    }
                },
                "results": results,
                "invocations": [{"executionSuccessful": True}],
            }
        ],
    }

    try:
        dst.write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )
    except OSError as exc:
        print(f"error: cannot write {dst}: {exc}", file=sys.stderr)
        return 1

    print(f"converted {len(results)} actionlint finding(s) -> {dst}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
