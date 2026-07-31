#!/usr/bin/env python3
"""Normalise a scanner's SARIF report so the gate can read it.

Some scanners write a report that contradicts their own exit code. Measured
with nuclei v3.11.0: it sets `invocations[].executionSuccessful` to `false`
even when the scan completed and produced findings.

That matters because `gate.py` refuses to emit a verdict on a report that says
its own run failed -- correct in general, since a crashed scanner must never be
read as a clean tree. But combined with nuclei's other habit (writing no file
at all when it finds nothing, which the wrapper compensates for with an empty
SARIF marked successful) it produces the worst possible pairing:

    no findings  -> empty SARIF, executionSuccessful=true  -> gate PASSES
    findings     -> nuclei's SARIF, executionSuccessful=false -> gate exits 4

A clean scan passes and a scan that found something reports a scanner error.
Anyone reading exit 4 as "tool problem, ignore" loses the findings.

Normalising belongs in the wrapper layer, which is what these scripts are for --
the same reason the wrappers normalise exit codes. Putting scanner-specific
knowledge in `gate.py` would make the deterministic judge depend on which tool
produced the file.

The flip is one-directional: `false` -> `true`, and the caller must only invoke
this after confirming the tool exited successfully. It never marks a successful
run as failed, and it never touches a report that already says `true`.

Usage:
    normalize_sarif.py <report.sarif>

Exit codes:
    0  the file was read; it may or may not have been changed
    1  the file could not be read or written
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def normalise(report: dict) -> int:
    """Flip executionSuccessful false -> true. Return how many were changed."""
    changed = 0
    for run in report.get("runs", []):
        if not isinstance(run, dict):
            continue
        for inv in run.get("invocations", []):
            if isinstance(inv, dict) and inv.get("executionSuccessful") is False:
                inv["executionSuccessful"] = True
                changed += 1
    return changed


def main() -> int:
    """Read, normalise, write. Return an exit code."""
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 1

    path = Path(sys.argv[1])
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        print(f"error: cannot read {path}: {exc}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as exc:
        # A malformed report is left exactly as it is. The gate rejects it, and
        # that is the right outcome -- rewriting a file we cannot parse would
        # destroy the evidence of why it is unusable.
        print(f"error: {path} is not valid JSON: {exc}", file=sys.stderr)
        return 1

    if not isinstance(report, dict):
        print(f"error: {path} is not a SARIF object", file=sys.stderr)
        return 1

    changed = normalise(report)
    if changed:
        try:
            path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        except OSError as exc:
            print(f"error: cannot write {path}: {exc}", file=sys.stderr)
            return 1
        print(
            f"normalised executionSuccessful=false -> true ({changed} invocation)",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
