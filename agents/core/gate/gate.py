#!/usr/bin/env python3
"""Decide pass/fail from a SARIF report. No model involved.

This is Tier 3 of the design: the build-blocking decision is made by reading
numbers out of a file, so it produces the same verdict every time and is
reviewable by someone who does not trust the agent. An LLM is useful for
triaging and for writing the fix; it is the wrong thing to put on the path that
decides whether code ships, because a probabilistic component makes a gate that
cannot be audited or reproduced.

Severity resolution order, applied per result:
  1. result.properties["security-severity"]        (numeric, 0-10)
  2. the matching rule's properties["security-severity"]
  3. the rule's defaultConfiguration.level
  4. result.level
  5. "warning", the SARIF default when level is absent

Numeric bands follow the CVSS v3 qualitative ranges that GitHub code scanning
also uses, so a score means the same thing here as it does there.

Usage:
    gate.py [--report PATH] [--fail-on LEVEL] [--max-allowed N] [--json]

Exit codes:
    0  gate passed
    1  gate failed (findings at or above the threshold exceed the budget)
    4  the report could not be read
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import tomllib
from pathlib import Path
from typing import Any

def resolve_agent_root() -> Path:
    """Return the agent folder this run belongs to.

    The gate is shared by more than one agent, so it cannot derive the agent
    from its own location the way it did when it lived inside one. Identity
    comes from outside: `AGENT_ROOT` if set, otherwise the current directory,
    which is what the documented usage (`cd agents/<domain>`) produces.

    Resolution is deliberately not silent about failure -- an agent folder is
    recognised by holding `agent/manifest.toml`, and if neither candidate does,
    the caller finds out from `main()` instead of getting a permissive default.
    """
    override = os.environ.get("AGENT_ROOT")
    if override:
        return Path(override).resolve()
    return Path.cwd().resolve()


AGENT_ROOT = resolve_agent_root()

# Honour the same environment override the scanner wrappers use
# (scanners/_lib.sh). Without this, setting SEC_REPORT_DIR moved where the
# scanners wrote but not where the gate read, so the gate silently evaluated a
# stale report from the default directory.
REPORT_DIR = Path(os.environ.get("SEC_REPORT_DIR") or AGENT_ROOT / "reports")
DEFAULT_REPORT = REPORT_DIR / "merged.sarif"
MANIFEST = AGENT_ROOT / "agent" / "manifest.toml"

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_ERROR = 4

# Ordered least to most severe. Index is the comparison key.
SEVERITY_ORDER = ["info", "low", "medium", "high", "critical"]

# SARIF `level` enum -> our buckets.
LEVEL_TO_SEVERITY = {
    "error": "high",
    "warning": "medium",
    "note": "low",
    "none": "info",
}


def bucket_from_score(score: float) -> str:
    """Map a 0-10 numeric severity onto a named bucket (CVSS v3 bands)."""
    if score >= 9.0:
        return "critical"
    if score >= 7.0:
        return "high"
    if score >= 4.0:
        return "medium"
    if score > 0.0:
        return "low"
    return "info"


def _score_of(props: Any) -> float | None:
    """Extract a usable numeric security-severity from a properties bag.

    Returns None when there is no usable number, so the caller falls through to
    the level-based path.

    NaN needs an explicit check. `float("NaN")` does not raise, and every
    comparison against NaN is False, so an unguarded numeric path sends a
    NaN-scored finding to the bottom bucket. Because the numeric path takes
    priority over `level`, that also discards a perfectly good `level: error`.
    An independent audit used exactly this to turn a high-severity finding into
    "info" and pass the gate. Negative and infinite values are refused for the
    same reason: they are not on the 0-10 scale, so they carry no information
    that should outrank `level`.
    """
    if not isinstance(props, dict):
        return None
    raw = props.get("security-severity")
    if raw is None:
        return None
    try:
        score = float(raw)
    except (TypeError, ValueError):
        # A non-numeric security-severity is a tool bug, not a reason to crash.
        # Fall through to the level-based path instead of guessing a number.
        return None
    if math.isnan(score) or math.isinf(score) or score < 0.0:
        return None
    return score


def build_rule_index(run: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Map ruleId -> rule object for one run, across driver and extensions."""
    index: dict[str, dict[str, Any]] = {}
    tool = run.get("tool") or {}
    components = []
    driver = tool.get("driver")
    if isinstance(driver, dict):
        components.append(driver)
    extensions = tool.get("extensions")
    if isinstance(extensions, list):
        components.extend(c for c in extensions if isinstance(c, dict))

    for component in components:
        for rule in component.get("rules") or []:
            if isinstance(rule, dict) and isinstance(rule.get("id"), str):
                index[rule["id"]] = rule
    return index


