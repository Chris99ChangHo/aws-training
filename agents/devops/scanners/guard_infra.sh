#!/bin/sh
# guard_infra.sh - PreToolUse hook. Decides whether a pending command may run.
#
# Contract (same as the security agent's guard, so callers learn one contract):
#   exit 0 -> allow
#   exit 2 -> block; stderr is fed back to the model as the reason
#
# Why a hook and not just the allow-list in the agent config:
# a regex over the raw command string cannot tell `terraform plan` from
# `terraform plan -destroy -out=x && terraform apply x`, and it cannot tell a
# read-only `aws ec2 describe-instances` from `aws ec2 terminate-instances`
# hidden behind extra flags. A hook receives the command as data, so it can
# tokenise it and inspect the verb that actually follows the tool name.
#
# This guard's subject differs from the security agent's. That one protects
# against reading secrets and scanning hosts nobody authorised. This one
# protects against changing infrastructure: the failure mode of a DevOps agent
# is not a leaked value, it is a deleted cluster. Reads are encouraged, writes
# to real infrastructure are refused outright.
#
# POSIX sh on purpose: macOS ships bash 3.2 (2007), and this must also run
# unchanged under dash/ash in a CI container.
#
# NOTE: sections 1-3 duplicate the generic half of the security agent's
# guard_scope.sh. Extracting them into agents/core is tracked as a seam in
# agents/README.md; it is deferred because that file carries 100 behavioural
# tests and a refactor of it is not worth bundling with a new agent.

set -u

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
LAB_ROOT=$(cd "$SCRIPT_DIR/.." && pwd)

block() {
    echo "BLOCKED by guard_infra.sh: $1" >&2
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
          "Install jq (see docs/setup-devops-tools.md). Failing closed: an
unparsed command is an unverified command."
fi

INPUT=$(cat)

if [ -z "$INPUT" ]; then
    block "empty hook payload; nothing to validate." \
          "Failing closed. If your harness does not send JSON on stdin to
PreToolUse hooks, this guard cannot protect you and must be replaced."
fi

# Harnesses disagree on the payload shape. Claude Code documents
# .tool_input.command; Kiro CLI's preToolUse schema is not documented, so try
# the plausible spellings rather than guessing one.
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

# ---------------------------------------------------------------------------
# 2. Credential material (applies to file tools as well as commands)
# ---------------------------------------------------------------------------

# A DevOps agent reads infrastructure definitions, never the credentials that
# deploy them. Directory names match with or without a trailing slash, because
# `cp -r ~/.aws /tmp/x` names the directory with no slash.
CREDENTIAL_RE='(\.aws([[:space:]]|/|$)|\.ssh([[:space:]]|/|$)|\.gnupg|\.kube([[:space:]]|/|$)|\.netrc|\.docker([[:space:]]|/|$)|\.npmrc|\.pypirc|\.pgpass|\.git-credentials|\.terraformrc|terraform\.tfstate|\.tfvars([[:space:]]|$)|\.env([[:space:]]|$|\.|/|rc|_)|id_rsa|id_ed25519|id_ecdsa|id_dsa|\.pem([[:space:]]|$)|\.key([[:space:]]|$)|kubeconfig|credentials([[:space:]]|$|\.))'

if [ -z "$CMD" ]; then
    # Not a shell call. It may still be a file-reading tool, and those bypass
    # command inspection entirely if the guard ignores them.
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
            block "tool '${TOOL:-<unknown>}' targets credential or state material." \
                  "Rejected path: ${PATHARG}
Terraform state and kubeconfig contain live secrets. Read the definition, not
the state. This check covers file tools as well as shell commands."
        fi
    fi
    exit 0
fi

if printf '%s' "$CMD" | grep -qE "$CREDENTIAL_RE"; then
    block "command touches credential or state material." \
          "Rejected command: ${CMD}
Terraform state files and kubeconfig hold live secrets."
fi

# ---------------------------------------------------------------------------
# 3. Structural bans
# ---------------------------------------------------------------------------

# Chaining and substitution hide a second command behind an approved first one.
# Blocking the structure is cheaper and more reliable than trying to inspect
# every branch of a compound command.
case $CMD in
    *';'*|*'&'*|*'|'*|*'`'*|*'$('*)
        block "command chaining, backgrounding or substitution is not allowed." \
              "Rejected command: ${CMD}
