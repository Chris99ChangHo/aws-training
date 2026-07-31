#!/bin/sh
# test_guard_infra.sh - exercises the PreToolUse guard with synthetic harness
# payloads. Requires no linters: the guard is pure decision logic, so it is
# fully testable on a machine where trivy/hadolint/actionlint are absent.
#
# Usage: sh tests/test_guard_infra.sh
# Exit code 0 means every case behaved as specified.

set -u

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
LAB_ROOT=$(cd "$SCRIPT_DIR/.." && pwd)
GUARD="$LAB_ROOT/scanners/guard_infra.sh"

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

# Claude Code shaped payload for a shell command.
cc() {
    printf '{"tool_name":"Bash","tool_input":{"command":%s}}' \
        "$(printf '%s' "$1" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))')"
}

# Alternative payload shape, to prove the multi-path extraction works.
alt() {
    printf '{"toolName":"shell","toolInput":{"command":%s}}' \
        "$(printf '%s' "$1" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))')"
}

# File-reading tool payload: these bypass command inspection entirely.
rd() {
    printf '{"tool_name":"Read","tool_input":{"file_path":%s}}' \
        "$(printf '%s' "$1" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))')"
}

ALLOW=0
BLOCK=2

echo "== payload parsing =="
expect $BLOCK "empty payload fails closed"            ""
expect $ALLOW "unrecognised payload is not a command" '{"tool_name":"Glob"}'
expect $ALLOW "alt payload shape parses"              "$(alt 'terraform plan')"

echo
echo "== terraform: plan yes, apply no =="
expect $ALLOW "terraform validate"                    "$(cc 'terraform validate')"
expect $ALLOW "terraform plan"                        "$(cc 'terraform plan')"
expect $ALLOW "terraform fmt -check"                  "$(cc 'terraform fmt -check')"
expect $ALLOW "terraform show"                        "$(cc 'terraform show')"
expect $BLOCK "terraform apply"                       "$(cc 'terraform apply')"
expect $BLOCK "terraform apply -auto-approve"         "$(cc 'terraform apply -auto-approve')"
expect $BLOCK "terraform destroy"                     "$(cc 'terraform destroy')"
expect $BLOCK "terraform plan -destroy"               "$(cc 'terraform plan -destroy')"
expect $BLOCK "terraform state rm"                    "$(cc 'terraform state rm aws_s3_bucket.x')"
expect $BLOCK "tofu apply (fork is still terraform)"  "$(cc 'tofu apply')"
expect $BLOCK "terragrunt destroy"                    "$(cc 'terragrunt destroy')"

echo
echo "== kubectl / helm =="
expect $ALLOW "kubectl get pods"                      "$(cc 'kubectl get pods')"
expect $ALLOW "kubectl describe node"                 "$(cc 'kubectl describe node n1')"
expect $ALLOW "kubectl diff -f manifest.yaml"         "$(cc 'kubectl diff -f manifest.yaml')"
expect $BLOCK "kubectl delete"                        "$(cc 'kubectl delete pod web-1')"
expect $BLOCK "kubectl apply"                         "$(cc 'kubectl apply -f manifest.yaml')"
expect $BLOCK "kubectl rollout restart"               "$(cc 'kubectl rollout restart deploy/web')"
expect $BLOCK "kubectl drain"                         "$(cc 'kubectl drain node1')"
expect $ALLOW "helm template"                         "$(cc 'helm template mychart')"
expect $ALLOW "helm lint"                             "$(cc 'helm lint mychart')"
expect $BLOCK "helm upgrade"                          "$(cc 'helm upgrade rel mychart')"
expect $BLOCK "helm uninstall"                        "$(cc 'helm uninstall rel')"

echo
echo "== docker =="
expect $ALLOW "docker build"                          "$(cc 'docker build -t app .')"
expect $ALLOW "docker inspect"                        "$(cc 'docker inspect app')"
expect $BLOCK "docker run"                            "$(cc 'docker run -d app')"
expect $BLOCK "docker push"                           "$(cc 'docker push registry/app')"
expect $BLOCK "docker system prune"                   "$(cc 'docker system prune -af')"

echo
echo "== cloud CLIs: read verbs only =="
expect $ALLOW "aws s3 ls"                             "$(cc 'aws s3 ls')"
expect $ALLOW "aws ec2 describe-instances"            "$(cc 'aws ec2 describe-instances')"
expect $ALLOW "aws iam get-role"                      "$(cc 'aws iam get-role --role-name r')"
expect $BLOCK "aws ec2 terminate-instances"           "$(cc 'aws ec2 terminate-instances --instance-ids i-1')"
expect $BLOCK "aws s3 rb"                             "$(cc 'aws s3 rb s3://bucket')"
expect $BLOCK "aws iam delete-role"                   "$(cc 'aws iam delete-role --role-name r')"
expect $BLOCK "aws eks update-cluster-config"         "$(cc 'aws eks update-cluster-config --name c')"

echo
echo "== structural bans =="
expect $BLOCK "chaining hides a second command"       "$(cc 'terraform plan; terraform apply')"
expect $BLOCK "&& chaining"                           "$(cc 'terraform plan && terraform apply')"
expect $BLOCK "pipe"                                  "$(cc 'kubectl get pods | xargs kubectl delete')"
expect $BLOCK "command substitution"                  "$(cc 'kubectl delete pod $(kubectl get pods -o name)')"
expect $BLOCK "backticks"                             "$(cc 'terraform apply `cat plan`')"
expect $BLOCK "output redirection"                    "$(cc 'terraform plan > /etc/hosts')"
expect $BLOCK "privilege escalation"                  "$(cc 'sudo terraform apply')"

echo
echo "== credential and state material =="
expect $BLOCK "reads terraform state"                 "$(cc 'cat terraform.tfstate')"
expect $BLOCK "reads tfvars"                          "$(cc 'cat prod.tfvars')"
expect $BLOCK "reads kubeconfig"                      "$(cc 'cat ~/.kube/config')"
expect $BLOCK "reads aws credentials"                 "$(cc 'cat /Users/x/.aws/credentials')"
expect $BLOCK "file tool targets tfstate"             "$(rd 'infra/terraform.tfstate')"
expect $BLOCK "file tool targets kubeconfig"          "$(rd '/Users/x/.kube/config')"
expect $ALLOW "file tool reads a definition"          "$(rd 'infra/main.tf')"

echo
echo "== wrappers and read-only inspection =="
expect $ALLOW "iac wrapper"                           "$(cc 'sh agents/devops/scanners/run_iac.sh .')"
expect $ALLOW "preflight wrapper"                     "$(cc 'sh agents/devops/scanners/preflight.sh')"
expect $ALLOW "gate"                                  "$(cc 'python3 agents/core/gate/gate.py --fail-on high')"
expect $ALLOW "git status"                            "$(cc 'git status')"
expect $ALLOW "ls"                                    "$(cc 'ls infra')"

echo
echo "-----------------------------------------------------------"
printf 'passed: %s   failed: %s\n' "$PASS" "$FAIL"

if [ "$FAIL" -ne 0 ]; then
    printf 'failing cases:%s\n' "$FAILED_CASES"
    echo "guard_infra.sh did not behave as specified."
    exit 1
fi

echo "all guard_infra.sh cases behaved as specified."
exit 0