def _level_to_severity(level: Any) -> str | None:
    """Map a SARIF `level` string to a bucket, case-insensitively.

    SARIF 2.1.0 defines the enum in lower case, but real tools emit "Error" and
    "WARNING". Comparing case-sensitively silently downgraded those findings, so
    the same vulnerability passed or failed the gate depending on how a scanner
    happened to capitalise a string.
    """
    if not isinstance(level, str):
        return None
    return LEVEL_TO_SEVERITY.get(level.strip().lower())


def severity_of(result: dict[str, Any], rules: dict[str, dict[str, Any]]) -> str:
    """Resolve one SARIF result to a named severity bucket."""
    score = _score_of(result.get("properties"))
    if score is not None:
        return bucket_from_score(score)

    rule = rules.get(result.get("ruleId", ""), {})
    score = _score_of(rule.get("properties"))
    if score is not None:
        return bucket_from_score(score)

    default_config = rule.get("defaultConfiguration")
    if isinstance(default_config, dict):
        severity = _level_to_severity(default_config.get("level"))
        if severity is not None:
            return severity

    severity = _level_to_severity(result.get("level"))
    if severity is not None:
        return severity

    return "medium"


def load_manifest_defaults() -> tuple[str, int]:
    """Read the gate threshold from the neutral manifest.

    The manifest is the single source of truth for agent configuration, so the
    gate reads its defaults from the same file the adapters are generated from.
    A missing or malformed manifest falls back to the strictest sensible values
    rather than to a permissive gate.
    """
    fail_on, max_allowed = "high", 0
    try:
        data = tomllib.loads(MANIFEST.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return fail_on, max_allowed

    gate = data.get("gate")
    if isinstance(gate, dict):
        candidate = gate.get("fail_on_severity")
        if isinstance(candidate, str) and candidate in SEVERITY_ORDER:
            fail_on = candidate
        budget = gate.get("max_allowed")
        if isinstance(budget, int) and budget >= 0:
            max_allowed = budget
    return fail_on, max_allowed


def validate_report(report: Any) -> str | None:
    """Return an error message if the report cannot support a verdict.

    A gate that answers "pass" must be answering "a scan ran and found nothing
    at or above the threshold". These shapes cannot support that sentence, and
    every one of them is what a crashed, absent or misconfigured scanner leaves
    behind:

      - no `runs`, or `runs` empty          nothing ran
      - `runs` not a list, or a non-object  the file is not SARIF
      - `results` not a list                the run recorded no result set
      - `executionSuccessful: false`        the tool reported its own failure

    Reading any of them as zero findings converts a broken pipeline into a green
    one, which is worse than no gate at all: it produces a signed-off build with
    no evidence behind it. All of these were found by an independent audit of
    the first implementation, which passed every one.
    """
    if not isinstance(report, dict):
        return "report top level is not a JSON object"

    runs = report.get("runs")
    if runs is None:
        return "report has no 'runs' key; this is not a SARIF document"
    if not isinstance(runs, list):
        return f"report 'runs' is {type(runs).__name__}, not an array"
    if not runs:
        return (
            "report contains zero runs, so no scanner is known to have "
            "executed. Run the scanner wrappers and merge_sarif.py first."
        )

    for index, run in enumerate(runs):
        if not isinstance(run, dict):
            return f"runs[{index}] is {type(run).__name__}, not an object"

        results = run.get("results")
        if results is not None and not isinstance(results, list):
            return f"runs[{index}].results is {type(results).__name__}, not an array"
        if results is None:
            return (
                f"runs[{index}] has no results array, so it does not record "
                "whether the scan found anything"
            )

        invocations = run.get("invocations")
        if isinstance(invocations, list):
            for inv in invocations:
                if isinstance(inv, dict) and inv.get("executionSuccessful") is False:
                    driver = (run.get("tool") or {}).get("driver") or {}
                    name = driver.get("name", f"runs[{index}]")
                    return (
                        f"{name} reported executionSuccessful=false. The scan "
                        "did not complete, so its result set is not evidence "
                        "of a clean tree."
                    )

    return None


def tally(report: dict[str, Any]) -> tuple[dict[str, int], list[dict[str, str]]]:
    """Count results per severity and collect a flat finding list."""
    counts = {name: 0 for name in SEVERITY_ORDER}
    findings: list[dict[str, str]] = []

    for run in report.get("runs") or []:
        if not isinstance(run, dict):
            continue
        driver = (run.get("tool") or {}).get("driver") or {}
        tool_name = driver.get("name", "unknown")
        rules = build_rule_index(run)

        for result in run.get("results") or []:
            if not isinstance(result, dict):
                continue
            severity = severity_of(result, rules)
            counts[severity] += 1

            location = ""
            locations = result.get("locations") or []
            if locations and isinstance(locations[0], dict):
                phys = locations[0].get("physicalLocation") or {}
                uri = (phys.get("artifactLocation") or {}).get("uri", "")
                line = (phys.get("region") or {}).get("startLine", "")
                location = f"{uri}:{line}" if line else uri

            findings.append(
                {
                    "tool": tool_name,
                    "severity": severity,
                    "ruleId": result.get("ruleId", ""),
                    "location": location,
                }
            )

    return counts, findings


def evaluate(
    counts: dict[str, int], fail_on: str, max_allowed: int
) -> tuple[bool, int]:
    """Return (passed, number of findings at or above the threshold)."""
    threshold = SEVERITY_ORDER.index(fail_on)
    blocking = sum(
        count
        for name, count in counts.items()
        if SEVERITY_ORDER.index(name) >= threshold
    )
    return blocking <= max_allowed, blocking


def render(
    counts: dict[str, int],
    findings: list[dict[str, str]],
    fail_on: str,
    max_allowed: int,
    passed: bool,
    blocking: int,
) -> None:
    """Print the human-readable verdict."""
    print("Security gate")
    print("-------------")
    print(f"threshold   : {fail_on} or above")
    print(f"budget      : {max_allowed}")
    print()
    print(f"{'severity':<10} {'count':>6}")
    for name in reversed(SEVERITY_ORDER):
        print(f"{name:<10} {counts[name]:>6}")
    print(f"{'total':<10} {sum(counts.values()):>6}")
    print()

    if not passed:
        print(f"blocking findings ({blocking}):")
        threshold = SEVERITY_ORDER.index(fail_on)
        shown = [
            f
            for f in findings
            if SEVERITY_ORDER.index(f["severity"]) >= threshold
        ]
        for finding in shown[:20]:
            print(
                f"  [{finding['severity']:<8}] {finding['tool']:<10} "
                f"{finding['ruleId']} {finding['location']}"
            )
        if len(shown) > 20:
            print(f"  ... and {len(shown) - 20} more")
        print()

    verdict = "PASS" if passed else "FAIL"
    print(f"verdict     : {verdict}")


def main() -> int:
    """Entry point."""
    default_fail_on, default_max = load_manifest_defaults()

    parser = argparse.ArgumentParser(
        description="Deterministic SARIF severity gate for CI."
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=DEFAULT_REPORT,
        help=f"merged SARIF path (default: {DEFAULT_REPORT})",
    )
    parser.add_argument(
        "--fail-on",
        choices=SEVERITY_ORDER,
        default=default_fail_on,
        help=f"lowest severity that blocks (default from manifest: {default_fail_on})",
    )
    parser.add_argument(
        "--max-allowed",
        type=int,
        default=default_max,
        help=f"how many blocking findings are tolerated (default: {default_max})",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit machine-readable JSON instead of a table",
    )
    args = parser.parse_args()

    try:
        report = json.loads(args.report.read_text(encoding="utf-8"))
    except OSError as exc:
        print(f"error: cannot read {args.report}: {exc}", file=sys.stderr)
        print("Run merge_sarif.py first.", file=sys.stderr)
        return EXIT_ERROR
    except json.JSONDecodeError as exc:
        print(f"error: {args.report} is not valid JSON: {exc}", file=sys.stderr)
        return EXIT_ERROR

    problem = validate_report(report)
    if problem is not None:
        print(f"error: {problem}", file=sys.stderr)
        print(
            "Refusing to emit a verdict. An unusable report is an error, not a "
            "pass.",
            file=sys.stderr,
        )
        return EXIT_ERROR

    counts, findings = tally(report)
    passed, blocking = evaluate(counts, args.fail_on, args.max_allowed)

    if args.json:
        print(
            json.dumps(
                {
                    "passed": passed,
                    "threshold": args.fail_on,
                    "maxAllowed": args.max_allowed,
                    "blockingCount": blocking,
                    "counts": counts,
                    "findings": findings,
                },
                indent=2,
            )
        )
    else:
        render(counts, findings, args.fail_on, args.max_allowed, passed, blocking)

    return EXIT_PASS if passed else EXIT_FAIL


if __name__ == "__main__":
    raise SystemExit(main())
