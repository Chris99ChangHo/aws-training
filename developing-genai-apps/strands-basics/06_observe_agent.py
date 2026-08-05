"""콜백 관찰 — 에이전트의 추론 과정을 실시간으로 출력합니다."""
from strands import Agent
from strands.models import BedrockModel
from tools import search_restaurants, create_reservation

REGION = "us-west-2"

model = BedrockModel(
    model_id="us.anthropic.claude-sonnet-4-6",
    region_name=REGION,
)

# 이미 출력한 도구 호출 ID 기록 — current_tool_use는 스트리밍 델타마다 반복 발화됨
seen_tool_ids = set()

def callback_handler(**kwargs):
    """에이전트 이벤트를 실시간으로 출력하는 콜백 핸들러"""

    # ReAct 루프 시작
    if "start_event_loop" in kwargs:
        print("\n🔄 [이벤트 루프 시작]")

    # 도구 호출 시작 — 같은 toolUseId로 여러 번 발화되므로 처음 한 번만 출력
    # (input은 스트리밍 중 누적되는 부분 문자열이라 완성 전까지 파싱할 수 없음)
    if "current_tool_use" in kwargs:
        tool_use = kwargs["current_tool_use"]
        tool_id = tool_use.get("toolUseId")
        if tool_id and tool_id not in seen_tool_ids:
            seen_tool_ids.add(tool_id)
            print(f"\n[도구 호출] {tool_use.get('name', 'unknown')}")

    # 스트리밍 텍스트 출력
    if "data" in kwargs:
        print(kwargs["data"], end="", flush=True)

# 콜백 핸들러를 에이전트에 연결
agent = Agent(
    model=model,
    system_prompt="""당신은 강남 지역 전문 식당 컨시어지 AI입니다.
도구를 사용하여 식당을 검색하고 예약을 진행합니다.
한국어로 답변합니다.""",
    tools=[search_restaurants, create_reservation],
    callback_handler=callback_handler,
)

print("🚀 에이전트 실행 시작\n")
response = agent(
    "강남역 근처 가성비 좋은 식당을 찾아주세요. "
    "4명이 갈 건데 1인 3만원 이하로요."
)
print("\n\n✅ 에이전트 실행 완료")