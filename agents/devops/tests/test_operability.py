#!/usr/bin/env python3
"""Tests for the operability checker.

Two properties matter beyond "does it find things":

1. **It must not fire when the control is present.** A checker that reports
   every file is noise, and a reviewer cannot tell noise from a finding.
2. **It must not overlap the security agent.** The earlier `run_iac.sh` shelled
   out to `trivy config` and produced byte-identical findings to the security
   agent's SCA wrapper. The last test in this file asserts the rule namespaces
   stay disjoint.

Usage: python3 tests/test_operability.py
       (or .venv/bin/python3, which additionally exercises the YAML checks)
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parent.parent
CHECKER = LAB_ROOT / "scanners" / "operability_check.py"
VENV_PY = LAB_ROOT / ".venv" / "bin" / "python3"

EXIT_OK = 0
EXIT_TOOL_MISSING = 3
EXIT_ERROR = 4

try:
    import yaml as _yaml  # noqa: F401

    HAVE_YAML = True
except ImportError:
    HAVE_YAML = False


def scan(files: dict[str, str], python: str | None = None) -> tuple[int, dict]:
    """Write files to a temp dir, run the checker, return (exit code, report)."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for rel, body in files.items():
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding="utf-8")
        out = root / "report.sarif"
        proc = subprocess.run(
            [python or sys.executable, str(CHECKER), str(root), str(out)],
            capture_output=True,
            text=True,
            check=False,
        )
        report = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
        return proc.returncode, report


def rule_ids(report: dict) -> list[str]:
    """Return the rule IDs of every result, in order."""
    return [r["ruleId"] for r in report["runs"][0]["results"]]


TF_BAD = """
terraform {
  required_providers {
    aws = {
      source = "hashicorp/aws"
    }
  }
}
"""

TF_GOOD = """
terraform {
  required_version = ">= 1.6.0"

  backend "s3" {
    bucket = "tfstate"
    key    = "prod/terraform.tfstate"
    region = "ap-northeast-2"
  }

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}
"""

K8S_BAD = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web
spec:
  replicas: 1
  template:
    spec:
      containers:
        - name: web
          image: web:1.2.3
"""

K8S_GOOD = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
  template:
    spec:
      containers:
        - name: web
          image: web:1.2.3
          readinessProbe:
            httpGet:
              path: /healthz
              port: 8080
"""

CRONJOB = """
apiVersion: batch/v1
kind: CronJob
metadata:
  name: nightly
spec:
  schedule: "0 3 * * *"
  jobTemplate:
    spec:
      template:
        spec:
          containers:
            - name: job
              image: job:1.0.0
              readinessProbe:
                exec:
                  command: ["true"]
"""

WF_BAD = """
name: ci
on: [push]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
"""

WF_GOOD = """
name: ci
on: [push]
jobs:
  build:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683
      - uses: ./local-action
      - run: make test
"""


class TestTerraform(unittest.TestCase):
    """OPS-0001 / 0002 / 0003. No YAML parser needed."""

    def test_missing_controls_are_reported(self) -> None:
        code, report = scan({"main.tf": TF_BAD})
        self.assertEqual(code, EXIT_OK)
        ids = rule_ids(report)
        self.assertIn("OPS-0001", ids)  # no required_version
        self.assertIn("OPS-0003", ids)  # no backend
        self.assertIn("OPS-0002", ids)  # provider without version

    def test_present_controls_are_not_reported(self) -> None:
        """The complement. A checker that always fires is not a checker."""
        code, report = scan({"main.tf": TF_GOOD})
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(rule_ids(report), [])

    def test_provider_with_version_is_not_flagged(self) -> None:
        """Only the provider missing a constraint is named."""
        extra = (
            'version = "~> 5.0"\n    }\n'
            '    random = {\n      source = "hashicorp/random"\n    }'
        )
        mixed = TF_GOOD.replace('version = "~> 5.0"\n    }', extra)
        code, report = scan({"main.tf": mixed})
        self.assertEqual(code, EXIT_OK)
        results = report["runs"][0]["results"]
        ops2 = [r for r in results if r["ruleId"] == "OPS-0002"]
        self.assertEqual(len(ops2), 1)
        self.assertIn("random", ops2[0]["message"]["text"])

    def test_no_terraform_block_means_no_terraform_findings(self) -> None:
        """A .tf file with only resources declares no version policy to check."""
        code, report = scan({"main.tf": 'resource "aws_s3_bucket" "b" {}\n'})
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(rule_ids(report), [])

    def test_cloud_block_counts_as_a_remote_backend(self) -> None:
        body = (
            'terraform {\n  required_version = ">= 1.6"\n'
            '  cloud {\n    organization = "o"\n  }\n}\n'
        )
        code, report = scan({"main.tf": body})
        self.assertNotIn("OPS-0003", rule_ids(report))


