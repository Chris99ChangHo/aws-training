#!/usr/bin/env python3
"""Generate harness adapters from the neutral agent definition.

Tier 1 of the design. `agent/SYSTEM_PROMPT.md` and `agent/manifest.toml` are the
only hand-edited sources; everything under `.kiro/` and `.claude/` is output.
Editing an adapter directly is a bug, and `--check` exists to catch it in CI.

The interesting part is the mapping table below: it is the entire vendor
coupling of this project, about sixty lines, against roughly a thousand lines of
prompt, scanners, gate and MCP server that no harness knows about.

Usage:
    build.py                 write the adapters
    build.py --check         exit 1 if what is on disk differs from the source
    build.py --print kiro    dump one adapter to stdout without writing
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from pathlib import Path
from typing import Any

LAB_ROOT = Path(__file__).resolve().parent.parent
WORKSPACE_ROOT = LAB_ROOT.parent.parent
MANIFEST_PATH = LAB_ROOT / "agent" / "manifest.toml"

# Paths are written relative to the workspace root, never absolute. Both
# harnesses discover workspace agents by walking up from the working directory,
# so the working directory is the workspace root by construction. Absolute
# paths would also embed the developer's home directory in a file that gets
# committed.
LAB_REL = LAB_ROOT.relative_to(WORKSPACE_ROOT).as_posix()
# Shared code lives beside the agent folders, not inside one of them. Extracted
# once a second agent needed the same deterministic gate (agents/README.md
# principle 3: abstract when there are two consumers, not before).
CORE_ROOT = LAB_ROOT.parent / "core"
CORE_REL = CORE_ROOT.relative_to(WORKSPACE_ROOT).as_posix()

KIRO_OUT = WORKSPACE_ROOT / ".kiro" / "agents" / "generic-sec-agent.json"
CLAUDE_AGENT_OUT = WORKSPACE_ROOT / ".claude" / "agents" / "generic-sec-agent.md"
CLAUDE_SETTINGS_OUT = WORKSPACE_ROOT / ".claude" / "settings.json"
CLAUDE_SETTINGS_FRAGMENT = (
    WORKSPACE_ROOT / ".claude" / "settings.generic-sec-agent.json"
)
CLAUDE_SESSION_GUARD_OUT = (
    WORKSPACE_ROOT / ".claude" / "settings.local.json.example"
)
CODEX_CONFIG_OUT = WORKSPACE_ROOT / ".codex" / "config.toml"
CODEX_CONFIG_FRAGMENT = WORKSPACE_ROOT / ".codex" / "config.generic-sec-agent.toml"
CODEX_PROMPT_OUT = WORKSPACE_ROOT / ".codex" / "generic-sec-agent.md"

GENERATED_MARKER = "GENERATED FILE - do not edit"

GENERATED_NOTE = (
    f"{GENERATED_MARKER}. Source: {LAB_REL}/agent/"
    f"(SYSTEM_PROMPT.md + manifest.toml). Regenerate with "
    f"python3 {LAB_REL}/adapters/build.py"
)

# --------------------------------------------------------------------------
# The mapping table: neutral capability -> harness tool names.
#
# This table plus the three functions that read it is the entire vendor
# coupling of the project. Everything else is harness-agnostic.
#
# Codex is deliberately sparse here, and the empty lists are the interesting
# part. Codex has no separate file-read or search tool: it reads and greps
# through the shell. Kiro and Claude Code expose `read`/`Read` as tools of
# their own, which is why the PreToolUse matcher below has to name them
# explicitly. A guard hooked only to the shell tool would never see
# `Read ~/.aws/credentials` on those two harnesses.
# --------------------------------------------------------------------------

CAPABILITY_TO_TOOLS: dict[str, dict[str, list[str]]] = {
    "read_files": {
        "kiro": ["read"],
        "claude_code": ["Read"],
        "codex": [],  # via the shell
    },
    "write_files": {
        "kiro": ["write"],
        "claude_code": ["Write", "Edit"],
        "codex": ["apply_patch"],
    },
    "run_shell": {
        "kiro": ["shell"],
        "claude_code": ["Bash"],
        "codex": ["Bash"],
    },
    "search_code": {
        "kiro": ["grep", "glob", "code"],
        "claude_code": ["Grep", "Glob"],
        "codex": [],  # via the shell
    },
    "fetch_web": {
        "kiro": ["web_fetch"],
        "claude_code": ["WebFetch", "WebSearch"],
        "codex": ["WebSearch"],
    },
}

# Which tool names the PreToolUse guard must be attached to, per harness.
#
# Kiro's matcher syntax for preToolUse is not documented, so rather than assume
# it accepts alternation the Kiro adapter registers one hook per tool name.
# Claude Code documents the matcher as an unanchored regular expression, and
# Codex documents it as a regex applied to tool_name.
HOOK_MATCHERS: dict[str, list[str]] = {
    "kiro": ["shell", "read"],
    "claude_code": ["Bash|Read"],
    "codex": ["^(Bash|apply_patch)$"],
}


def load_manifest() -> dict[str, Any]:
    """Parse the neutral manifest."""
    return tomllib.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def load_prompt(manifest: dict[str, Any]) -> str:
    """Read the system prompt referenced by the manifest."""
    name = manifest["agent"]["prompt_file"]
    return (LAB_ROOT / "agent" / name).read_text(encoding="utf-8").rstrip() + "\n"


def tools_for(manifest: dict[str, Any], harness: str) -> list[str]:
    """Expand enabled capabilities into one harness's tool names."""
    caps = manifest["capabilities"]
    tools: list[str] = []
    for capability, mapping in CAPABILITY_TO_TOOLS.items():
        if caps.get(capability) is True:
            tools.extend(mapping[harness])
    return tools