Run one command per call. An approved command followed by ';' is how an
allow-list gets bypassed."
        ;;
    *'>'*|*'<'*)
        block "shell redirection is not allowed." \
              "Rejected command: ${CMD}
The wrappers write their own report files. Redirection would let an arbitrary
path be overwritten."
        ;;
esac

case $CMD in
    *sudo*|*' su '*|*doas*)
        block "privilege escalation is not allowed." "Rejected command: ${CMD}"
        ;;
esac

# ---------------------------------------------------------------------------
# 4. Infrastructure mutation -- the reason this guard exists
# ---------------------------------------------------------------------------

# Word-split the command without glob expansion. Without `set -f`, a token such
# as *.tf would expand against the current directory and the loop below would
# inspect filenames instead of the argument the model actually wrote.
set -f
# shellcheck disable=SC2086
set -- $CMD
set +f

TOOL_BIN=""
VERB=""
for TOKEN in "$@"; do
    case $TOKEN in
        -*) continue ;;          # flags are not the verb
    esac
    if [ -z "$TOOL_BIN" ]; then
        TOOL_BIN=$(basename "$TOKEN")
        continue
    fi
    if [ -z "$VERB" ]; then
        VERB="$TOKEN"
        break
    fi
done

refuse_mutation() {
    block "'$TOOL_BIN $VERB' changes infrastructure state." \
          "Rejected command: ${CMD}
This agent plans and inspects; it does not apply. Produce the plan, report what
would change, and let a human run the mutation. Allowed verbs for $TOOL_BIN:
$1"
}

case $TOOL_BIN in
    terraform|terragrunt|tofu)
        case $VERB in
            validate|plan|show|providers|version|fmt|graph|output|init) ;;
            *) refuse_mutation "validate, plan, show, providers, fmt, graph, output, init" ;;
        esac
        # `plan -destroy` writes nothing but produces a destruction plan that a
        # later apply consumes. Refusing it keeps the destructive intent from
        # being laundered through an approved verb.
        case $CMD in
            *-destroy*) refuse_mutation "plan without -destroy" ;;
        esac
        ;;
    kubectl|oc)
        case $VERB in
            get|describe|logs|explain|api-resources|api-versions|version|top|diff|config) ;;
            *) refuse_mutation "get, describe, logs, explain, diff, top, version" ;;
        esac
        ;;
    helm)
        case $VERB in
            template|lint|show|list|get|version|dependency) ;;
            *) refuse_mutation "template, lint, show, list, get, version" ;;
        esac
        ;;
    docker|podman|nerdctl)
        case $VERB in
            build|images|ps|inspect|version|history|manifest) ;;
            *) refuse_mutation "build, images, ps, inspect, history, version" ;;
        esac
        ;;
    aws|gcloud|az)
        # Cloud CLIs put the verb in the third position (aws s3 ls), and the
        # read-only verbs are a small enumerable set while the mutating ones are
        # open-ended. Allow-list rather than deny-list.
        THIRD=""
        _seen=0
        for TOKEN in "$@"; do
            case $TOKEN in
                -*) continue ;;
            esac
            _seen=$((_seen + 1))
            if [ "$_seen" -eq 3 ]; then
                THIRD="$TOKEN"
                break
            fi
        done
        case $THIRD in
            ""|describe*|get*|list*|ls|show*|head*|search*|validate*|version|help|estimate*) ;;
            *)
                VERB="$VERB $THIRD"
                refuse_mutation "describe-*, get-*, list-*, ls, show, head, validate"
                ;;
        esac
        ;;
esac

exit 0
