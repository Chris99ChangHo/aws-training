"""프로덕션 엔드포인트를 특정 버전에 고정해 생성합니다."""
import os
import time

import boto3

REGION = "us-west-2"
RUNTIME_ID = os.environ["RUNTIME_ID"]
STABLE_VERSION = "1"  # 조회 결과에 맞춰 조정

control = boto3.client("bedrock-agentcore-control", region_name=REGION)

control.create_agent_runtime_endpoint(
    agentRuntimeId=RUNTIME_ID,
    name="production",
    agentRuntimeVersion=STABLE_VERSION,
    description=f"stable traffic pinned to v{STABLE_VERSION}",
)
print(f"production 엔드포인트 생성 요청 — v{STABLE_VERSION} 고정")

while True:
    ep = control.get_agent_runtime_endpoint(
        agentRuntimeId=RUNTIME_ID,
        endpointName="production",
    )
    print(f"  status={ep['status']} live={ep.get('liveVersion', '-')}")
    if ep["status"] in ("READY", "CREATE_FAILED"):
        break
    time.sleep(5)