@unittest.skipUnless(HAVE_YAML, "PyYAML not installed in this interpreter")
class TestKubernetes(unittest.TestCase):
    """OPS-0010 / 0011 / 0012."""

    def test_missing_controls_are_reported(self) -> None:
        code, report = scan({"deploy.yaml": K8S_BAD})
        self.assertEqual(code, EXIT_OK)
        ids = rule_ids(report)
        self.assertIn("OPS-0010", ids)  # no probe
        self.assertIn("OPS-0011", ids)  # single replica
        self.assertIn("OPS-0012", ids)  # no strategy

    def test_present_controls_are_not_reported(self) -> None:
        code, report = scan({"deploy.yaml": K8S_GOOD})
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(rule_ids(report), [])

    def test_cronjob_is_exempt_from_replicas_and_strategy(self) -> None:
        """Run-to-completion workloads have neither, so flagging them is wrong."""
        code, report = scan({"cron.yaml": CRONJOB})
        ids = rule_ids(report)
        self.assertNotIn("OPS-0011", ids)
        self.assertNotIn("OPS-0012", ids)
        self.assertNotIn("OPS-0010", ids)

    def test_non_workload_yaml_is_ignored(self) -> None:
        cm = "apiVersion: v1\nkind: ConfigMap\ndata:\n  a: b\n"
        code, report = scan({"cm.yaml": cm})
        self.assertEqual(rule_ids(report), [])


@unittest.skipUnless(HAVE_YAML, "PyYAML not installed in this interpreter")
class TestWorkflows(unittest.TestCase):
    """OPS-0020 / 0021."""

    def test_missing_controls_are_reported(self) -> None:
        code, report = scan({".github/workflows/ci.yml": WF_BAD})
        ids = rule_ids(report)
        self.assertIn("OPS-0020", ids)  # no timeout-minutes
        self.assertIn("OPS-0021", ids)  # tag instead of SHA

    def test_pinned_and_local_actions_are_not_flagged(self) -> None:
        code, report = scan({".github/workflows/ci.yml": WF_GOOD})
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(rule_ids(report), [])


class TestParserContract(unittest.TestCase):
    """Unchecked must never be reported as clean."""

    def test_yaml_without_a_parser_reports_tool_missing(self) -> None:
        """Exit 3, not 0, when YAML files were present but could not be read."""
        if HAVE_YAML:
            self.skipTest("this interpreter has PyYAML; run with system python3")
        code, report = scan({"deploy.yaml": K8S_BAD})
        self.assertEqual(code, EXIT_TOOL_MISSING)
        self.assertEqual(rule_ids(report), [])

    def test_terraform_still_checked_without_a_yaml_parser(self) -> None:
        """A missing YAML parser must not disable the checks that can run."""
        if HAVE_YAML:
            self.skipTest("this interpreter has PyYAML; run with system python3")
        code, report = scan({"main.tf": TF_BAD})
        self.assertEqual(code, EXIT_OK)
        self.assertIn("OPS-0001", rule_ids(report))

    def test_missing_target_is_an_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proc = subprocess.run(
                [
                    sys.executable,
                    str(CHECKER),
                    str(Path(tmp) / "nope"),
                    str(Path(tmp) / "o.sarif"),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(proc.returncode, EXIT_ERROR)


class TestReportShape(unittest.TestCase):
    """The gate reads this document; it has to be well formed."""

    def test_every_rule_is_declared_even_when_nothing_fires(self) -> None:
        """A reader must see what was looked for, not only what was found."""
        code, report = scan({"main.tf": TF_GOOD})
        driver = report["runs"][0]["tool"]["driver"]
        self.assertEqual(driver["name"], "operability-check")
        self.assertEqual(len(driver["rules"]), 8)
        for rule in driver["rules"]:
            self.assertIn(
                rule["defaultConfiguration"]["level"],
                {"error", "warning", "note"},
            )

    def test_results_reference_declared_rules_only(self) -> None:
        code, report = scan({"main.tf": TF_BAD})
        driver = report["runs"][0]["tool"]["driver"]
        declared = {r["id"] for r in driver["rules"]}
        self.assertTrue(set(rule_ids(report)) <= declared)

    def test_levels_are_standard_sarif_not_invented_properties(self) -> None:
        """The gate maps error/warning/note onto high/medium/low.

        Using a `security-severity` property for findings that are not security
        findings would misrepresent them.
        """
        code, report = scan({"main.tf": TF_BAD})
        for result in report["runs"][0]["results"]:
            self.assertIn(result["level"], {"error", "warning", "note"})
            self.assertNotIn("properties", result)


class TestNoOverlapWithSecurityAgent(unittest.TestCase):
    """The boundary that this checker exists to restore."""

    def test_rule_namespace_is_disjoint_from_the_security_scanners(self) -> None:
        """OPS-* must not collide with Trivy's AWS-* / KSV-* / DS-* or Semgrep's.

        Measured cause of this test: the previous run_iac.sh emitted the exact
        13 rule IDs the security agent's SCA already emitted.
        """
        code, report = scan({"main.tf": TF_BAD})
        foreign_prefixes = ("AWS-", "KSV-", "DS-", "AVD-", "CVE-")
        for rid in rule_ids(report):
            self.assertTrue(rid.startswith("OPS-"), f"unexpected namespace: {rid}")
            for prefix in foreign_prefixes:
                self.assertFalse(rid.startswith(prefix))

    def test_no_vulnerability_or_secret_rules_are_declared(self) -> None:
        """This agent does not answer "is it vulnerable"."""
        code, report = scan({"main.tf": TF_GOOD})
        text = json.dumps(report["runs"][0]["tool"]["driver"]["rules"]).lower()
        for word in ("vulnerab", "secret", "cve", "injection", "encrypt"):
            self.assertNotIn(word, text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
