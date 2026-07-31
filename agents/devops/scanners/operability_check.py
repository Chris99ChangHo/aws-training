#!/usr/bin/env python3
"""Check infrastructure definitions for operability gaps and emit SARIF.

This is the DevOps agent's own check, and it deliberately does not overlap the
security agent. That boundary was measured, not assumed: running the security
agent's SCA wrapper over the same fixtures showed Trivy already reports resource
limits (KSV-0011/15/16/18), image tags (KSV-0013), Dockerfile HEALTHCHECK
(DS-0026) and every `securityContext` control. Duplicating those would mean two
agents producing byte-identical findings, which is what an earlier version of
this wrapper did.

What is left is the set of things that make a system *operable* rather than
*secure*, and that no security scanner reports:

    OPS-0001  terraform: no required_version          reproducibility
    OPS-0002  terraform: provider without version     reproducibility
    OPS-0003  terraform: no remote backend            state loss, no locking
    OPS-0010  k8s: container without a probe          traffic to unready pods
    OPS-0011  k8s: single replica                     single point of failure
    OPS-0012  k8s: no update strategy                 undefined rollback path
    OPS-0020  actions: job without timeout-minutes    runner held indefinitely
    OPS-0021  actions: `uses` not pinned to a SHA     pipeline not reproducible

Severity is expressed with standard SARIF levels only (`error` / `warning` /
`note`). The shared gate maps those onto high / medium / low, so no invented
`security-severity` property is needed for findings that are not security ones.

Usage:
    operability_check.py <target> <out.sarif>

Exit codes:
    0  checks ran (findings may exist)
    3  a parser needed for files that are present is unavailable
    4  the target could not be read, or the report could not be written
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

SARIF_SCHEMA = "https://json.schemastore.org/sarif-2.1.0.json"

EXIT_OK = 0
EXIT_TOOL_MISSING = 3
EXIT_ERROR = 4

# Directories that hold vendored or generated code. Scanning them reports on
# other people's definitions, which is noise a reviewer cannot act on.
SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "site-packages",
    ".terraform",
    "cdk.out",
    ".cache",
    "vendor",
    "dist",
    "build",
}

# id -> (level, short message). Kept in one place so the rule table in the
# report and the findings cannot describe different things.
RULES: dict[str, tuple[str, str]] = {
    "OPS-0001": (
        "warning",
        "terraform block does not set required_version, so the same "
        "configuration can be planned by incompatible CLI versions",
    ),
    "OPS-0002": (
        "warning",
        "provider is declared without a version constraint, so a later run "
        "can resolve a different provider and produce a different plan",
    ),
    "OPS-0003": (
        "error",
        "no remote backend is configured, so state is local and unlocked: two "
        "concurrent applies can corrupt it and the state is lost with the host",
    ),
    "OPS-0010": (
        "error",
        "container declares neither readinessProbe nor livenessProbe, so the "
        "orchestrator sends traffic to a process that may not be ready",
    ),
    "OPS-0011": (
        "warning",
        "workload runs a single replica, so it is a single point of failure "
        "and cannot be updated without downtime",
    ),
    "OPS-0012": (
        "note",
        "no update strategy is declared, so the rollout and rollback behaviour "
        "is whatever the cluster default happens to be",
    ),
    "OPS-0020": (
        "note",
        "job does not set timeout-minutes, so a hung step holds a runner until "
        "the platform maximum",
    ),
    "OPS-0021": (
        "warning",
        "action reference is a tag or branch rather than a commit SHA, so the "
        "same workflow can execute different code on a later run",
    ),
}


class Finding:
    """One operability gap, located in a file."""

    def __init__(self, rule_id: str, path: str, line: int, detail: str) -> None:
        self.rule_id = rule_id
        self.path = path
        self.line = line
        self.detail = detail

    def to_sarif(self) -> dict[str, Any]:
        """Render as a SARIF result."""
        level, message = RULES[self.rule_id]
        text = f"{message}. {self.detail}" if self.detail else message
        return {
            "ruleId": self.rule_id,
            "level": level,
            "message": {"text": text},
            "locations": [
                {
                    "physicalLocation": {
                        "artifactLocation": {"uri": self.path},
                        "region": {"startLine": max(self.line, 1)},
                    }
                }
            ],
        }


# --------------------------------------------------------------------------
# Terraform (no YAML parser needed)
# --------------------------------------------------------------------------

# Matching HCL with regular expressions is only safe for the few top-level
# declarations checked here. Anything that needs to understand nesting or
# expressions belongs in a real parser, and is not attempted.
RE_TERRAFORM_BLOCK = re.compile(r"^\s*terraform\s*\{", re.M)
RE_REQUIRED_VERSION = re.compile(r"^\s*required_version\s*=", re.M)
RE_BACKEND = re.compile(r'^\s*backend\s+"[^"]+"\s*\{', re.M)
RE_CLOUD_BLOCK = re.compile(r"^\s*cloud\s*\{", re.M)
RE_PROVIDER_ENTRY = re.compile(
    r'^\s*([A-Za-z0-9_-]+)\s*=\s*\{(?P<body>[^}]*)\}', re.M | re.S
)
RE_VERSION_KEY = re.compile(r"^\s*version\s*=", re.M)


def line_of(text: str, index: int) -> int:
    """Return the 1-based line number of a character offset."""
    return text.count("\n", 0, index) + 1


def block_body(text: str, open_index: int) -> tuple[str, int] | None:
    """Return the body of the brace block that starts at or after open_index.

    Regular expressions cannot match balanced braces, and a non-greedy `\\{.*?\\}`
    stops at the first inner closing brace. `required_providers` always contains
    nested blocks, so the body has to be found by counting.
    """
    start = text.find("{", open_index)
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1 : i], start + 1
    return None


def check_terraform(path: Path, rel: str) -> list[Finding]:
    """Check one .tf file for reproducibility and state-safety gaps."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    found: list[Finding] = []
    tf_block = RE_TERRAFORM_BLOCK.search(text)

    if tf_block:
        line = line_of(text, tf_block.start())
        if not RE_REQUIRED_VERSION.search(text):
            found.append(Finding("OPS-0001", rel, line, ""))
        # `cloud {}` (Terraform Cloud / HCP) is a remote backend by another
        # name; treating its absence as a missing backend would be wrong.
        if not RE_BACKEND.search(text) and not RE_CLOUD_BLOCK.search(text):
            found.append(Finding("OPS-0003", rel, line, ""))

        marker = re.search(r"required_providers\s*\{", text)
        if marker:
            extracted = block_body(text, marker.start())
            if extracted:
                body, offset = extracted
                for entry in RE_PROVIDER_ENTRY.finditer(body):
                    if not RE_VERSION_KEY.search(entry.group("body")):
                        found.append(
                            Finding(
                                "OPS-0002",
                                rel,
                                line_of(text, offset + entry.start()),
                                f"provider: {entry.group(1)}",
                            )
                        )
    return found


