"""AgentCore Runtime에 배포된 CodingService를 호출한다.

1. 세션을 시작(일반 invoke)해 준비 상태를 확인
2. Shell Command API(invoke_agent_runtime_command)로 세션 안에서 git clone
3. 같은 세션에서 코드 수정 요청 (파일시스템 공유)
4. Shell Command로 git push

실행 전 RUNTIME_ARN을 채워야 한다.
"""
from __future__ import annotations

import datetime
import json
import sys
import uuid

import boto3
import botocore.auth
import botocore.awsrequest
import botocore.compat
from botocore.config import Config

REGION = "us-west-2"
RUNTIME_ARN = "arn:aws:bedrock-agentcore:us-west-2:000000000000:runtime/CodingService_CodingService-wexBNxC63R"
REPOSITORY_NAME = "dining-reservation"

# invoke 엔트리포인트 프로세스는 /workspace에 쓰기 권한이 없어(실제로 겪은
# PermissionError) main.py가 /tmp/workspace로 폴백한다. Shell Command는
# 다른 실행 컨텍스트(root)라 /workspace에 쓸 수 있지만, 그러면 두 API가
# 서로 다른 경로를 보게 되어 git commit이 "nothing to commit"으로
# 끝난다(실제로 겪음) — Shell Command도 같은 /tmp/workspace를 쓰도록 통일한다.
REPO_DIR = "/tmp/workspace/repo"

# 리뷰 루프(Coder→Reviewer→Tester 최대 3라운드)는 boto3 기본 read timeout
# (60초)보다 오래 걸린다 — 실제로 ReadTimeoutError를 겪었다. 넉넉하게 설정한다.
agentcore_client = boto3.client(
    "bedrock-agentcore",
    region_name=REGION,
    config=Config(read_timeout=600, connect_timeout=30, retries={"max_attempts": 1}),
)

# runtimeSessionId는 호출자가 만들어 전달하는 입력값 (33자 이상)
SESSION_ID = f"coding-service-{uuid.uuid4().hex}"


def _signed_codecommit_url(repository_name: str) -> str:
    """git-remote-codecommit과 동일한 SigV4 서명으로 인증된 HTTPS git URL을
    만든다 (main.py의 get_codecommit_url 도구와 동일 로직).

    Runtime 컨테이너에는 git-remote-codecommit이 없다 — PyPI에 wheel이
    없는 sdist-only 패키지라 AgentCore CDK 패키징(--only-binary)에 넣을
    수 없다(실제로 겪은 문제). 이 호출자(로컬 스크립트)도 동일한 방식으로
    직접 서명해 Shell Command에 인증 URL을 넘긴다.
    """
    session = boto3.Session(region_name=REGION)
    credentials = session.get_credentials().get_frozen_credentials()

    hostname = f"git-codecommit.{REGION}.amazonaws.com"
    path = f"/v1/repos/{repository_name}"

    token = f"%{credentials.token}" if credentials.token else ""
    username = botocore.compat.quote(credentials.access_key + token, safe="")

    request = botocore.awsrequest.AWSRequest(method="GIT", url=f"https://{hostname}{path}")
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S")
    request.context["timestamp"] = timestamp
    signer = botocore.auth.SigV4Auth(credentials, "codecommit", REGION)
    canonical_request = f"GIT\n{path}\n\nhost:{hostname}\n\nhost\n"
    string_to_sign = signer.string_to_sign(request, canonical_request)
    signature = signer.signature(string_to_sign, request)

    return f"https://{username}:{timestamp}Z{signature}@{hostname}{path}"


def run_command(command: str, timeout: int = 300) -> int | None:
    """세션 안에서 셸 명령을 실행하고 종료 코드를 반환한다.

    Shell Command API는 명령 문자열의 &&·;·| 같은 셸 연산자를 해석하지
    않고 그대로 토큰화해서 실행한다 (실제로 확인함 — "cd /tmp && pwd"를
    그대로 보내면 cd가 "&&"와 "pwd"까지 자신의 인자로 받아 "too many
    arguments"로 실패한다). 복합 명령은 sh -c로 명시적으로 감싼다.
    """
    wrapped_command = f'sh -c "{command}"' if ("&&" in command or ";" in command or "|" in command) else command
    response = agentcore_client.invoke_agent_runtime_command(
        agentRuntimeArn=RUNTIME_ARN,
        runtimeSessionId=SESSION_ID,
        contentType="application/json",
        accept="application/vnd.amazon.eventstream",
        body={"command": wrapped_command, "timeout": timeout},
    )
    exit_code = None
    for event in response.get("stream", []):
        chunk = event.get("chunk", {})
        if "contentDelta" in chunk:
            delta = chunk["contentDelta"]
            if delta.get("stdout"):
                print(delta["stdout"], end="")
            if delta.get("stderr"):
                print(delta["stderr"], end="", file=sys.stderr)
        if "contentStop" in chunk:
            exit_code = chunk["contentStop"].get("exitCode")
    return exit_code


def invoke(prompt: str, target_path: str = "") -> str:
    """단순 요청(target_path 없음) 또는 리뷰 루프(target_path 지정) 호출."""
    payload: dict = {"prompt": prompt}
    if target_path:
        payload["target_path"] = target_path
    response = agentcore_client.invoke_agent_runtime(
        agentRuntimeArn=RUNTIME_ARN,
        runtimeSessionId=SESSION_ID,
        payload=json.dumps(payload).encode(),
    )
    body = json.loads(response["response"].read())
    return body["result"]


def main() -> int:
    print(f"세션 시작: {SESSION_ID}")

    # 1. 세션 시작 — 준비 상태 확인
    print(invoke("작업 준비 완료를 알려 주세요")[:200])

    # 2. Shell Command — git clone (SigV4로 서명한 인증 URL 사용)
    auth_url = _signed_codecommit_url(REPOSITORY_NAME)
    clone_exit = run_command(f"git clone {auth_url} {REPO_DIR}")
    print(f"\ngit clone exit: {clone_exit}")
    if clone_exit != 0:
        print("git clone 실패 — REPO_URL과 Runtime 실행 역할의 codecommit 권한을 확인하세요.")
        return 1

    # 3. 같은 세션에서 코드 수정 요청 — 파일시스템을 공유하므로 repo/ 안에서 작업
    result = invoke("repo/reservation.py에 예약 인원 검증 함수를 추가해 주세요")
    print(result[:300])

    # 4. Shell Command — git push (서명은 시간 제한이 있으므로 push 직전에
    #    remote URL을 새로 서명해 갱신한다). 컨테이너에는 git author identity가
    #    설정되어 있지 않아(실제로 겪은 오류: "Author identity unknown") 커밋
    #    전에 로컬 설정을 지정한다.
    fresh_auth_url = _signed_codecommit_url(REPOSITORY_NAME)
    push_exit = run_command(
        f"cd {REPO_DIR} && "
        "git config user.email 'coding-service@example.com' && "
        "git config user.name 'CodingService Agent' && "
        f"git remote set-url origin {fresh_auth_url} && "
        "git add -A && git commit -m 'feat: add capacity validation' && git push"
    )
    print(f"\ngit push exit: {push_exit}")
    return 0 if push_exit == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
