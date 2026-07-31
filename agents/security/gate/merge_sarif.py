#!/usr/bin/env python3
"""Merge several SARIF files into one.

SARIF 2.1.0 models a report as a list of `runs`, one per tool invocation, so
merging is a concatenation rather than a reconciliation: each scanner keeps its
own driver metadata and rule definitions, and nothing has to be translated.
That is the property that makes SARIF worth using here — the pipeline gains a
scanner by appending a run, not by teaching the gate a new output format.

Usage:
    merge_sarif.py [-o OUTPUT] [INPUT ...]

With no INPUT arguments, every *.sarif file in the report directory except the
merged output itself is used.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

# Resolve paths from this file, not the caller's cwd: the wrappers, the MCP
# server and CI all invoke this from different working directories.
# SEC_REPORT_DIR is honoured so this agrees with scanners/_lib.sh and gate.py
# about where reports live.
LAB_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REPORT_DIR = Path(os.environ.get("SEC_REPORT_DIR") or LAB_ROOT / "reports")
DEFAULT_OUTPUT = DEFAULT_REPORT_DIR / "merged.sarif"

SARIF_SCHEMA = "https://json.schemastore.org/sarif-2.1.0.json"
SARIF_VERSION = "2.1.0"

EXIT_OK = 0
EXIT_ERROR = 4


def load_runs(path: Path) -> list[dict[str, Any]]:
    """Return the `runs` array of one SARIF file.

    A malformed or unreadable input is an error rather than an empty result:
    silently contributing zero runs would let a crashed scanner look like a
    clean scan.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path.name} is not valid JSON: {exc}") from exc
    except OSError as exc:
        raise ValueError(f"{path.name} could not be read: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError(
            f"{path.name} top level is {type(data).__name__}, not an object"
        )

    runs = data.get("runs")
    if runs is None:
        raise ValueError(f"{path.name} has no 'runs' key; is it SARIF?")
    if not isinstance(runs, list):
        raise ValueError(f"{path.name} 'runs' is not an array")

    # Record where each run came from. Without this, a merged report cannot
    # answer "which scanner said this?" once the runs are side by side.
    for run in runs:
        if isinstance(run, dict):
            props = run.setdefault("properties", {})
            if isinstance(props, dict):
                props.setdefault("sourceFile", path.name)

    return runs


def discover_inputs(report_dir: Path, output: Path) -> list[Path]:
    """Return the SARIF files in `report_dir`, excluding the merge target."""
    if not report_dir.is_dir():
        return []
    return sorted(
        p for p in report_dir.glob("*.sarif") if p.resolve() != output.resolve()
    )


def merge(inputs: list[Path], output: Path) -> int:
    """Write a merged SARIF file. Return a process exit code."""
    if not inputs:
        print(
            f"error: no SARIF inputs found. Looked in {DEFAULT_REPORT_DIR}.\n"
            "Run the scanner wrappers first, or pass input paths explicitly.",
            file=sys.stderr,
        )
        return EXIT_ERROR

    all_runs: list[dict[str, Any]] = []
    for path in inputs:
        try:
            runs = load_runs(path)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return EXIT_ERROR
        all_runs.extend(runs)
        count = sum(
            len(r.get("results", []) or []) for r in runs if isinstance(r, dict)
        )
        print(f"  {path.name}: {len(runs)} run(s), {count} result(s)")

    merged = {
        "$schema": SARIF_SCHEMA,
        "version": SARIF_VERSION,
        "runs": all_runs,
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")

    total = sum(
        len(r.get("results", []) or []) for r in all_runs if isinstance(r, dict)
    )
    print(f"merged {len(all_runs)} run(s), {total} result(s) -> {output}")
    return EXIT_OK


def main() -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(
        description="Merge SARIF reports into a single file."
    )
    parser.add_argument(
        "inputs",
        nargs="*",
        type=Path,
        help="SARIF files to merge (default: all *.sarif in reports/)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"output path (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=DEFAULT_REPORT_DIR,
        help="directory to search when no inputs are given",
    )
    args = parser.parse_args()

    inputs = args.inputs or discover_inputs(args.report_dir, args.output)
    return merge(inputs, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
