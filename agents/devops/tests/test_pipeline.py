#!/usr/bin/env python3
"""Tests for the pipeline wrapper contract and the actionlint SARIF converter.

Runs on a host where hadolint and actionlint are absent, which is the point:
the case that must never regress is "no linter ran" reporting exit 3 rather
than a clean result.

Usage: python3 tests/test_pipeline.py
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parent.parent
CONVERTER = LAB_ROOT / "scanners" / "actionlint_to_sarif.py"
WRAPPER = LAB_ROOT / "scanners" / "run_pipeline.sh"

EXIT_OK = 0
EXIT_TOOL_MISSING = 3
EXIT_SCAN_ERROR = 4


def convert(payload: str) -> subprocess.CompletedProcess[str]:
    """Run the converter over a literal payload and return the process."""
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "actionlint.json"
        dst = Path(tmp) / "out.sarif"
        src.write_text(payload, encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(CONVERTER), str(src), str(dst)],
            capture_output=True,
            text=True,
            check=False,
        )
        # Attach the output document so assertions can read it after cleanup.
        proc.sarif = (  # type: ignore[attr-defined]
            json.loads(dst.read_text(encoding="utf-8")) if dst.exists() else None
        )
        return proc


class TestConverter(unittest.TestCase):
    """actionlint JSON -> SARIF 2.1.0."""

    def test_finding_becomes_sarif_result(self) -> None:
        payload = json.dumps(
            [
                {
                    "message": "shellcheck reported issue",
                    "kind": "shellcheck",
                    "filepath": ".github/workflows/ci.yml",
                    "line": 12,
                    "column": 9,
                }
            ]
        )
        proc = convert(payload)
        self.assertEqual(proc.returncode, EXIT_OK)
        run = proc.sarif["runs"][0]  # type: ignore[index]
        self.assertEqual(run["tool"]["driver"]["name"], "actionlint")
        result = run["results"][0]
        self.assertEqual(result["ruleId"], "actionlint/shellcheck")
        region = result["locations"][0]["physicalLocation"]["region"]
        self.assertEqual(region["startLine"], 12)
        self.assertEqual(region["startColumn"], 9)

    def test_rules_are_declared_for_every_result(self) -> None:
        """A SARIF consumer resolves severity through the rule table."""
        payload = json.dumps(
            [
                {"message": "a", "kind": "syntax-check", "filepath": "w.yml"},
                {"message": "b", "kind": "expression", "filepath": "w.yml"},
                {"message": "c", "kind": "expression", "filepath": "w.yml"},
            ]
        )
        proc = convert(payload)
        run = proc.sarif["runs"][0]  # type: ignore[index]
        declared = {r["id"] for r in run["tool"]["driver"]["rules"]}
        used = {r["ruleId"] for r in run["results"]}
        self.assertEqual(declared, used)
        self.assertEqual(len(run["results"]), 3)

    def test_empty_input_is_a_valid_empty_report(self) -> None:
        """No findings must still produce a document the gate can read."""
        proc = convert("")
        self.assertEqual(proc.returncode, EXIT_OK)
        run = proc.sarif["runs"][0]  # type: ignore[index]
        self.assertEqual(run["results"], [])
        self.assertTrue(run["invocations"][0]["executionSuccessful"])

    def test_malformed_input_fails_loudly(self) -> None:
        """A silent empty report would look identical to a clean workflow."""
        proc = convert("not json")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("not JSON", proc.stderr)

    def test_non_array_input_fails_loudly(self) -> None:
        proc = convert('{"message": "single object, not a list"}')
        self.assertEqual(proc.returncode, 1)
        self.assertIn("expected a JSON array", proc.stderr)

    def test_missing_position_is_omitted_not_faked(self) -> None:
        """A finding without a line must not claim line 0."""
        payload = json.dumps([{"message": "m", "kind": "k", "filepath": "w.yml"}])
        proc = convert(payload)
        loc = proc.sarif["runs"][0]["results"][0]["locations"][0]  # type: ignore[index]
        self.assertNotIn("region", loc["physicalLocation"])


class TestWrapperContract(unittest.TestCase):
    """run_pipeline.sh exit codes."""

    def test_absent_linters_report_tool_missing(self) -> None:
        """Exit 3, never 0. An absent linter is not an absence of problems."""
        if shutil.which("hadolint") or shutil.which("actionlint"):
            self.skipTest("a pipeline linter is installed on this host")
        proc = subprocess.run(
            ["sh", str(WRAPPER), str(LAB_ROOT)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, EXIT_TOOL_MISSING)
        self.assertIn("not a clean result", proc.stderr)

    def test_missing_target_is_a_scan_error(self) -> None:
        proc = subprocess.run(
            ["sh", str(WRAPPER), str(LAB_ROOT / "does-not-exist")],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, EXIT_SCAN_ERROR)
        self.assertIn("target does not exist", proc.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