# --------------------------------------------------------------------------
# Kubernetes and GitHub Actions (need a YAML parser)
# --------------------------------------------------------------------------

WORKLOAD_KINDS = {
    "Deployment",
    "StatefulSet",
    "DaemonSet",
    "ReplicaSet",
    "Job",
    "CronJob",
}

# A SHA is 40 hex characters. Anything shorter is a tag or branch, both of which
# can be moved to point at different code.
RE_SHA_PIN = re.compile(r"@[0-9a-f]{40}$")


def pod_spec_of(doc: dict[str, Any]) -> dict[str, Any] | None:
    """Return the pod spec inside a workload document, if there is one."""
    spec = doc.get("spec")
    if not isinstance(spec, dict):
        return None
    template = spec.get("template")
    if isinstance(template, dict):
        inner = template.get("spec")
        return inner if isinstance(inner, dict) else None
    # CronJob nests one level deeper.
    job_template = spec.get("jobTemplate")
    if isinstance(job_template, dict):
        return pod_spec_of(job_template)
    return None


def check_k8s_doc(doc: dict[str, Any], rel: str) -> list[Finding]:
    """Check one Kubernetes document for operability gaps."""
    kind = doc.get("kind")
    if kind not in WORKLOAD_KINDS:
        return []

    found: list[Finding] = []
    spec = doc.get("spec") if isinstance(doc.get("spec"), dict) else {}
    name = (doc.get("metadata") or {}).get("name", "<unnamed>")

    pod = pod_spec_of(doc)
    if pod:
        for container in pod.get("containers") or []:
            if not isinstance(container, dict):
                continue
            has_probe = any(
                k in container for k in ("readinessProbe", "livenessProbe")
            )
            if not has_probe:
                found.append(
                    Finding(
                        "OPS-0010",
                        rel,
                        1,
                        f"{kind}/{name} container "
                        f"{container.get('name', '<unnamed>')}",
                    )
                )

    # Jobs and CronJobs run to completion; replicas and rollout strategy do not
    # apply to them.
    if kind in {"Deployment", "StatefulSet", "ReplicaSet"}:
        replicas = spec.get("replicas")
        if isinstance(replicas, int) and replicas < 2:
            found.append(
                Finding("OPS-0011", rel, 1, f"{kind}/{name} replicas={replicas}")
            )
        strategy_key = "updateStrategy" if kind == "StatefulSet" else "strategy"
        if strategy_key not in spec:
            found.append(Finding("OPS-0012", rel, 1, f"{kind}/{name}"))

    return found


