# test_invoke.py — boto3 bedrock-agentcore로 배포된 Runtime을 직접 호출
#
# AGENT_RUNTIME_ARN은 환경변수로 주입한다(agentcore invoke 출력이나
# `agentcore status`로 확인한 값):
#   AGENT_RUNTIME_ARN="arn:aws:bedrock-agentcore:us-west-2:<ACCOUNT_ID>:runtime/..." \
#     python3 test_invoke.py
import json
import os
import uuid

import boto3

REGION = "us-west-2"
AGENT_RUNTIME_ARN = os.environ.get(
    "AGENT_RUNTIME_ARN", "<YOUR_AGENT_RUNTIME_ARN>"
)


def invoke_agent(prompt: str, session_id: str | None = None) -> str:
    client = boto3.client("bedrock-agentcore", region_name=REGION)
    session_id = session_id or str(uuid.uuid4()) + str(uuid.uuid4())

    response = client.invoke_agent_runtime(
        agentRuntimeArn=AGENT_RUNTIME_ARN,
        runtimeSessionId=session_id,
        qualifier="DEFAULT",
        payload=json.dumps({"prompt": prompt}),
    )

    body = response["response"].read()
    text = body.decode("utf-8")

    # 스트리밍 엔트리포인트라 SSE(data: 줄) 프레이밍이 섞일 수 있어 줄 단위로 파싱
    answer_parts = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue
        data_str = line[len("data:"):].strip()
        try:
            event = json.loads(data_str)
        except json.JSONDecodeError:
            continue
        delta = event.get("event", {}).get("contentBlockDelta", {}).get("delta", {})
        if "text" in delta:
            answer_parts.append(delta["text"])

    if answer_parts:
        return "".join(answer_parts)
    return text  # 파싱 실패 시 원문 그대로 반환(디버깅용)


if __name__ == "__main__":
    answer = invoke_agent("강남 식당 추천해 주세요")
    print(answer)
