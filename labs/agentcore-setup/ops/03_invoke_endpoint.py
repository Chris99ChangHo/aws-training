"""카나리 엔드포인트를 만들고 엔드포인트별로 호출해 응답을 비교합니다."""
import json
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
CANARY_VERSION = "3"  # 재배포로 생긴 새 버전

control = boto3.client("bedrock-agentcore-control", region_name=REGION)
data = boto3.client("bedrock-agentcore", region_name=REGION)

# 1) 카나리 엔드포인트 — 새 버전에 고정
control.create_agent_runtime_endpoint(
    agentRuntimeId=RUNTIME_ID,
    name="canary",
    agentRuntimeVersion=CANARY_VERSION,
    description=f"canary pinned to v{CANARY_VERSION}",
)
while True:
    ep = control.get_agent_runtime_endpoint(agentRuntimeId=RUNTIME_ID, endpointName="canary")
    if ep["status"] in ("READY", "CREATE_FAILED"):
        print(f"canary status={ep['status']} live={ep.get('liveVersion', '-')}")
        break
    time.sleep(5)

runtime = control.get_agent_runtime(agentRuntimeId=RUNTIME_ID)
runtime_arn = runtime["agentRuntimeArn"]

# 2) 엔드포인트별 호출 — qualifier에 엔드포인트 이름을 넣습니다
for endpoint in ("production", "canary"):
    response = data.invoke_agent_runtime(
        agentRuntimeArn=runtime_arn,
        qualifier=endpoint,
        payload=json.dumps({"prompt": "트라토리아 벨라 오늘 저녁 예약 가능한지 확인해주세요"}).encode("utf-8"),
    )
    body = response["response"].read().decode("utf-8")
    print(f"\n[{endpoint}] {body[:200]}")