def auto_approved_for(manifest: dict[str, Any], harness: str) -> list[str]:
    """Expand the auto-approve capability list into tool names."""
    approved: list[str] = []
    for capability in manifest["capabilities"].get("auto_approve", []):
        mapping = CAPABILITY_TO_TOOLS.get(capability)
        if mapping:
            approved.extend(mapping[harness])
    return approved


def denied_tools_for(manifest: dict[str, Any], harness: str) -> list[str]:
    """Tool names for capabilities explicitly turned off."""
    denied: list[str] = []
    for capability, mapping in CAPABILITY_TO_TOOLS.items():
        if manifest["capabilities"].get(capability) is False:
            denied.extend(mapping[harness])
    return denied


def anchor(pattern: str) -> str:
    """Anchor a command pattern at both ends.

    The manifest stores fragments so the same list can feed harnesses with
    different rule syntaxes. An unanchored allow rule is worse than no rule:
    `git status` unanchored also matches `evil && git status`.
    """
    return f"^{pattern}$"


def expand_lab(pattern: str) -> str:
    """Substitute path placeholders with the paths this agent actually uses.

    `{lab}` is this agent's own folder; `{core}` is the shared code extracted
    for use by more than one agent. Any other brace-delimited token is a typo
    in the manifest, and silently emitting it would produce an allow rule that
    can never match -- the exact failure this replaced. Fail loudly instead.
    """
    expanded = pattern.replace("{lab}", LAB_REL).replace("{core}", CORE_REL)
    leftover = re.search(r"\{[^}]*\}", expanded)
    if leftover:
        raise ValueError(
            f"unknown placeholder {leftover.group(0)!r} in manifest "
            f"pattern {pattern!r}; supported: '{{lab}}', '{{core}}'"
        )
    return expanded


# --------------------------------------------------------------------------
# Kiro CLI adapter
# --------------------------------------------------------------------------


