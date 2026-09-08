"""멀티턴 대화 — 3턴에 걸쳐 요구사항 파악 → 검색 → 예약을 진행합니다."""
from strands import Agent
from strands.models import BedrockModel
from tools import search_restaurants, create_reservation

REGION = "us-west-2"

model = BedrockModel(
    model_id="us.anthropic.claude-sonnet-4-6",
    region_name=REGION,
)

agent = Agent(
    model=model,
    system_prompt="""당신은 강남 지역 전문 식당 컨시어지 AI입니다.

역할:
- 고객의 요구사항을 파악합니다
- search_restaurants 도구로 조건에 맞는 식당을 검색합니다
- create_reservation 도구로 예약을 진행합니다

규칙:
- 한국어로 답변합니다
- 정보가 부족하면 먼저 질문합니다
- 예약 시 날짜, 시간, 인원, 예약자 이름을 확인합니다""",
    tools=[search_restaurants, create_reservation],
    callback_handler=None,  # 스트리밍 콜백 끄기 — print 결과만 출력
)

# 턴 1: 요구사항 전달
print("=" * 60)
print("👤 턴 1: 요구사항 전달")
print("=" * 60)
response1 = agent(
    "이번 주 금요일에 여자친구와 기념일 저녁을 먹으려고 합니다. "
    "분위기 좋은 곳으로 추천해주세요."
)
print(response1)

# 턴 2: 추가 조건 제시 — 에이전트가 이전 대화를 기억
print("\n" + "=" * 60)
print("👤 턴 2: 추가 조건 제시")
print("=" * 60)
response2 = agent(
    "예산은 1인 6만원 정도이고, 강남역 근처가 좋겠습니다. "
    "와인 페어링이 가능한 곳이면 좋겠어요."
)
print(response2)

# 턴 3: 예약 요청 — 에이전트가 추천한 식당으로 예약
print("\n" + "=" * 60)
print("👤 턴 3: 예약 요청")
print("=" * 60)
response3 = agent(
    "첫 번째 추천 식당으로 예약해주세요. "
    "7월 31일 금요일 저녁 7시, 2명, 예약자 이름은 김민수입니다."
)
print(response3)