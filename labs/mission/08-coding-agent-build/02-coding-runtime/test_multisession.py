"""멀티세션 협업 실증 (도전 과제) — 서로 다른 runtimeSessionId로 동시 호출해
각 세션이 /tmp/workspace에 만든 파일이 서로 격리되는지 확인한다.

공유가 필요한 데이터만 /mnt/persistent(work-log.json)에 둔다는 것을
대조군으로 함께 보여준다.
"""
from __future__ import annotations

import json
import uuid
from concurrent.futures import ThreadPoolExecutor

import boto3
from botocore.config import Config

REGION = "us-west-2"
RUNTIME_ARN = "arn:aws:bedrock-agentcore:us-west-2:000000000000:runtime/CodingService_CodingService-wexBNxC63R"

agentcore_client = boto3.client(
    "bedrock-agentcore",
    region_name=REGION,
    config=Config(read_timeout=300, connect_timeout=30, retries={"max_attempts": 1}),
)


def invoke(session_id: str, prompt: str) -> str:
    response = agentcore_client.invoke_agent_runtime(
        agentRuntimeArn=RUNTIME_ARN,
        runtimeSessionId=session_id,
        payload=json.dumps({"prompt": prompt}).encode(),
    )
    body = json.loads(response["response"].read())
    return body["result"]


def main() -> int:
    session_a = f"team-member-a-{uuid.uuid4().hex}"
    session_b = f"team-member-b-{uuid.uuid4().hex}"

    # 두 팀원이 동시에 서로 다른 파일을 만든다.
    with ThreadPoolExecutor(max_workers=2) as executor:
        future_a = executor.submit(
            invoke, session_a, "alice.txt 파일에 'Alice의 작업'이라고 써주세요"
        )
        future_b = executor.submit(
            invoke, session_b, "bob.txt 파일에 'Bob의 작업'이라고 써주세요"
        )
        result_a = future_a.result()
        result_b = future_b.result()

    print(f"[세션 A 결과] {result_a[:150]}")
    print(f"[세션 B 결과] {result_b[:150]}")

    # 교차 조회 — A 세션에서 B가 만든 파일이 안 보여야 격리 증명
    cross_check_a = invoke(session_a, "현재 워크스페이스에 bob.txt 파일이 있는지 ls로 확인해 주세요")
    cross_check_b = invoke(session_b, "현재 워크스페이스에 alice.txt 파일이 있는지 ls로 확인해 주세요")

    print(f"\n[세션 A가 본 워크스페이스] {cross_check_a[:200]}")
    print(f"[세션 B가 본 워크스페이스] {cross_check_b[:200]}")

    print(
        "\n판정: 세션 A 응답에 'bob.txt'가 없고, 세션 B 응답에 'alice.txt'가 "
        "없어야 격리 실증 성공입니다."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
