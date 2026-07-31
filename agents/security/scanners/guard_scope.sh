#!/bin/sh
# guard_scope.sh - PreToolUse hook. Decides whether a pending shell command
# may run.
#
# Contract: the harness pipes the pending tool call to us as JSON on stdin.
#   exit 0 -> allow
#   exit 2 -> block; stderr is fed back to the model as the reason
#
# Why a hook instead of a regex allow-list in the agent config:
# an allow-list entry like "nuclei .*" also matches "nuclei -u localhost;
# rm -rf ~", because the harness matches the raw command string. A hook
# receives the command as data, so it can tokenise it, pull the actual scan
# target out, and compare that target to an authorisation file. That check
# is not expressible as a regex over the command line.
#
# POSIX sh on purpose: macOS ships bash 3.2 (2007), so bash 4 features such
# as associative arrays are unavailable. Sticking to POSIX also means this
# runs unchanged under dash/ash in a CI container.

set -u

# Resolve paths from the script's own location, never from the caller's cwd.
# A hook is invoked by the harness, whose working directory is not ours to
# assume.
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
LAB_ROOT=$(cd "$SCRIPT_DIR/.." && pwd)
SCOPE_FILE="$LAB_ROOT/.sec-scope"

# The scope rule is shared with run_dast.sh; see _scope_lib.sh for why both
# enforcement points exist.
# shellcheck source=_scope_lib.sh
. "$SCRIPT_DIR/_scope_lib.sh"

