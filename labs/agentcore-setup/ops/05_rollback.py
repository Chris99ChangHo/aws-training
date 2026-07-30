"""장애가 확인되면 production 엔드포인트를 이전 버전으로 되돌립니다."""
import os

import boto3

REGION = "us-west-2"
RUNTIME_ID = os.environ["RUNTIME_ID"]
PREVIOUS_VERSION = "1"

control = boto3.client("bedrock-agentcore-control", region_name=REGION)

response = control.update_agent_runtime_endpoint(
    agentRuntimeId=RUNTIME_ID,
    endpointName="production",
    agentRuntimeVersion=PREVIOUS_VERSION,
    description=f"rollback to v{PREVIOUS_VERSION}",
)
print(f"롤백 요청 — target v{PREVIOUS_VERSION}, status={response['status']}")

ep = control.get_agent_runtime_endpoint(agentRuntimeId=RUNTIME_ID, endpointName="production")
print(f"현재 live={ep.get('liveVersion', '-')} target={ep.get('targetVersion', '-')}")