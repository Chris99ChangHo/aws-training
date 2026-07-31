#!/bin/sh
# _scope_lib.sh - the authorisation-scope rule, in one place.
#
# Sourced by both enforcement points:
#   guard_scope.sh  guards the shell path (PreToolUse hook)
#   run_dast.sh     guards the MCP path
#
# Both are needed. An MCP tool call is not a shell command, so the PreToolUse
# hook never sees it; a scope check that lived only in the hook would be
# bypassed the moment the agent used the MCP server instead of the shell.
# Keeping the rule in one file is what stops the two paths from drifting apart
# and disagreeing about what is in scope.
#
# POSIX sh. No side effects on source: defines functions and nothing else.

# Reduce one token to a bare host: drop scheme, userinfo, path, query, port and
# IPv6 brackets, and lowercase the result.
#
# The userinfo strip matters: http://localhost@evil.test/ has authority
# "evil.test", not "localhost". Reading the host as the part before "@" is a
# classic way to smuggle an out-of-scope target past a naive check.
normalise_host() {
    printf '%s' "$1" \
        | tr 'A-Z' 'a-z' \
        | sed -e 's|^[a-z0-9+.-]*://||' \
              -e 's|^[^/@]*@||' \
              -e 's|[/?#].*$||' \
        | sed -e 's|^\[\(.*\)\]:.*$|\1|' \
              -e 's|^\[\(.*\)\]$|\1|' \
        | sed -e '/^[0-9a-f:]*:[0-9a-f:]*$/! s|:[0-9]*$||'
}

# Echo the authorised hosts, one per line, lowercased, comments stripped.
# Returns non-zero if the file is missing or lists nothing.
load_scope() {
    _file="$1"
    [ -f "$_file" ] || return 1
    _hosts=$(sed -e 's/#.*//' -e 's/[[:space:]]//g' "$_file" \
             | grep -v '^$' | tr 'A-Z' 'a-z')
    [ -n "$_hosts" ] || return 1
    printf '%s\n' "$_hosts"
}

# in_scope <host> <newline-separated-authorised-hosts>
# Exact match only. No wildcards, no suffix matching: allowing "*.example.com"
# or a suffix rule is how evil-localhost.test gets treated as localhost.
in_scope() {
    _h="$1"
    _allowed_list="$2"
    [ -n "$_h" ] || return 1
    for _allowed in $_allowed_list; do
        [ "$_h" = "$_allowed" ] && return 0
    done
    return 1
}

# Does this token look like a host on its own? Used to catch targets that were
# not introduced by a recognised flag. Over-matching is safe here: an extra
# candidate can only cause a block, never an allow.
looks_like_host() {
    printf '%s' "$1" | grep -qE '^([0-9]{1,3}\.){3}[0-9]{1,3}$' && return 0
    printf '%s' "$1" | grep -qE '^[0-9a-f]{0,4}(:[0-9a-f]{0,4}){2,}$' && return 0
    printf '%s' "$1" | grep -qE '^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$' && return 0
    return 1
}
