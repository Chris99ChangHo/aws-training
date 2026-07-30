"""카나리 검증을 통과했으면 production 엔드포인트를 새 버전으로 승격합니다."""
import os

import boto3

REGION = "us-west-2"
RUNTIME_ID = os.environ["RUNTIME_ID"]
NEW_VERSION = "3"

control = boto3.client("bedrock-agentcore-control", region_name=REGION)

response = control.update_agent_runtime_endpoint(
    agentRuntimeId=RUNTIME_ID,
    endpointName="production",
    agentRuntimeVersion=NEW_VERSION,
    description=f"promoted to v{NEW_VERSION}",
)
print(f"status      : {response['status']}")
print(f"liveVersion : {response.get('liveVersion', '-')}")
print(f"targetVersion: {response.get('targetVersion', '-')}")