def build_kiro(manifest: dict[str, Any], prompt: str) -> str:
    """Render the Kiro CLI agent configuration as JSON text."""
    agent = manifest["agent"]
    shell_cfg = manifest["shell"]
    hooks_cfg = manifest["hooks"]
    mcp_cfg = manifest["mcp"]

    config: dict[str, Any] = {
        "$generated": GENERATED_NOTE,
        "name": agent["name"],
        "description": agent["description"],
        "prompt": prompt,
        "model": manifest["model"]["kiro"],
        "tools": tools_for(manifest, "kiro"),
        "allowedTools": auto_approved_for(manifest, "kiro"),
        "toolsSettings": {
            "shell": {
                "allowedCommands": [
                    anchor(expand_lab(p))
                    for p in shell_cfg["auto_approve_commands"]
                ],
                "deniedCommands": list(shell_cfg["deny_commands"]),
                "autoAllowReadonly": True,
                "denyByDefault": False,
            },
            "write": {
                # The agent writes findings and fixes, not host configuration.
                "deniedPaths": [
                    "~/.aws/**",
                    "~/.ssh/**",
                    "~/.kube/**",
                    f"{LAB_REL}/.sec-scope",
                ]
            },
        },
        "resources": [
            f"file://{LAB_REL}/.sec-scope",
            f"file://{LAB_REL}/docs/setup-sec-tools.md",
        ],
        "hooks": {
            "agentSpawn": [{"command": f"sh {LAB_REL}/{hooks_cfg['spawn']}"}],
            "preToolUse": [
                {
                    "matcher": matcher,
                    "command": f"sh {LAB_REL}/{hooks_cfg['pre_tool_use']}",
                }
                for matcher in HOOK_MATCHERS["kiro"]
            ],
        },
        "mcpServers": {
            mcp_cfg["server_name"]: {
                "command": "python3",
                "args": [f"{LAB_REL}/{mcp_cfg['server_command']}"],
            }
        },
        "welcomeMessage": agent["welcome"],
    }
    return json.dumps(config, indent=2, ensure_ascii=False) + "\n"


# --------------------------------------------------------------------------
# Claude Code adapter
# --------------------------------------------------------------------------


def yaml_scalar(value: str) -> str:
    """Quote a string for YAML frontmatter."""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")
    return f'"{escaped}"'


def build_claude_agent(manifest: dict[str, Any], prompt: str) -> str:
    """Render the Claude Code subagent file: YAML frontmatter plus prompt body.

    Command-level Bash rules are deliberately not emitted. Claude Code's
    documented and testable enforcement point for shell commands is the
    PreToolUse hook, which receives the call as JSON and blocks on exit code 2.
    Encoding the same intent a second time as command patterns would add a
    control whose syntax could not be verified against a live install here, and
    two controls that disagree are worse than one that holds.
    """
    agent = manifest["agent"]
    hooks_cfg = manifest["hooks"]
    mcp_cfg = manifest["mcp"]

    tools = tools_for(manifest, "claude_code")
    denied = denied_tools_for(manifest, "claude_code")

    lines = [
        "---",
        f"# {GENERATED_NOTE}",
        f"name: {agent['name']}",
        f"description: {yaml_scalar(agent['description'])}",
        f"tools: {', '.join(tools)}",
        f"disallowedTools: {', '.join(denied)}" if denied else None,
        f"model: {manifest['model']['claude_code']}",
        "permissionMode: default",
        "hooks:",
        "  PreToolUse:",
        f'    - matcher: "{HOOK_MATCHERS["claude_code"][0]}"',
        "      hooks:",
        "        - type: command",
        f'          command: "sh {LAB_REL}/{hooks_cfg["pre_tool_use"]}"',
        "mcpServers:",
        f"  - {mcp_cfg['server_name']}:",
        "      type: stdio",
        "      command: python3",
        f'      args: ["{LAB_REL}/{mcp_cfg["server_command"]}"]',
        "---",
        "",
        prompt.rstrip(),
        "",
    ]
    return "\n".join(line for line in lines if line is not None)