block() {
    echo "BLOCKED by guard_scope.sh: $1" >&2
    if [ $# -gt 1 ]; then
        echo "$2" >&2
    fi
    exit 2
}

# ---------------------------------------------------------------------------
# 1. Parse the harness payload
# ---------------------------------------------------------------------------

if ! command -v jq >/dev/null 2>&1; then
    block "jq is not installed, so the pending command cannot be parsed." \
          "Install jq (see docs/setup-sec-tools.md). Failing closed: an
unparsed command is an unverified command."
fi

INPUT=$(cat)

if [ -z "$INPUT" ]; then
    block "empty hook payload; nothing to validate." \
          "Failing closed. If your harness does not send JSON on stdin to
PreToolUse hooks, this guard cannot protect you and must be replaced."
fi

# Harnesses disagree on the payload shape. Claude Code documents
# .tool_input.command; Kiro CLI's preToolUse payload schema is not documented,
# so try the plausible spellings rather than guessing one.
CMD=$(printf '%s' "$INPUT" | jq -r '
    .tool_input.command
    // .toolInput.command
    // .input.command
    // .arguments.command
    // .parameters.command
    // .command
    // empty
' 2>/dev/null || true)

TOOL=$(printf '%s' "$INPUT" | jq -r '
    .tool_name // .toolName // .tool // .name // empty
' 2>/dev/null || true)

# Credential material. A security agent proves a secret is committed by
# reporting its location; it never needs the value. Blocking the read means a
# leaked value cannot reach the model context or a transcript.
#
# Directory names are matched with or without a trailing slash. Requiring the
# slash was a real hole: `cp -r ~/.aws /tmp/exfil` names the directory with no
# slash and copies every credential in it.
#
# The `.env` alternatives are enumerated rather than left open so that a path
# like ./environments/staging does not match, while .env, .env.local, .envrc
# and .env/ all do.
CREDENTIAL_RE='(\.aws([[:space:]]|/|$)|\.ssh([[:space:]]|/|$)|\.gnupg|\.kube|\.netrc|\.docker|\.npmrc|\.pypirc|\.pgpass|\.git-credentials|\.htpasswd|\.env([[:space:]]|$|\.|/|rc|_)|id_rsa|id_ed25519|id_ecdsa|id_dsa|\.pem([[:space:]]|$)|\.key([[:space:]]|$)|\.p12([[:space:]]|$)|\.pfx([[:space:]]|$)|\.jks([[:space:]]|$)|credentials([[:space:]]|$|\.)|/Library/Keychains|security[[:space:]]+(find-generic-password|find-internet-password|dump-keychain))'

if [ -z "$CMD" ]; then
    # Not a shell call. It may still be a file-reading tool, and those need
    # checking too.
    #
    # This is not hypothetical. Kiro exposes `read` and Claude Code exposes
    # `Read` as tools separate from the shell, and both are auto-approved in
    # the generated adapters. A hook whose matcher is only the shell tool never
    # sees them, so `Read ~/.aws/credentials` would sail past a guard that only
    # inspects commands. Codex happens not to have this gap because it reads
    # files through the shell, which is what made the gap visible at all.
    PATHARG=$(printf '%s' "$INPUT" | jq -r '
        .tool_input.file_path
        // .tool_input.path
        // .tool_input.abs_path
        // .tool_input.filePath
        // .toolInput.path
        // .toolInput.file_path
        // .input.path
        // .arguments.path
        // .parameters.path
        // .path
        // empty
    ' 2>/dev/null || true)

    if [ -n "$PATHARG" ]; then
        if printf '%s' "$PATHARG" | grep -qE "$CREDENTIAL_RE"; then
            block "tool '${TOOL:-<unknown>}' targets credential material." \
                  "Rejected path: ${PATHARG}
Report the location of a committed secret, never read its value. This check
covers file tools as well as shell commands, because a separate read tool
would otherwise bypass the command inspection entirely."
        fi
        # A path that is not credential material: nothing else here applies.
        exit 0
    fi

    # No command and no path. Either this is a tool with nothing to check, or
    # the payload shape is one we do not recognise.
    case "$TOOL" in
        ""|*[Ss]hell*|*[Bb]ash*|*execute*|*Execute*|*[Cc]md*|*[Pp]ower[Ss]hell*)
            KEYS=$(printf '%s' "$INPUT" | jq -r 'try (paths|join("."))' 2>/dev/null \
                   | head -20 | tr '\n' ' ')
            block "could not locate the command in the hook payload for tool '${TOOL:-<unknown>}'." \
                  "Payload paths seen: ${KEYS:-<unparseable>}
Add the correct JSON path to guard_scope.sh. Failing closed on purpose:
allowing an unread command would make this guard decorative."
            ;;
        *)
            # A tool with no command and no path (search, plan, ...).
            exit 0
            ;;
    esac
fi

# ---------------------------------------------------------------------------
# 2. Structural bans - these remove the ways a single approved command can
#    turn into several commands.
# ---------------------------------------------------------------------------

# Literal newline inside the command means multiple statements.
if [ "$(printf '%s' "$CMD" | wc -l | tr -d ' ')" != "0" ]; then
    block "the command spans multiple lines." \
          "Run one command per tool call so each can be checked on its own."
fi

if printf '%s' "$CMD" | grep -q '[;&|`]'; then
    block "command chaining or substitution character (; & | \`) present." \
          "Rejected: ${CMD}
Chaining lets an approved prefix carry an unapproved payload. Issue the
commands separately so each is validated."
fi

# Any '$' is refused, which covers $(...) and ${...} and bare $VAR alike.
#
# ${IFS} is the reason this is a blanket ban rather than a check for '$('.
# IFS expands to whitespace when the shell runs the command, so
# `cat${IFS}/etc/shadow` is one token to this guard and two arguments to the
# shell. Any check that reads the pre-expansion string is looking at different
# text from the one that will execute, so the only sound rule is to refuse
# text that expands at all.
if printf '%s' "$CMD" | grep -q '\$'; then
    block "variable or command expansion (\$) present." \
          "Rejected: ${CMD}
The command as written is not the command that would run. Pass literal values."
fi

# Brace expansion produces multiple words from one token, with the same
# read-versus-execute mismatch as above.
if printf '%s' "$CMD" | grep -q '[{}]'; then
    block "brace expansion present." "Rejected: ${CMD}"
fi

if printf '%s' "$CMD" | grep -q '[<>]'; then
    block "shell redirection (< >) present." \
          "Rejected: ${CMD}
The scanner wrappers write their own output files; redirection is not needed
and can overwrite arbitrary paths."
fi

# ---------------------------------------------------------------------------
# 3. Category bans
# ---------------------------------------------------------------------------

# Is this one of our own wrapper entry points?
#
# The wrappers are documented as `sh scanners/run_sast.sh` and
# `python3 gate/gate.py`, so the interpreter ban below would make the agent
# unable to scan anything at all. Rather than weaken the ban, exactly these
# forms are exempt from it. Every other check still applies to them, and the
# form is pinned tightly enough that the interpreter cannot be pointed at some
# other script.
is_own_wrapper() {
    _c="$1"

    if printf '%s' "$_c" | grep -qE \
        '^(sh|/bin/sh)[[:space:]]+([A-Za-z0-9._-]+/)*scanners/(run_sast|run_sca|run_dast|preflight)\.sh([[:space:]]+[A-Za-z0-9._:/@%?=+~-]+)*$'
    then
        _args=$(printf '%s' "$_c" | sed -e 's/^[^[:space:]]*[[:space:]]*//' \
                                        -e 's/^[^[:space:]]*[[:space:]]*//')
    elif printf '%s' "$_c" | grep -qE \
        '^python3?[[:space:]]+([A-Za-z0-9._-]+/)*gate/(gate|merge_sarif)\.py([[:space:]]+[A-Za-z0-9._:/@%?=+~-]+)*$'
    then
        _args=$(printf '%s' "$_c" | sed -e 's/^[^[:space:]]*[[:space:]]*//' \
                                        -e 's/^[^[:space:]]*[[:space:]]*//')
    else
        return 1
    fi

    # A second script among the arguments would mean the interpreter is being
    # aimed somewhere else after all.
    if printf '%s' "$_args" | grep -qE '\.(sh|py|pl|rb|php|js|lua)([[:space:]]|$)'; then
        return 1
    fi
    return 0
}

# Interpreters, indirection and command-prefix wrappers. Each of these executes
# text that this guard cannot inspect: the banned-binary checks below read the
# command line, and an interpreter's script argument is opaque to them.
#
# This list is not a sandbox and does not claim to be exhaustive. It closes the
# well-known escapes; see the residual-risk note in the lab README.
INDIRECTION='eval|exec|command|builtin|source|sh|bash|dash|zsh|ksh|csh|tcsh|fish|env|xargs|perl|perl5|python|python2|python3|ruby|node|deno|bun|php|lua|awk|gawk|mawk|osascript|make|npm|npx|yarn|pnpm|nohup|setsid|timeout|stdbuf|watch|script|expect'

if ! is_own_wrapper "$CMD"; then
    if printf '%s' "$CMD" | grep -qE "(^|[[:space:]/])($INDIRECTION)([[:space:]]|$)"; then
        block "interpreter or command indirection." \
              "Rejected: ${CMD}
This would execute text the guard cannot read. Use the scanner wrappers
(sh scanners/run_*.sh, python3 gate/*.py), which are the only interpreter
invocations allowed."
    fi
    # The dot command sources a file, same problem as `source`.
    if printf '%s' "$CMD" | grep -qE '(^|[[:space:]])\.[[:space:]]'; then
        block "dot command sources a file." "Rejected: ${CMD}"
    fi
fi

# find's action flags run arbitrary programs on every match.
if printf '%s' "$CMD" | grep -qE '(^|[[:space:]/])find([[:space:]]|$)' && \
   printf '%s' "$CMD" | grep -qE '[[:space:]](-exec|-execdir|-ok|-okdir|-delete)([[:space:]]|$)'; then
    block "find with an action flag executes arbitrary programs." \
          "Rejected: ${CMD}"
fi

if printf '%s' "$CMD" | grep -qE '(^|[[:space:]/])(sudo|su|doas|pkexec)([[:space:]]|$)'; then
    block "privilege escalation attempt." "Rejected: ${CMD}"
fi

if printf '%s' "$CMD" | grep -qE '(^|[[:space:]/])(rm|rmdir|dd|mkfs|mkfs\.[a-z0-9]+|shred|truncate|chown|unlink)([[:space:]]|$)'; then
    block "destructive filesystem command." \
          "Rejected: ${CMD}
Security analysis is read-only with respect to the host. If a file genuinely
must be removed, a human should do it."
fi

if printf '%s' "$CMD" | grep -qE 'chmod[[:space:]]+(-[A-Za-z]+[[:space:]]+)*(777|a\+rwx|o\+w)'; then
    block "world-writable permission change." "Rejected: ${CMD}"
fi

if printf '%s' "$CMD" | grep -qE 'git[[:space:]]+(reset[[:space:]]+--hard|clean[[:space:]]+-[a-z]*f|push[[:space:]]+.*--force|branch[[:space:]]+-D)'; then
    block "destructive git operation." "Rejected: ${CMD}"
fi

# Same rule as the file-tool check above, from the same variable so the two
# paths cannot drift apart.
if printf '%s' "$CMD" | grep -qE "$CREDENTIAL_RE"; then
    block "path looks like credential material." \
          "Rejected: ${CMD}
Report the location of a committed secret, never its value."
fi

# Outbound network utilities. Findings must not leave the host through the
# agent. DAST tools are handled separately below.
if printf '%s' "$CMD" | grep -qE '(^|[[:space:]/])(curl|wget|nc|ncat|socat|telnet|ssh|scp|sftp|rsync|ftp)([[:space:]]|$)'; then
    block "outbound network utility." \
          "Rejected: ${CMD}
This would give scan output a path off the host. Use the scanner wrappers,
which write to the local report directory."
fi

# ---------------------------------------------------------------------------
# 4. DAST scope enforcement
# ---------------------------------------------------------------------------

# run_dast.sh is listed alongside the scanners so the scope decision happens at
# approval time, in front of the human, rather than only inside the wrapper
# after the command was approved. Both still enforce it.
DAST_TOOLS='nuclei|nmap|masscan|zap|zap\.sh|zaproxy|sqlmap|nikto|wpscan|ffuf|gobuster|dirb|dirbuster|hydra|medusa|arachni|wapiti|whatweb|amass|subfinder|httpx|run_dast\.sh'

if ! printf '%s' "$CMD" | grep -qE "(^|[[:space:]/])($DAST_TOOLS)([[:space:]]|$)"; then
    # Not an active-scan command and nothing above objected.
    exit 0
fi

if [ ! -f "$SCOPE_FILE" ]; then
    block "active scan requested but the authorisation file is missing." \
          "Expected: ${SCOPE_FILE}
Without it there is no record of what you are permitted to test."
fi

# A target list read from a file cannot be validated at this point: the file's
# contents can change between this check and the scan. Refuse rather than
# pretend to have checked.
if printf '%s' "$CMD" | grep -qE '(^|[[:space:]])(-l|-iL|-list|--list|--target-file|-tL)([[:space:]]|=)'; then
    block "active scan uses a target list file." \
          "Rejected: ${CMD}
The list contents are not verifiable at approval time. Pass targets
explicitly, one scan at a time."
fi

# Load the authorisation list. The rule itself lives in _scope_lib.sh so that
# the MCP path (run_dast.sh) enforces exactly the same thing.
SCOPE_HOSTS=$(load_scope "$SCOPE_FILE") || \
    block "the authorisation file is missing or lists no targets." \
          "File: ${SCOPE_FILE}"

# Word-split the command without glob expansion. Without `set -f`, a token
# such as *.txt would expand against the current directory and the loop would
# inspect filenames instead of the argument the model actually wrote.
set -f
# shellcheck disable=SC2086
set -- $CMD
set +f

TARGETS=""
PREV=""
SEEN_TOOL=0

for TOKEN in "$@"; do
    # The scanner binary itself is not a target.
    if printf '%s' "$TOKEN" | grep -qE "(^|/)($DAST_TOOLS)$"; then
        SEEN_TOOL=1
        PREV="$TOKEN"
        continue
    fi

    RAW="$TOKEN"
    TAKE=0

    # --flag=value form.
    case "$TOKEN" in
        -u=*|-url=*|--url=*|-target=*|--target=*|--targets=*|-host=*|--host=*|-d=*|--domain=*)
            RAW=$(printf '%s' "$TOKEN" | sed 's/^[^=]*=//')
            TAKE=1
            ;;
    esac

    # Value following a flag that introduces a target. Taken verbatim, so a
    # bare name like "localhost" is validated even though it is not host-shaped.
    if [ "$TAKE" -eq 0 ]; then
        case "$PREV" in
            -u|-url|--url|-target|--target|--targets|-host|--host|-d|--domain)
                TAKE=1
                ;;
        esac
    fi

    # Anything carrying a scheme is a target wherever it appears.
    if [ "$TAKE" -eq 0 ]; then
        case "$TOKEN" in
            http://*|https://*|ws://*|wss://*) TAKE=1 ;;
        esac
    fi

    # Host-shaped operand anywhere after the tool name. This is what catches
    # `nmap 203.0.113.10` and `nuclei -H internal.corp` alike.
    if [ "$TAKE" -eq 0 ] && [ "$SEEN_TOOL" -eq 1 ]; then
        case "$TOKEN" in
            -*) : ;;
            *) looks_like_host "$(printf '%s' "$TOKEN" | tr 'A-Z' 'a-z')" && TAKE=1 ;;
        esac
    fi

    if [ "$TAKE" -eq 1 ]; then
        H=$(normalise_host "$RAW")
        [ -n "$H" ] && TARGETS="$TARGETS $H"
    fi
    PREV="$TOKEN"
done

TARGETS=$(printf '%s' "$TARGETS" | tr ' ' '\n' | grep -v '^$' | sort -u)

if [ -z "$TARGETS" ]; then
    block "active scan with no target this guard could identify." \
          "Rejected: ${CMD}
Refusing to approve a scan whose target is unknown. State the target
explicitly, for example -u http://localhost:8080 or -target localhost."
fi

OUT_OF_SCOPE=""
for H in $TARGETS; do
    if ! in_scope "$H" "$SCOPE_HOSTS"; then
        OUT_OF_SCOPE="$OUT_OF_SCOPE $H"
    fi
done

if [ -n "$OUT_OF_SCOPE" ]; then
    block "active scan target out of authorised scope:${OUT_OF_SCOPE}" \
          "Rejected: ${CMD}
Authorised (${SCOPE_FILE}):
$(printf '%s' "$SCOPE_HOSTS" | sed 's/^/  - /')
Scanning a host you are not authorised to test is unlawful in most
jurisdictions. A human must add the host to .sec-scope after confirming
ownership. Do not retry."
fi

exit 0
