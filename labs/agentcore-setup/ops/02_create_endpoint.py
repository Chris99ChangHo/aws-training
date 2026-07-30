"""프로덕션 엔드포인트를 특정 버전에 고정해 생성합니다."""
import os
import time

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