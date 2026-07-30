"""Runtime의 최신 버전과 엔드포인트 목록을 조회합니다."""
import os

import boto3

REGION = "us-west-2"

# 런타임 이름은 CLI가 <프로젝트명>_<런타임명>으로 붙인다(예: RestaurantAgent_RestaurantAgent).
# 'RestaurantAgent'로 조회하면 매칭 실패로 RUNTIME_ID에 "None" 문자열이 들어가고,
# 존재하지 않는 ID로 API를 호출해 엉뚱한 AccessDenied가 나므로 조회 명령을 안내한다.
RUNTIME_ID = os.environ.get("RUNTIME_ID")
if RUNTIME_ID is None or RUNTIME_ID in ("", "None"):
    raise SystemExit(
        "RUNTIME_ID 환경변수가 필요합니다. 아래 명령으로 설정하세요(한 줄로 실행):\n"
        '  export RUNTIME_ID=$(aws bedrock-agentcore-control list-agent-runtimes '
        f'--region {REGION} --output text '
        '--query "agentRuntimes[?agentRuntimeName==\'RestaurantAgent_RestaurantAgent\']'
        '.agentRuntimeId | [0]")'
    )

control = boto3.client("bedrock-agentcore-control", region_name=REGION)

runtime = control.get_agent_runtime(agentRuntimeId=RUNTIME_ID)
print(f"Runtime : {runtime['agentRuntimeName']}")
print(f"Status  : {runtime['status']}")
print(f"Version : {runtime['agentRuntimeVersion']}")

endpoints = control.list_agent_runtime_endpoints(agentRuntimeId=RUNTIME_ID)
print("\n엔드포인트:")
for ep in endpoints.get("runtimeEndpoints", []):
    print(f"  - {ep['name']:12s} status={ep['status']:8s} live={ep.get('liveVersion', '-')}")