def build_claude_settings(manifest: dict[str, Any]) -> str:
    """Render the project-wide Claude Code settings.

    Deliberately carries no hooks. `.claude/settings.json` applies to *every*
    session in the project, so putting the guard here forces general work
    (writing docs, unrelated code) through a security agent's policy — web
    search denied, no command chaining, no interpreters. The guard belongs to
    the agent, not the project.

    The subagent's own frontmatter already carries the same hooks, and those
    fire when the agent is spawned through the Agent tool or an @-mention.
    That is the on/off switch: spawn the agent, get the guard.

    Caveat: frontmatter hooks do not fire when the agent runs as the *main*
    session (`claude --agent generic-sec-agent`). For that path the operator
    copies the fragment written to `.claude/settings.local.json.example`.
    """
    settings: dict[str, Any] = {
        "$generated": GENERATED_NOTE,
        "$note": (
            "Agent-neutral settings only. The security guard lives in "
            ".claude/agents/generic-sec-agent.md frontmatter and fires when "
            "the agent is spawned. To put a whole main session under the "
            "guard, copy .claude/settings.local.json.example to "
            ".claude/settings.local.json; delete it to turn the guard off."
        ),
        "permissions": {
            "allow": auto_approved_for(manifest, "claude_code"),
        },
    }
    return json.dumps(settings, indent=2, ensure_ascii=False) + "\n"


def build_claude_session_guard(manifest: dict[str, Any]) -> str:
    """Render the opt-in session-wide guard for Claude Code.

    Written as `.claude/settings.local.json.example`. The operator copies it to
    `.claude/settings.local.json` (gitignored) to run an entire main session
    under the guard, and deletes that copy to go back to unrestricted work.
    A file is the switch because a human has to move it — the agent cannot
    silently disable its own enforcement, since `rm` is blocked by the guard
    it would be removing.
    """
    hooks_cfg = manifest["hooks"]
    guard = f"sh {LAB_REL}/{hooks_cfg['pre_tool_use']}"

    settings: dict[str, Any] = {
        "$generated": GENERATED_NOTE,
        "$note": (
            "Copy to .claude/settings.local.json to put every session in this "
            "project under the security guard. Delete that copy to turn it "
            "off. Not needed when the agent is spawned as a subagent — its "
            "frontmatter carries the same hooks."
        ),
        "permissions": {
            "deny": denied_tools_for(manifest, "claude_code"),
        },
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": HOOK_MATCHERS["claude_code"][0],
                    "hooks": [{"type": "command", "command": guard}],
                }
            ],
            "SessionStart": [
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": f"sh {LAB_REL}/{hooks_cfg['spawn']}",
                        }
                    ]
                }
            ],
        },
    }
    return json.dumps(settings, indent=2, ensure_ascii=False) + "\n"


# --------------------------------------------------------------------------
# Codex CLI adapter
# --------------------------------------------------------------------------


