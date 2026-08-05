"""빌트인 도구 — calculator, current_time, file_read를 에이전트에 연결합니다."""
from strands import Agent
from strands.models import BedrockModel
from strands_tools import calculator, current_time, file_read

REGION = "us-west-2"

model = BedrockModel(
    model_id="us.anthropic.claude-sonnet-4-6",
    region_name=REGION,
)

# 빌트인 도구 3개를 에이전트에 연결
agent = Agent(
    model=model,
    system_prompt="""당신은 강남 지역 전문 식당 컨시어지 AI입니다.

역할:
- 파일에서 식당 정보를 읽어 고객에게 추천합니다
- 예산 계산을 도와줍니다
- 현재 시간을 확인하여 영업 중인 식당을 안내합니다

규칙:
- 한국어로 답변합니다
- 반드시 파일의 실제 데이터를 기반으로 추천합니다
- 추천 시 식당명, 카테고리, 가격대, 특징을 포함합니다""",
    tools=[calculator, current_time, file_read],
    callback_handler=None,  # 스트리밍 콜백 끄기 — print 결과만 출력
)

# 에이전트에게 질문 — file_read로 파일 읽기 + calculator로 계산
response = agent(
    "restaurants.txt를 읽고 1인 5만원 이하 식당을 추천해주세요. "
    "2명이 가면 총 예산이 얼마인지 계산해주세요."
)
print(response)

# --- Structured Output ---
from pydantic import BaseModel, Field
from typing import List

# Pydantic 모델 정의 — 에이전트 응답의 구조를 지정
class RestaurantRecommendation(BaseModel):
    """개별 식당 추천 정보"""
    name: str = Field(description="식당 이름")
    cuisine: str = Field(description="음식 카테고리")
    location: str = Field(description="위치")
    price_per_person: str = Field(description="1인 가격대")
    rating: float = Field(description="평점")
    features: List[str] = Field(description="특징 목록")
    total_for_two: str = Field(description="2인 기준 총 예상 비용")

class RecommendationList(BaseModel):
    """식당 추천 목록"""
    recommendations: List[RestaurantRecommendation] = Field(
        description="추천 식당 목록"
    )
    summary: str = Field(description="추천 요약")

# Structured Output으로 에이전트 호출
result = agent(
    "restaurants.txt를 읽고 1인 5만원 이하 식당을 추천해주세요. "
    "2명이 가면 총 예산도 알려주세요.",
    structured_output_model=RecommendationList,
)

# 타입 안전한 접근
data = result.structured_output
print(f"\n📊 Structured Output 결과:")
print(f"추천 요약: {data.summary}")
print(f"추천 식당 수: {len(data.recommendations)}")
for r in data.recommendations:
    print(f"\n🍽️ {r.name} ({r.cuisine})")
    print(f"   위치: {r.location}")
    print(f"   가격: {r.price_per_person}")
    print(f"   평점: {r.rating}")
    print(f"   특징: {', '.join(r.features)}")
    print(f"   2인 예상: {r.total_for_two}")