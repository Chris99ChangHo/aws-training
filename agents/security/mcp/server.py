#!/usr/bin/env python3
"""MCP server exposing the scanner wrappers as tools.

Why this layer exists
---------------------
Tier 1 gives each harness its own adapter, which means each harness also gets
its own permission model to configure. Tier 2 removes that duplication: the
scanners become MCP tools, so Kiro CLI, Claude Code, Cline, Continue, Zed and
anything else that speaks MCP consume the same server, and argument validation
happens once, here, instead of once per adapter.

Why no SDK
----------
The protocol surface needed for a tool server is three methods over
newline-delimited JSON-RPC 2.0. Implementing it against the standard library
keeps the install story to "have Python", which matters because this server is
the thing a CI runner has to start before it can scan anything. It also means
Python 3.14 needs no wheel that may not exist yet.

Security notes
--------------
- Subprocesses are spawned with an argument list and never with shell=True, so
  there is no shell for an argument to escape from.
- Arguments are still validated against a conservative character set, because
  a scanner flag smuggled through a "path" is a real bug class even without a
  shell.
- The DAST scope check is not repeated here. It lives in run_dast.sh, which
  this server calls, so the shell path and the MCP path enforce one rule from
  one file. Duplicating the check here would create a second copy to drift.

Run standalone for a protocol smoke test:
    echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | mcp/server.py
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

LAB_ROOT = Path(__file__).resolve().parent.parent
SCANNERS = LAB_ROOT / "scanners"
GATE_DIR = LAB_ROOT.parent / "core" / "gate"
SCOPE_FILE = LAB_ROOT / ".sec-scope"

SERVER_NAME = "sec-scanners"
SERVER_VERSION = "1.0.0"
FALLBACK_PROTOCOL = "2024-11-05"

# Wrapper exit codes, mirrored from scanners/_lib.sh.
EXIT_MEANING = {
    0: "scan completed (findings may exist; gate_report decides pass/fail)",
    1: "gate failed: blocking findings exceed the budget",
    2: "refused: authorisation scope violation",
    3: "required scanner is not installed",
    4: "scan or report error",
}

# Deliberately narrow. Scan targets are paths, hosts and URLs; none of them
# need quotes, spaces or shell punctuation.
#
# Anchored with \A and \Z rather than ^ and $. In Python, `$` also matches just
# before a trailing newline, so `^...$` accepts "localhost\n" — the validator
# would pass an argument carrying a line break. \Z has no such exception.
SAFE_ARG = re.compile(r"\A[A-Za-z0-9._:/@%?=&+~-]{1,512}\Z")

# Even without a shell, there is no reason for a scanner to be pointed at a
# key store.
CREDENTIAL_HINT = re.compile(
    r"(\.ssh|\.aws|\.gnupg|\.kube|\.netrc|id_rsa|id_ed25519|\.pem|\.p12|credentials)",
    re.IGNORECASE,
)

TIMEOUT_SECONDS = 900


def log(message: str) -> None:
    """Write a diagnostic to stderr.

    stdout carries the JSON-RPC stream; a stray print there desynchronises the
    client and the failure looks like a protocol bug rather than a log line.
    """
    print(f"[{SERVER_NAME}] {message}", file=sys.stderr, flush=True)


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

TOOLS: list[dict[str, Any]] = [
    {
        "name": "preflight",
        "description": (
            "Report which security scanners are installed on this host. Run "
            "this before any scan so a missing tool is not mistaken for a "
            "clean result."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
    {
        "name": "get_scope",
        "description": (
            "Show the DAST authorisation scope (.sec-scope): the only hosts "
            "this agent may actively scan. Read-only; the agent cannot widen "
            "the scope."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
    {
        "name": "run_sast",
        "description": (
            "Static analysis of source code with Semgrep against pinned "
            "rulesets. Writes SARIF to reports/sast.sarif."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": (
                        "Directory or file to scan. Defaults to the "
                        "current directory."
                    ),
                }
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "run_sca",
        "description": (
            "Dependency, secret and IaC misconfiguration scan with Trivy. "
            "Accepts a filesystem path or a container image reference. Writes "
            "SARIF to reports/sca.sarif."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": (
                        "Path to scan, or an image reference such as "
                        "nginx:1.27."
                    ),
                }
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "run_dast",
        "description": (
            "Active scan of a running target with Nuclei. The target MUST "
            "already be listed in .sec-scope; the wrapper refuses anything "
            "else and the refusal is final. Writes SARIF to reports/dast.sarif."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": "URL or host to scan, e.g. http://localhost:8080.",
                }
            },
            "required": ["target"],
            "additionalProperties": False,
        },
    },
    {
        "name": "merge_reports",
        "description": (
            "Merge every SARIF file in reports/ into reports/merged.sarif so "
            "the gate can evaluate all scanners together."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
    {
        "name": "gate_report",
        "description": (
            "Evaluate the merged SARIF against a severity threshold and return "
            "a deterministic pass/fail verdict with counts. This decision does "
            "not involve a model."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "fail_on": {
                    "type": "string",
                    "enum": ["info", "low", "medium", "high", "critical"],
                    "description": (
                        "Lowest severity that blocks. Defaults to the "
                        "manifest value."
                    ),
                },
                "max_allowed": {
                    "type": "integer",
                    "minimum": 0,
                    "description": (
                        "How many blocking findings are tolerated. "
                        "Defaults to the manifest value."
                    ),
                },
                "as_json": {
                    "type": "boolean",
                    "description": "Return machine-readable JSON instead of a table.",
                },
            },
            "additionalProperties": False,
        },
    },
]


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------


class ToolError(Exception):
    """A tool call that must be reported to the model as an error."""


def check_arg(value: Any, label: str) -> str:
    """Validate one string argument, or raise ToolError."""
    if not isinstance(value, str):
        raise ToolError(f"{label} must be a string, got {type(value).__name__}")
    if not SAFE_ARG.match(value):
        raise ToolError(
            f"{label} rejected: {value!r} contains characters outside the "
            "allowed set [A-Za-z0-9._:/@%?=&+~-]."
        )
    if CREDENTIAL_HINT.search(value):
        raise ToolError(
            f"{label} rejected: {value!r} points at credential material. "
            "Report the location of a committed secret, never read its value."
        )
    return value


def execute(argv: list[str]) -> tuple[int, str]:
    """Run a wrapper and return (exit code, combined output)."""
    # The shared gate in agents/core cannot infer which agent it serves from
    # its own path, so name it explicitly rather than relying on cwd.
    env = {**os.environ, "AGENT_ROOT": str(LAB_ROOT)}
    try:
        proc = subprocess.run(  # noqa: S603 - argv list, never shell=True
            argv,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
            cwd=str(LAB_ROOT),
            env=env,
            check=False,
        )
    except FileNotFoundError as exc:
        raise ToolError(f"cannot execute {argv[0]}: {exc}") from exc
    except subprocess.TimeoutExpired:
        raise ToolError(
            f"{argv[0]} exceeded {TIMEOUT_SECONDS}s and was terminated. "
            "Narrow the scan target and retry."
        ) from None

    output = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, output.strip()


def call_tool(name: str, args: dict[str, Any]) -> tuple[str, bool]:
    """Dispatch one tool call. Return (text, is_error)."""
    if name == "get_scope":
        try:
            body = SCOPE_FILE.read_text(encoding="utf-8")
        except OSError as exc:
            raise ToolError(f"cannot read {SCOPE_FILE}: {exc}") from exc
        hosts = [
            line.strip()
            for line in body.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        return (
            "Authorised DAST targets (.sec-scope):\n"
            + "\n".join(f"  - {h}" for h in hosts)
            + "\n\nAnything else is refused. Only a human may edit this file.",
            False,
        )

    if name == "preflight":
        argv = ["sh", str(SCANNERS / "preflight.sh")]
    elif name == "run_sast":
        argv = ["sh", str(SCANNERS / "run_sast.sh")]
        if "path" in args:
            argv.append(check_arg(args["path"], "path"))
    elif name == "run_sca":
        argv = ["sh", str(SCANNERS / "run_sca.sh")]
        if "target" in args:
            argv.append(check_arg(args["target"], "target"))
    elif name == "run_dast":
        if "target" not in args:
            raise ToolError("run_dast requires a 'target'.")
        argv = [
            "sh",
            str(SCANNERS / "run_dast.sh"),
            check_arg(args["target"], "target"),
        ]
    elif name == "merge_reports":
        argv = [sys.executable, str(GATE_DIR / "merge_sarif.py")]
    elif name == "gate_report":
        argv = [sys.executable, str(GATE_DIR / "gate.py")]
        if "fail_on" in args:
            argv += ["--fail-on", check_arg(args["fail_on"], "fail_on")]
        if "max_allowed" in args:
            budget = args["max_allowed"]
            if not isinstance(budget, int) or isinstance(budget, bool) or budget < 0:
                raise ToolError("max_allowed must be a non-negative integer.")
            argv += ["--max-allowed", str(budget)]
        if args.get("as_json"):
            argv.append("--json")
    else:
        raise ToolError(f"unknown tool: {name}")

    code, output = execute(argv)
    meaning = EXIT_MEANING.get(code, "unrecognised exit code")

    # State the exit code and its meaning explicitly. A scanner that exits 1
    # because it found something and a scanner that exits 3 because it is not
    # installed look similar in raw output, and conflating them is how an
    # unscanned repository gets reported as clean.
    header = f"exit={code} ({meaning})"
    is_error = code not in (0, 1)
    return f"{header}\n\n{output}" if output else header, is_error


# ---------------------------------------------------------------------------
# JSON-RPC plumbing
# ---------------------------------------------------------------------------


def response(request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    """Build a JSON-RPC success envelope."""
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    """Build a JSON-RPC error envelope."""
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message},
    }


def handle(request: dict[str, Any]) -> dict[str, Any] | None:
    """Handle one request. Return None for notifications."""
    method = request.get("method")
    request_id = request.get("id")
    params = request.get("params") or {}

    # Notifications carry no id and must not be answered.
    if request_id is None:
        return None

    if method == "initialize":
        client_version = params.get("protocolVersion")
        return response(
            request_id,
            {
                "protocolVersion": client_version
                if isinstance(client_version, str)
                else FALLBACK_PROTOCOL,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            },
        )

    if method == "ping":
        return response(request_id, {})

    if method == "tools/list":
        return response(request_id, {"tools": TOOLS})

    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments") or {}
        if not isinstance(name, str):
            return error(request_id, -32602, "params.name must be a string")
        if not isinstance(args, dict):
            return error(request_id, -32602, "params.arguments must be an object")
        try:
            text, is_error = call_tool(name, args)
        except ToolError as exc:
            # Tool-level failures are reported inside the result, not as a
            # protocol error, so the model can read and act on the reason.
            return response(
                request_id,
                {"content": [{"type": "text", "text": str(exc)}], "isError": True},
            )
        return response(
            request_id,
            {"content": [{"type": "text", "text": text}], "isError": is_error},
        )

    return error(request_id, -32601, f"method not found: {method}")


def main() -> int:
    """Read newline-delimited JSON-RPC from stdin until EOF."""
    log(f"ready. lab root {LAB_ROOT}")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError as exc:
            print(
                json.dumps(error(None, -32700, f"parse error: {exc}")),
                flush=True,
            )
            continue

        if not isinstance(request, dict):
            print(
                json.dumps(error(None, -32600, "request must be an object")),
                flush=True,
            )
            continue

        # Broad except at the process boundary: one malformed request must not
        # take down a long-lived server that a client depends on.
        try:
            reply = handle(request)
        except Exception as exc:  # noqa: BLE001
            log(f"unhandled error in {request.get('method')!r}: {exc!r}")
            reply = error(request.get("id"), -32603, f"internal error: {exc}")

        if reply is not None:
            print(json.dumps(reply), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