def build_codex_config(manifest: dict[str, Any]) -> str:
    """Render `.codex/config.toml`.

    Codex expresses capability differently from the other two. There is no list
    of allowed tools: filesystem and network reach come from `sandbox_mode`,
    pauses come from `approval_policy`, and individual tools are toggled through
    `[features]` and the top-level `web_search` key. So the neutral capability
    flags are translated into that vocabulary rather than into a tool list.

    That difference is worth noticing rather than papering over: `sandbox_mode`
    is an operating-system sandbox, which is a stronger control than any
    denylist a hook can implement. Codex therefore gets a layer the other two
    harnesses do not have, and the hook is defence in depth on top of it.

    Hook commands resolve from the git root because Codex documents that a
    session's working directory may be a subdirectory of the repository, which
    would break a relative path.
    """
    agent = manifest["agent"]
    hooks_cfg = manifest["hooks"]
    mcp_cfg = manifest["mcp"]
    caps = manifest["capabilities"]

    root = '$(git rev-parse --show-toplevel)'
    guard = f'sh "{root}/{LAB_REL}/{hooks_cfg["pre_tool_use"]}"'
    spawn = f'sh "{root}/{LAB_REL}/{hooks_cfg["spawn"]}"'

    # write_files decides whether the workspace is writable at all.
    sandbox = "workspace-write" if caps.get("write_files") else "read-only"
    # fetch_web is off, so the hosted web search tool is turned off with it.
    # Note this one is not hookable: Codex documents hosted tools as outside the
    # local function-tool hook path, so disabling it is the only control.
    web_search = "live" if caps.get("fetch_web") else "disabled"

    lines = [
        f"# {GENERATED_NOTE}",
        "",
        f'model = "{manifest["model"]["codex"]}"',
        "",
        "# on-request keeps a human in the loop for anything the sandbox would",
        "# otherwise escalate. Active-scan tools are refused by the hook, but the",
        "# approval prompt is the layer that catches whatever the hook misses.",
        'approval_policy = "on-request"',
        "",
        "# An OS-level sandbox, which is a stronger control than the hook's",
        "# denylist. Codex is the only one of the three harnesses that offers it.",
        f'sandbox_mode = "{sandbox}"',
        "",
        "# Capability fetch_web is false in the neutral manifest. Hosted tools",
        "# such as web search do not go through the local hook path, so turning",
        "# the tool off is the only way to enforce that.",
        f'web_search = "{web_search}"',
        "",
        "[features]",
        "hooks = true",
        "",
        f"[mcp_servers.{mcp_cfg['server_name']}]",
        'command = "python3"',
        f'args = ["{LAB_REL}/{mcp_cfg["server_command"]}"]',
        "",
        "# Report scanner availability when the session starts, so a missing",
        "# tool is never mistaken for a clean scan.",
        "[[hooks.SessionStart]]",
        'matcher = "startup|resume"',
        "",
        "[[hooks.SessionStart.hooks]]",
        'type = "command"',
        f"command = '{spawn}'",
        "timeout = 30",
        'statusMessage = "Checking scanner availability"',
        "",
        "# The security guard. Codex blocks on exit code 2 with the reason on",
        "# stderr, which is the same contract Claude Code documents, so the same",
        "# script serves both unchanged.",
        "#",
        "# apply_patch is matched alongside Bash because Codex routes file edits",
        "# through it, and an edit is how a credential file would be written.",
        "[[hooks.PreToolUse]]",
        f'matcher = "{HOOK_MATCHERS["codex"][0]}"',
        "",
        "[[hooks.PreToolUse.hooks]]",
        'type = "command"',
        f"command = '{guard}'",
        "timeout = 30",
        'statusMessage = "Checking command against security policy"',
        "",
        "# Codex requires a human to review and trust a non-managed command hook",
        "# before it runs. Run /hooks in the CLI after generating this file, or",
        f"# the guard is configured but inert. Agent: {agent['name']}",
        "",
    ]
    return "\n".join(lines)


def build_codex_prompt(manifest: dict[str, Any], prompt: str) -> str:
    """Render the Codex prompt file.

    Codex loads project instructions from AGENTS.md, which applies to every
    session in the repository. Binding this prompt there would turn every Codex
    session in the repo into a security agent, so the prompt is written to its
    own file instead and pointed at explicitly.

    Codex does have named subagents, but their file format was not verified
    against a live install here, so this adapter does not generate one. See the
    porting guide for what to check before wiring it up.
    """
    agent = manifest["agent"]
    return "\n".join(
        [
            f"<!-- {GENERATED_NOTE} -->",
            "",
            f"# {agent['name']}",
            "",
            agent["description"],
            "",
            "Load this file as the operating instructions for a security review",
            "session. From the repository root:",
            "",
            "```",
            f'codex "Follow .codex/{agent["name"]}.md and review this project"',
            "```",
            "",
            "Controls live in `.codex/config.toml`: the PreToolUse guard, the",
            "sandbox mode, and the MCP scanner server. Run `/hooks` once to trust",
            "the guard, otherwise it is configured but does not run.",
            "",
            "---",
            "",
            prompt.rstrip(),
            "",
        ]
    )


# --------------------------------------------------------------------------
# Driver
# --------------------------------------------------------------------------


def _generated_target(primary: Path, fragment: Path) -> Path:
    """Pick where to write a shared config file.

    A settings file may already exist and belong to the user. Overwriting it
    would destroy configuration a generator has no business touching, so the
    output goes to a fragment beside it instead and the operator merges by hand.
    A file this script wrote before carries the generated marker and is safe to
    replace.
    """
    if not primary.exists():
        return primary
    if GENERATED_MARKER in primary.read_text(encoding="utf-8"):
        return primary
    return fragment