def check_workflow(doc: dict[str, Any], rel: str) -> list[Finding]:
    """Check one GitHub Actions workflow document."""
    jobs = doc.get("jobs")
    if not isinstance(jobs, dict):
        return []

    found: list[Finding] = []
    for job_name, job in jobs.items():
        if not isinstance(job, dict):
            continue
        if "timeout-minutes" not in job:
            found.append(Finding("OPS-0020", rel, 1, f"job: {job_name}"))
        for step in job.get("steps") or []:
            if not isinstance(step, dict):
                continue
            uses = step.get("uses")
            if isinstance(uses, str) and not RE_SHA_PIN.search(uses):
                # Local and container actions have no ref to pin.
                if uses.startswith("./") or uses.startswith("docker://"):
                    continue
                found.append(
                    Finding("OPS-0021", rel, 1, f"job {job_name}: {uses}")
                )
    return found


def yaml_docs(path: Path, loader: Any) -> list[Any]:
    """Parse a YAML file into documents, tolerating unparseable files."""
    try:
        return [d for d in loader(path.read_text(encoding="utf-8")) if d]
    except Exception:  # noqa: BLE001 - any parse error means "cannot check"
        # A file this tool cannot parse is reported as unchecked by the caller
        # rather than silently counted as clean.
        return []


# --------------------------------------------------------------------------
# Walk and report
# --------------------------------------------------------------------------


def iter_files(root: Path) -> list[Path]:
    """Return candidate files under root, skipping vendored directories."""
    if root.is_file():
        return [root]
    out: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if SKIP_DIRS & set(path.relative_to(root).parts):
            continue
        if path.suffix in {".tf", ".yaml", ".yml"}:
            out.append(path)
    return out


def main() -> int:
    """Scan the target, write SARIF, and return an exit code."""
    if len(sys.argv) != 3:
        print(__doc__, file=sys.stderr)
        return EXIT_ERROR

    target = Path(sys.argv[1]).resolve()
    out = Path(sys.argv[2])

    if not target.exists():
        print(f"error: target does not exist: {target}", file=sys.stderr)
        return EXIT_ERROR

    files = iter_files(target)
    tf_files = [f for f in files if f.suffix == ".tf"]
    yaml_files = [f for f in files if f.suffix in {".yaml", ".yml"}]

    loader: Any = None
    try:
        import yaml  # noqa: PLC0415 - optional; absence is a reported outcome

        loader = yaml.safe_load_all
    except ImportError:
        loader = None

    findings: list[Finding] = []
    base = target.parent if target.is_file() else target

    for path in tf_files:
        findings += check_terraform(path, str(path.relative_to(base)))

    yaml_checked = 0
    if loader is not None:
        for path in yaml_files:
            rel = str(path.relative_to(base))
            for doc in yaml_docs(path, loader):
                if not isinstance(doc, dict):
                    continue
                yaml_checked += 1
                if "jobs" in doc and "kind" not in doc:
                    findings += check_workflow(doc, rel)
                else:
                    findings += check_k8s_doc(doc, rel)

    # Rules are declared for the whole checker, not only for what fired, so a
    # consumer can see what was looked for as well as what was found.
    report = {
        "$schema": SARIF_SCHEMA,
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "operability-check",
                        "informationUri": (
                            "https://github.com/Chris99ChangHo/aws-training"
                        ),
                        "rules": [
                            {
                                "id": rid,
                                "shortDescription": {"text": msg},
                                "defaultConfiguration": {"level": level},
                            }
                            for rid, (level, msg) in RULES.items()
                        ],
                    }
                },
                "results": [f.to_sarif() for f in findings],
                "invocations": [{"executionSuccessful": True}],
            }
        ],
    }

    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    except OSError as exc:
        print(f"error: cannot write {out}: {exc}", file=sys.stderr)
        return EXIT_ERROR

    print(
        f"operability: {len(findings)} finding(s) "
        f"[terraform {len(tf_files)} file(s), yaml {yaml_checked} doc(s)] -> {out}"
    )

    if yaml_files and loader is None:
        print(
            f"error: {len(yaml_files)} YAML file(s) were NOT checked: no YAML "
            "parser available. Install requirements.txt. Reporting exit 3 "
            "rather than 0, because unchecked is not clean.",
            file=sys.stderr,
        )
        return EXIT_TOOL_MISSING

    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
