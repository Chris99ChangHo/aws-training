"""배포된 DiningConcierge Runtime 호출 클라이언트."""
from __future__ import annotations

import json
import os

import boto3

REGION = "us-west-2"
# 04번 미션에서 배포한 Runtime ARN을 환경변수로 주입한다:
#   AGENT_RUNTIME_ARN="arn:aws:bedrock-agentcore:us-west-2:<ACCOUNT_ID>:runtime/..." \
#     python3 agent_client.py
RUNTIME_ARN = os.environ.get("AGENT_RUNTIME_ARN", "<YOUR_AGENT_RUNTIME_ARN>")

client = boto3.client("bedrock-agentcore", region_name=REGION)
control = boto3.client("bedrock-agentcore-control", region_name=REGION)


def invoke_agent(prompt: str, session_id: str, actor_id: str) -> dict:
    """Runtime을 호출하고 결과를 파싱해 반환한다."""
    response = client.invoke_agent_runtime(
        agentRuntimeArn=RUNTIME_ARN,
        runtimeSessionId=session_id,
        qualifier="DEFAULT",
        payload=json.dumps(
            {"prompt": prompt, "session_id": session_id, "actor_id": actor_id}
        ).encode("utf-8"),
    )
    body = response["response"].read().decode("utf-8")
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return {"result": body, "tool_calls": []}


def get_runtime_status() -> str:
    """DiningConcierge Runtime 상태를 반환한다."""
    for rt in control.list_agent_runtimes()["agentRuntimes"]:
        if rt["agentRuntimeName"] == "DiningConcierge_DiningConcierge":
            return rt["status"]
    return "NOT_FOUND"


if __name__ == "__main__":
    print("Runtime:", get_runtime_status())
    print(invoke_agent(
        "강남 식당 추천해 주세요",
        "session-app-test-000000000000000000",
        "user-001",
    ))
