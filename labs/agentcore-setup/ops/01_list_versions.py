"""Runtime의 최신 버전과 엔드포인트 목록을 조회합니다."""
import os

import boto3

REGION = "us-west-2"
RUNTIME_ID = os.environ["RUNTIME_ID"]

control = boto3.client("bedrock-agentcore-control", region_name=REGION)

runtime = control.get_agent_runtime(agentRuntimeId=RUNTIME_ID)
print(f"Runtime : {runtime['agentRuntimeName']}")
print(f"Status  : {runtime['status']}")
print(f"Version : {runtime['agentRuntimeVersion']}")

endpoints = control.list_agent_runtime_endpoints(agentRuntimeId=RUNTIME_ID)
print("\n엔드포인트:")
for ep in endpoints.get("runtimeEndpoints", []):
    print(f"  - {ep['name']:12s} status={ep['status']:8s} live={ep.get('liveVersion', '-')}")