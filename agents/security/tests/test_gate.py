#!/usr/bin/env python3
"""Tests for the SARIF merge step and the deterministic gate.

Uses only unittest from the standard library, matching the runtime's
zero-dependency constraint. Run from anywhere:

    python3 tests/test_gate.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

LAB_ROOT = Path(__file__).resolve().parent.parent
FIXTURES = LAB_ROOT / "tests" / "fixtures"
MERGE = LAB_ROOT / "gate" / "merge_sarif.py"
GATE = LAB_ROOT / "gate" / "gate.py"

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_ERROR = 4


def run(script: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Invoke one of the gate scripts and capture its output."""
    return subprocess.run(
        [sys.executable, str(script), *args],
        capture_output=True,
        text=True,
        check=False,
    )


class TestMerge(unittest.TestCase):
    """merge_sarif.py behaviour."""

    def test_merges_runs_from_two_scanners(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "merged.sarif"
            result = run(
                MERGE,
                str(FIXTURES / "semgrep.sarif"),
                str(FIXTURES / "trivy.sarif"),
                "-o",
                str(out),
            )
            self.assertEqual(result.returncode, 0, result.stderr)

            merged = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(merged["version"], "2.1.0")
            self.assertEqual(len(merged["runs"]), 2)

            drivers = [r["tool"]["driver"]["name"] for r in merged["runs"]]
            self.assertEqual(drivers, ["semgrep", "Trivy"])

            total = sum(len(r["results"]) for r in merged["runs"])
            self.assertEqual(total, 7)

    def test_records_source_file_per_run(self) -> None:
        """A merged report must still say which scanner produced each run."""
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "merged.sarif"
            run(
                MERGE,
                str(FIXTURES / "semgrep.sarif"),
                str(FIXTURES / "trivy.sarif"),
                "-o",
                str(out),
            )
            merged = json.loads(out.read_text(encoding="utf-8"))
            sources = [r["properties"]["sourceFile"] for r in merged["runs"]]
            self.assertEqual(sources, ["semgrep.sarif", "trivy.sarif"])

    def test_malformed_input_is_an_error_not_an_empty_merge(self) -> None:
        """A broken scanner output must not be silently treated as clean."""
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.sarif"
            bad.write_text("{not json", encoding="utf-8")
            out = Path(tmp) / "merged.sarif"
            result = run(MERGE, str(bad), "-o", str(out))
            self.assertEqual(result.returncode, EXIT_ERROR)
            self.assertFalse(out.exists())

    def test_non_sarif_json_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "notsarif.sarif"
            bad.write_text('{"hello": "world"}', encoding="utf-8")
            out = Path(tmp) / "merged.sarif"
            result = run(MERGE, str(bad), "-o", str(out))
            self.assertEqual(result.returncode, EXIT_ERROR)
            self.assertIn("runs", result.stderr)

    def test_no_inputs_is_an_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "merged.sarif"
            result = run(
                MERGE, "-o", str(out), "--report-dir", str(Path(tmp) / "empty")
            )
            self.assertEqual(result.returncode, EXIT_ERROR)


class TestSeverityResolution(unittest.TestCase):
    """gate.py must map each SARIF result to the documented bucket."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls.merged = Path(cls._tmp.name) / "merged.sarif"
        run(
            MERGE,
            str(FIXTURES / "semgrep.sarif"),
            str(FIXTURES / "trivy.sarif"),
            "-o",
            str(cls.merged),
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def _counts(self) -> dict[str, int]:
        result = run(
            GATE, "--report", str(self.merged), "--fail-on", "high", "--json"
        )
        return json.loads(result.stdout)["counts"]

    def test_numeric_security_severity_wins(self) -> None:
        # 9.5 and 10.0 are the only two results in the critical band.
        self.assertEqual(self._counts()["critical"], 2)

    def test_falls_back_to_rule_default_level(self) -> None:
        # semgrep's hardcoded-token rule has no security-severity but
        # defaultConfiguration.level=error -> high. Trivy's CVE-2023-45853
        # scores 7.5 -> high. Two in total.
        self.assertEqual(self._counts()["high"], 2)

    def test_falls_back_to_result_level(self) -> None:
        # 6.1 -> medium, plus no-severity-metadata (level=warning) -> medium.
        self.assertEqual(self._counts()["medium"], 2)

    def test_low_band(self) -> None:
        # AVD-AWS-0088 scores 3.4 -> low.
        self.assertEqual(self._counts()["low"], 1)

    def test_every_result_is_classified(self) -> None:
        counts = self._counts()
        self.assertEqual(sum(counts.values()), 7)

    def test_locations_are_reported(self) -> None:
        result = run(
            GATE, "--report", str(self.merged), "--fail-on", "high", "--json"
        )
        findings = json.loads(result.stdout)["findings"]
        locations = {f["location"] for f in findings}
        self.assertIn("app/tasks.py:42", locations)
        self.assertIn("pom.xml:31", locations)


class TestGateVerdict(unittest.TestCase):
    """The pass/fail decision must be a pure function of the report."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls.merged = Path(cls._tmp.name) / "merged.sarif"
        run(
            MERGE,
            str(FIXTURES / "semgrep.sarif"),
            str(FIXTURES / "trivy.sarif"),
            "-o",
            str(cls.merged),
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def test_high_threshold_zero_budget_fails(self) -> None:
        result = run(
            GATE,
            "--report",
            str(self.merged),
            "--fail-on",
            "high",
            "--max-allowed",
            "0",
        )
        self.assertEqual(result.returncode, EXIT_FAIL)
        self.assertIn("FAIL", result.stdout)

    def test_critical_threshold_generous_budget_passes(self) -> None:
        result = run(
            GATE,
            "--report",
            str(self.merged),
            "--fail-on",
            "critical",
            "--max-allowed",
            "5",
        )
        self.assertEqual(result.returncode, EXIT_PASS)
        self.assertIn("PASS", result.stdout)

    def test_budget_boundary_is_inclusive(self) -> None:
        """Exactly at budget passes; one over fails."""
        at_budget = run(
            GATE, "--report", str(self.merged), "--fail-on", "critical",
            "--max-allowed", "2",
        )
        over_budget = run(
            GATE, "--report", str(self.merged), "--fail-on", "critical",
            "--max-allowed", "1",
        )
        self.assertEqual(at_budget.returncode, EXIT_PASS)
        self.assertEqual(over_budget.returncode, EXIT_FAIL)

    def test_blocking_count_matches_threshold(self) -> None:
        result = run(
            GATE, "--report", str(self.merged), "--fail-on", "medium", "--json"
        )
        payload = json.loads(result.stdout)
        # critical 2 + high 2 + medium 2
        self.assertEqual(payload["blockingCount"], 6)

    def test_clean_report_passes_at_strictest_threshold(self) -> None:
        result = run(
            GATE,
            "--report",
            str(FIXTURES / "clean.sarif"),
            "--fail-on",
            "info",
            "--max-allowed",
            "0",
        )
        self.assertEqual(result.returncode, EXIT_PASS)

    def test_verdict_is_reproducible(self) -> None:
        """Same input, same verdict - the property an LLM gate cannot offer."""
        outputs = {
            run(
                GATE, "--report", str(self.merged), "--fail-on", "high", "--json"
            ).stdout
            for _ in range(3)
        }
        self.assertEqual(len(outputs), 1)

    def test_missing_report_is_error_not_pass(self) -> None:
        result = run(GATE, "--report", "/nonexistent/merged.sarif")
        self.assertEqual(result.returncode, EXIT_ERROR)

    def test_malformed_report_is_error_not_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "merged.sarif"
            bad.write_text("truncated{", encoding="utf-8")
            result = run(GATE, "--report", str(bad))
            self.assertEqual(result.returncode, EXIT_ERROR)


class TestReportIntegrity(unittest.TestCase):
    """A report that does not prove a scan ran must not produce a pass.

    Every case here was found by an independent audit of the first
    implementation, which passed all of them. A crashed or absent scanner
    leaves exactly these shapes behind, and reading them as "nothing found"
    turns a broken pipeline into a green one.
    """

    def _gate(self, payload: str) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "merged.sarif"
            report.write_text(payload, encoding="utf-8")
            return run(GATE, "--report", str(report), "--fail-on", "high")

    def test_empty_runs_is_error(self) -> None:
        result = self._gate('{"version":"2.1.0","runs":[]}')
        self.assertEqual(result.returncode, EXIT_ERROR)

    def test_missing_runs_is_error(self) -> None:
        result = self._gate('{"version":"2.1.0","results":[]}')
        self.assertEqual(result.returncode, EXIT_ERROR)

    def test_runs_not_a_list_is_error(self) -> None:
        result = self._gate('{"version":"2.1.0","runs":"hacked"}')
        self.assertEqual(result.returncode, EXIT_ERROR)

    def test_run_not_an_object_is_error(self) -> None:
        result = self._gate('{"version":"2.1.0","runs":["nope"]}')
        self.assertEqual(result.returncode, EXIT_ERROR)

    def test_null_results_is_error(self) -> None:
        payload = json.dumps(
            {
                "version": "2.1.0",
                "runs": [
                    {"tool": {"driver": {"name": "t"}}, "results": None}
                ],
            }
        )
        self.assertEqual(self._gate(payload).returncode, EXIT_ERROR)

    def test_failed_invocation_is_error(self) -> None:
        """A scanner that reported its own failure cannot yield a pass."""
        payload = json.dumps(
            {
                "version": "2.1.0",
                "runs": [
                    {
                        "tool": {"driver": {"name": "semgrep"}},
                        "results": [],
                        "invocations": [{"executionSuccessful": False}],
                    }
                ],
            }
        )
        self.assertEqual(self._gate(payload).returncode, EXIT_ERROR)

    def test_successful_empty_run_still_passes(self) -> None:
        """A genuinely clean scan must not be caught by the checks above."""
        result = run(
            GATE,
            "--report",
            str(FIXTURES / "clean.sarif"),
            "--fail-on",
            "info",
            "--max-allowed",
            "0",
        )
        self.assertEqual(result.returncode, EXIT_PASS)


class TestSeverityEdgeCases(unittest.TestCase):
    """Severity resolution must not be defeated by odd but legal JSON."""

    def _severity(
        self, result_obj: dict[str, Any], rules: list[Any] | None = None
    ) -> str:
        payload = json.dumps(
            {
                "version": "2.1.0",
                "runs": [
                    {
                        "tool": {"driver": {"name": "t", "rules": rules or []}},
                        "results": [result_obj],
                        "invocations": [{"executionSuccessful": True}],
                    }
                ],
            }
        )
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "r.sarif"
            report.write_text(payload, encoding="utf-8")
            out = run(GATE, "--report", str(report), "--fail-on", "high", "--json")
            return json.loads(out.stdout)["findings"][0]["severity"]

    def test_uppercase_level_is_normalised(self) -> None:
        """Some tools emit "Error" or "WARNING"; SARIF's enum is lowercase."""
        self.assertEqual(
            self._severity({"ruleId": "X", "level": "Error", "locations": []}),
            "high",
        )

    def test_mixed_case_level_is_normalised(self) -> None:
        self.assertEqual(
            self._severity({"ruleId": "X", "level": "WARNING", "locations": []}),
            "medium",
        )

    def test_nan_score_falls_back_to_level(self) -> None:
        """float("NaN") does not raise, and every comparison against it is
        False, so an unguarded numeric path silently reports "info"."""
        self.assertEqual(
            self._severity(
                {
                    "ruleId": "X",
                    "level": "error",
                    "properties": {"security-severity": "NaN"},
                    "locations": [],
                }
            ),
            "high",
        )

    def test_negative_score_falls_back_to_level(self) -> None:
        self.assertEqual(
            self._severity(
                {
                    "ruleId": "X",
                    "level": "error",
                    "properties": {"security-severity": "-1"},
                    "locations": [],
                }
            ),
            "high",
        )

    def test_infinite_score_falls_back_to_level(self) -> None:
        self.assertEqual(
            self._severity(
                {
                    "ruleId": "X",
                    "level": "warning",
                    "properties": {"security-severity": "Infinity"},
                    "locations": [],
                }
            ),
            "medium",
        )

    def test_score_above_ten_is_treated_as_critical(self) -> None:
        """Out-of-range but positive: clamp upward rather than discard."""
        self.assertEqual(
            self._severity(
                {
                    "ruleId": "X",
                    "level": "note",
                    "properties": {"security-severity": "99"},
                    "locations": [],
                }
            ),
            "critical",
        )

    def test_unknown_level_string_defaults_to_medium(self) -> None:
        self.assertEqual(
            self._severity({"ruleId": "X", "level": "spicy", "locations": []}),
            "medium",
        )


class TestManifestDefaults(unittest.TestCase):
    """The gate's defaults must come from the neutral manifest."""

    def test_defaults_match_manifest(self) -> None:
        import tomllib

        manifest = tomllib.loads(
            (LAB_ROOT / "agent" / "manifest.toml").read_text(encoding="utf-8")
        )
        result = run(GATE, "--report", str(FIXTURES / "clean.sarif"))
        self.assertIn(
            f"threshold   : {manifest['gate']['fail_on_severity']} or above",
            result.stdout,
        )
        self.assertIn(
            f"budget      : {manifest['gate']['max_allowed']}", result.stdout
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
