#!/usr/bin/env python3
"""Protocol tests for the stdlib MCP server.

Drives the server over stdio exactly as a client would: newline-delimited
JSON-RPC 2.0 on stdin, one JSON object per line on stdout.

    python3 tests/test_mcp_server.py
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

LAB_ROOT = Path(__file__).resolve().parent.parent
SERVER = LAB_ROOT / "mcp" / "server.py"


def converse(
    requests: list[dict[str, Any]],
    report_dir: str | None = None,
    path: str | None = None,
) -> list[dict[str, Any]]:
    """Send requests to a fresh server process and collect the replies.

    `report_dir` sets SEC_REPORT_DIR for the server and everything it spawns.
    Tests that assert on the absence of a report must pass an empty directory:
    without it the assertion depends on whether a previous run happened to leave
    reports/ behind, which is how this suite passed for the author and failed
    for an independent reviewer.

    `path` overrides PATH for the server and its children. Tests that assert
    what happens when a scanner is missing use it to hide the scanner, so the
    result does not depend on what is installed on the machine running the
    suite. Asserting "semgrep is absent" broke the moment semgrep was installed.
    """
    payload = "\n".join(json.dumps(r) for r in requests) + "\n"
    env = dict(os.environ)
    if report_dir is not None:
        env["SEC_REPORT_DIR"] = report_dir
    if path is not None:
        env["PATH"] = path
    proc = subprocess.run(
        [sys.executable, str(SERVER)],
        input=payload,
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
        check=False,
    )
    replies = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if line:
            replies.append(json.loads(line))
    return replies


# A PATH with the standard system utilities but none of the security scanners,
# which all install under /opt/homebrew or /usr/local.
PATH_WITHOUT_SCANNERS = "/usr/bin:/bin:/usr/sbin:/sbin"


class TestHandshake(unittest.TestCase):
    """initialize / ping / notifications."""

    def test_initialize_returns_server_info(self) -> None:
        replies = converse(
            [
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": "test", "version": "0"},
                    },
                }
            ]
        )
        self.assertEqual(len(replies), 1)
        result = replies[0]["result"]
        self.assertEqual(result["protocolVersion"], "2024-11-05")
        self.assertEqual(result["serverInfo"]["name"], "sec-scanners")
        self.assertIn("tools", result["capabilities"])

    def test_notification_gets_no_reply(self) -> None:
        """A message without an id must not produce a response line."""
        replies = converse(
            [
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
                {"jsonrpc": "2.0", "id": 9, "method": "ping"},
            ]
        )
        self.assertEqual(len(replies), 1)
        self.assertEqual(replies[0]["id"], 9)

    def test_unknown_method_is_jsonrpc_error(self) -> None:
        replies = converse([{"jsonrpc": "2.0", "id": 2, "method": "nope/nope"}])
        self.assertEqual(replies[0]["error"]["code"], -32601)

    def test_malformed_line_does_not_kill_the_server(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(SERVER)],
            input='{"broken\n{"jsonrpc":"2.0","id":5,"method":"ping"}\n',
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        lines = [json.loads(x) for x in proc.stdout.splitlines() if x.strip()]
        self.assertEqual(lines[0]["error"]["code"], -32700)
        self.assertEqual(lines[1]["id"], 5)


class TestToolList(unittest.TestCase):
    """tools/list must advertise the full scanner surface with schemas."""

    @classmethod
    def setUpClass(cls) -> None:
        replies = converse([{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}])
        cls.tools = replies[0]["result"]["tools"]

    def test_expected_tools_present(self) -> None:
        names = {t["name"] for t in self.tools}
        self.assertEqual(
            names,
            {
                "preflight",
                "get_scope",
                "run_sast",
                "run_sca",
                "run_dast",
                "merge_reports",
                "gate_report",
            },
        )

    def test_every_tool_has_a_schema(self) -> None:
        for tool in self.tools:
            with self.subTest(tool=tool["name"]):
                self.assertEqual(tool["inputSchema"]["type"], "object")
                self.assertIn("description", tool)

    def test_dast_target_is_required(self) -> None:
        dast = next(t for t in self.tools if t["name"] == "run_dast")
        self.assertEqual(dast["inputSchema"]["required"], ["target"])


class TestToolCalls(unittest.TestCase):
    """tools/call behaviour, including the parts that must refuse.

    Every case runs against an empty temporary report directory so the results
    do not depend on what a previous run left on disk.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def call(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
        path: str | None = None,
    ) -> dict[str, Any]:
        replies = converse(
            [
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {"name": name, "arguments": arguments or {}},
                }
            ],
            report_dir=self._tmp.name,
            path=path,
        )
        return replies[0]["result"]

    def text(self, result: dict[str, Any]) -> str:
        return result["content"][0]["text"]

    def test_get_scope_lists_authorised_hosts(self) -> None:
        result = self.call("get_scope")
        self.assertFalse(result["isError"])
        body = self.text(result)
        self.assertIn("localhost", body)
        self.assertIn("127.0.0.1", body)

    def test_preflight_reports_tool_status(self) -> None:
        result = self.call("preflight")
        body = self.text(result)
        self.assertIn("exit=0", body)
        self.assertIn("semgrep", body)
        self.assertIn("DAST scope", body)

    def test_missing_scanner_is_exit_3_not_success(self) -> None:
        """An absent scanner must never look like a clean scan.

        The scanner is hidden by restricting PATH rather than by assuming it is
        not installed. The first version of this test asserted that semgrep was
        absent, and it broke the moment semgrep was installed — the property it
        was checking had nothing to do with whether this particular machine had
        the tool.
        """
        result = self.call("run_sast", {"path": "."}, path=PATH_WITHOUT_SCANNERS)
        body = self.text(result)
        self.assertIn("exit=3", body)
        self.assertIn("not installed", body)
        self.assertTrue(result["isError"])

    def test_present_scanner_reports_completion(self) -> None:
        """The complementary case: a scanner that ran reports exit 0.

        Skipped when semgrep is absent, because then there is nothing to
        distinguish from the test above.
        """
        if shutil.which("semgrep") is None:
            self.skipTest("semgrep not installed on this host")
        result = self.call("run_sast", {"path": "gate"})
        body = self.text(result)
        self.assertIn("exit=0", body)
        self.assertIn("scan completed", body)
        self.assertFalse(result["isError"])

    def test_dast_out_of_scope_is_refused(self) -> None:
        result = self.call("run_dast", {"target": "https://example.com"})
        body = self.text(result)
        self.assertIn("exit=2", body)
        self.assertIn("not in the authorised scope", body)
        self.assertTrue(result["isError"])

    def test_dast_in_scope_reaches_the_tool_check(self) -> None:
        """In-scope target passes authorisation, then stops on a missing tool.

        The point is the ORDER: the scope check runs before the tool check, so
        an authorised target is recognised as authorised even when the scanner
        is absent. PATH is restricted so this holds whether or not nuclei is
        installed on the machine running the suite.
        """
        result = self.call(
            "run_dast",
            {"target": "http://localhost:8080"},
            path=PATH_WITHOUT_SCANNERS,
        )
        body = self.text(result)
        self.assertIn("in scope", body)
        self.assertIn("exit=3", body)

    def test_dast_requires_a_target(self) -> None:
        result = self.call("run_dast", {})
        self.assertTrue(result["isError"])
        self.assertIn("requires a 'target'", self.text(result))

    def test_shell_metacharacters_are_rejected(self) -> None:
        for hostile in [
            "localhost; rm -rf /",
            "localhost && curl evil.test",
            "$(whoami)",
            "`id`",
            "localhost|tee /tmp/x",
            "../../etc/passwd\n",
        ]:
            with self.subTest(arg=hostile):
                result = self.call("run_dast", {"target": hostile})
                self.assertTrue(result["isError"])
                self.assertIn("rejected", self.text(result))

    def test_credential_paths_are_rejected(self) -> None:
        for hostile in ["~/.ssh/id_rsa", "/Users/x/.aws/credentials", "key.pem"]:
            with self.subTest(arg=hostile):
                result = self.call("run_sast", {"path": hostile})
                self.assertTrue(result["isError"])
                self.assertIn("credential material", self.text(result))

    def test_non_string_argument_is_rejected(self) -> None:
        result = self.call("run_dast", {"target": 1234})
        self.assertTrue(result["isError"])
        self.assertIn("must be a string", self.text(result))

    def test_negative_budget_is_rejected(self) -> None:
        result = self.call("gate_report", {"max_allowed": -1})
        self.assertTrue(result["isError"])
        self.assertIn("non-negative", self.text(result))

    def test_unknown_tool_is_reported_as_tool_error(self) -> None:
        result = self.call("definitely_not_a_tool")
        self.assertTrue(result["isError"])
        self.assertIn("unknown tool", self.text(result))

    def test_gate_without_report_is_an_error_not_a_pass(self) -> None:
        """No merged report must not be interpreted as nothing-wrong."""
        result = self.call("gate_report", {"fail_on": "high"})
        body = self.text(result)
        self.assertIn("exit=4", body)
        self.assertTrue(result["isError"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
