"""컨시어지 에이전트 — 커스텀 도구로 식당 검색 및 예약을 수행합니다."""
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
- search_restaurants 도구로 조건에 맞는 식당을 검색합니다
- 검색 결과를 바탕으로 최적의 식당을 추천합니다
- 고객이 원하면 create_reservation 도구로 예약을 진행합니다

규칙:
- 한국어로 답변합니다
- 반드시 도구를 사용하여 실제 데이터를 기반으로 추천합니다
- 추천 시 식당명, 카테고리, 가격대, 특징을 포함합니다
- 예약 시 예약 번호를 안내합니다""",
    tools=[search_restaurants, create_reservation],
    callback_handler=None,  # 스트리밍 콜백 끄기 — print 결과만 출력
)

# Part 1과 동일한 질문 — 이제 실제 데이터 기반 추천
response = agent(
    "강남역 근처 이탈리안 식당을 추천해주세요. 2명이고 예산은 1인 5만원입니다."
)
print(response)