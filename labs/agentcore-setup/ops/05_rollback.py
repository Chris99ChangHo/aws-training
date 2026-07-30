"""장애가 확인되면 production 엔드포인트를 이전 버전으로 되돌립니다."""
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