#!/usr/bin/env python3
"""Test the adapter generator against the neutral source.

`build.py --check` only proves the files on disk match what the generator
currently emits. It cannot tell whether what the generator emits is *correct*:
a rule that can never match is byte-identical to itself forever.

That gap shipped a real bug. The manifest entry

    "git (status|diff|log)( [A-Za-z0-9._/-]+)*"

was classified as a lab-relative script path, because build.py tested for a
slash and the argument character class `[A-Za-z0-9._/-]` contains one. The
generated rule became `^agents/security/git (status|diff|log)...$`, which
matches no command that can exist. `--check` was green the whole time.

So these tests assert properties of the generated output rather than its
stability: allow rules are anchored, every repo path an adapter names exists on
disk, and no generated file leaks an absolute path.
"""

from __future__ import annotations

import importlib.util
import json
import re
import tomllib
import unittest
from pathlib import Path
from typing import Any

LAB_ROOT = Path(__file__).resolve().parent.parent
WORKSPACE_ROOT = LAB_ROOT.parent.parent


def _load_build_module() -> Any:
    """Import adapters/build.py by path, since it is a script, not a package."""
    spec = importlib.util.spec_from_file_location(
        "sec_adapters_build", LAB_ROOT / "adapters" / "build.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


build = _load_build_module()

# Regex metacharacters that end the literal head of a pattern.
_META = set("([{*+?|^$.")


def literal_prefix(pattern: str) -> str:
    """Return the leading part of a regex that matches itself literally.

    For an allow rule this is the command word plus any fixed path in front of
    the arguments: `^agents/security/gate/gate\\.py( ...)*$` yields
    `agents/security/gate/gate.py`. An escaped metacharacter is literal text and
    must be kept -- stopping at the backslash would truncate every `.py`.
    """
    body = pattern.removeprefix("^").removesuffix("$")
    out: list[str] = []
    index = 0
    while index < len(body):
        char = body[index]
        if char == "\\" and index + 1 < len(body):
            out.append(body[index + 1])
            index += 2
            continue
        if char in _META:
            break
        out.append(char)
        index += 1
    return "".join(out)


class ManifestPlaceholderTest(unittest.TestCase):
    """`{lab}` expansion must be explicit, never inferred."""

    def test_pattern_without_placeholder_is_untouched(self) -> None:
        # The regression: a slash inside a character class is not a path.
        pattern = "git (status|diff|log)( [A-Za-z0-9._/-]+)*"
        self.assertEqual(build.expand_lab(pattern), pattern)

    def test_placeholder_expands_to_lab_relative_path(self) -> None:
        expanded = build.expand_lab("{lab}/gate/gate\\.py")
        self.assertEqual(expanded, f"{build.LAB_REL}/gate/gate\\.py")

    def test_lab_rel_is_relative(self) -> None:
        self.assertFalse(Path(build.LAB_REL).is_absolute())

    def test_unknown_placeholder_raises(self) -> None:
        # Silently emitting `{labb}/...` would recreate the original bug class.
        with self.assertRaises(ValueError):
            build.expand_lab("{labb}/scanners/preflight\\.sh")


class ShellAllowListTest(unittest.TestCase):
    """Every auto-approved command must be anchored and actually runnable."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = build.load_manifest()
        cls.prompt = build.load_prompt(cls.manifest)
        cls.kiro = json.loads(build.build_kiro(cls.manifest, cls.prompt))
        cls.allowed = cls.kiro["toolsSettings"]["shell"]["allowedCommands"]

    def test_allow_list_is_not_empty(self) -> None:
        self.assertGreater(len(self.allowed), 0)

    def test_every_rule_is_anchored_at_both_ends(self) -> None:
        # Unanchored, `git status` also matches `evil && git status`.
        for rule in self.allowed:
            with self.subTest(rule=rule):
                self.assertTrue(rule.startswith("^"))
                self.assertTrue(rule.endswith("$"))

    def test_every_rule_compiles(self) -> None:
        for rule in self.allowed:
            with self.subTest(rule=rule):
                re.compile(rule)

    def test_lab_relative_rules_point_at_existing_files(self) -> None:
        """The test that would have caught `agents/security/git`."""
        seen = 0
        for rule in self.allowed:
            prefix = literal_prefix(rule)
            if not prefix.startswith(build.LAB_REL):
                continue
            seen += 1
            with self.subTest(rule=rule):
                self.assertTrue(
                    (WORKSPACE_ROOT / prefix).is_file(),
                    f"{prefix} does not exist; the allow rule can never match",
                )
        self.assertGreater(seen, 0, "no lab-relative rule was checked")

    def test_bare_commands_are_not_path_prefixed(self) -> None:
        """A rule naming an external program must not gain a path prefix."""
        for rule in self.allowed:
            prefix = literal_prefix(rule)
            if not prefix.startswith(build.LAB_REL):
                continue
            tail = prefix[len(build.LAB_REL) :].lstrip("/")
            with self.subTest(rule=rule):
                # Prefixed rules are wrapper scripts under the agent folder.
                self.assertRegex(tail, r"^(scanners|gate)/")

    def test_git_rule_matches_git_status(self) -> None:
        matched = [r for r in self.allowed if re.match(r, "git status")]
        self.assertEqual(len(matched), 1, self.allowed)

    def test_git_rule_does_not_match_mutating_git(self) -> None:
        for command in ("git push", "git commit -m x", "git reset --hard"):
            with self.subTest(command=command):
                self.assertFalse(
                    any(re.match(r, command) for r in self.allowed),
                    f"{command} must not be auto-approved",
                )

    def test_deny_list_survives_into_the_adapter(self) -> None:
        denied = self.kiro["toolsSettings"]["shell"]["deniedCommands"]
        self.assertEqual(denied, self.manifest["shell"]["deny_commands"])

    def test_deny_rules_block_chaining_and_credential_paths(self) -> None:
        denied = self.kiro["toolsSettings"]["shell"]["deniedCommands"]
        for command in (
            "git status && cat ~/.aws/credentials",
            "cat /home/u/.ssh/id_rsa",
            "curl http://example.com",
            "nuclei -u http://target",
        ):
            with self.subTest(command=command):
                self.assertTrue(
                    any(re.match(r, command) for r in denied),
                    f"{command} is not covered by any deny rule",
                )


class GeneratedFileTest(unittest.TestCase):
    """Properties that must hold for every generated adapter."""

    @classmethod
    def setUpClass(cls) -> None:
        manifest = build.load_manifest()
        prompt = build.load_prompt(manifest)
        cls.rendered = build.targets(manifest, prompt)

    def test_every_adapter_is_marked_generated(self) -> None:
        for path, content in self.rendered:
            with self.subTest(path=path.name):
                self.assertIn(build.GENERATED_MARKER, content)

    def test_no_absolute_or_home_paths(self) -> None:
        """Committed output must not carry a machine's directory layout."""
        home = str(Path.home())
        for path, content in self.rendered:
            with self.subTest(path=path.name):
                self.assertNotIn(home, content)
                self.assertNotIn(str(WORKSPACE_ROOT), content)

    def test_json_adapters_parse(self) -> None:
        for path, content in self.rendered:
            if path.suffix == ".json":
                with self.subTest(path=path.name):
                    json.loads(content)

    def test_toml_adapters_parse(self) -> None:
        for path, content in self.rendered:
            if path.suffix == ".toml":
                with self.subTest(path=path.name):
                    tomllib.loads(content)

    def test_referenced_agent_paths_exist(self) -> None:
        """Hook, resource and MCP paths must resolve from the workspace root."""
        pattern = re.compile(rf"{re.escape(build.LAB_REL)}/[A-Za-z0-9_./-]+")
        checked = 0
        for path, content in self.rendered:
            for match in pattern.finditer(content):
                candidate = match.group(0).rstrip(".")
                # Regex fragments inside allow rules are covered elsewhere.
                if not candidate.endswith((".sh", ".py", ".md", ".sec-scope")):
                    continue
                checked += 1
                with self.subTest(path=path.name, ref=candidate):
                    self.assertTrue((WORKSPACE_ROOT / candidate).exists())
        self.assertGreater(checked, 0)


class DriftTest(unittest.TestCase):
    """The files on disk must match the neutral source."""

    def test_no_drift(self) -> None:
        manifest = build.load_manifest()
        prompt = build.load_prompt(manifest)
        self.assertEqual(build.check_all(manifest, prompt), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