def targets(manifest: dict[str, Any], prompt: str) -> list[tuple[Path, str]]:
    """Return (path, content) for every generated adapter file."""
    return [
        (KIRO_OUT, build_kiro(manifest, prompt)),
        (CLAUDE_AGENT_OUT, build_claude_agent(manifest, prompt)),
        (
            _generated_target(CLAUDE_SETTINGS_OUT, CLAUDE_SETTINGS_FRAGMENT),
            build_claude_settings(manifest),
        ),
        (CLAUDE_SESSION_GUARD_OUT, build_claude_session_guard(manifest)),
        (
            _generated_target(CODEX_CONFIG_OUT, CODEX_CONFIG_FRAGMENT),
            build_codex_config(manifest),
        ),
        (CODEX_PROMPT_OUT, build_codex_prompt(manifest, prompt)),
    ]


def write_all(manifest: dict[str, Any], prompt: str) -> int:
    """Write every adapter. Return an exit code."""
    for path, content in targets(manifest, prompt):
        path.parent.mkdir(parents=True, exist_ok=True)
        existed = path.exists()
        path.write_text(content, encoding="utf-8")
        verb = "updated" if existed else "created"
        print(f"  {verb}: {path.relative_to(WORKSPACE_ROOT)}")

    for primary, fragment in (
        (CLAUDE_SETTINGS_OUT, CLAUDE_SETTINGS_FRAGMENT),
        (CODEX_CONFIG_OUT, CODEX_CONFIG_FRAGMENT),
    ):
        if fragment.exists():
            print()
            print(
                f"note: {primary.relative_to(WORKSPACE_ROOT)} already exists and "
                "was not written by this script, so the generated version was "
                f"left at {fragment.relative_to(WORKSPACE_ROOT)}.\n"
                "      Merge it by hand rather than letting a generator "
                "overwrite settings you wrote."
            )
    return 0


def check_all(manifest: dict[str, Any], prompt: str) -> int:
    """Compare generated output with what is on disk. Return an exit code."""
    drifted: list[str] = []
    for path, content in targets(manifest, prompt):
        rel = path.relative_to(WORKSPACE_ROOT)
        if not path.exists():
            drifted.append(f"{rel}: missing")
        elif path.read_text(encoding="utf-8") != content:
            drifted.append(f"{rel}: differs from generated output")

    if drifted:
        print("adapter drift detected:", file=sys.stderr)
        for item in drifted:
            print(f"  - {item}", file=sys.stderr)
        print(
            "\nAn adapter was edited directly, or the neutral source changed "
            "without a rebuild.\nRun: python3 "
            f"{LAB_REL}/adapters/build.py",
            file=sys.stderr,
        )
        return 1

    print("adapters are in sync with agent/SYSTEM_PROMPT.md and agent/manifest.toml")
    return 0


def main() -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(
        description="Generate harness adapters from the neutral agent source."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify the adapters match the source; exit 1 on drift",
    )
    parser.add_argument(
        "--print",
        dest="print_target",
        choices=[
            "kiro",
            "claude-agent",
            "claude-settings",
            "codex-config",
            "codex-prompt",
        ],
        help="dump one adapter to stdout without writing anything",
    )
    args = parser.parse_args()

    manifest = load_manifest()
    prompt = load_prompt(manifest)

    printers = {
        "kiro": lambda: build_kiro(manifest, prompt),
        "claude-agent": lambda: build_claude_agent(manifest, prompt),
        "claude-settings": lambda: build_claude_settings(manifest),
        "codex-config": lambda: build_codex_config(manifest),
        "codex-prompt": lambda: build_codex_prompt(manifest, prompt),
    }
    if args.print_target:
        print(printers[args.print_target](), end="")
        return 0

    if args.check:
        return check_all(manifest, prompt)

    print("building adapters from the neutral source")
    return write_all(manifest, prompt)


if __name__ == "__main__":
    raise SystemExit(main())
