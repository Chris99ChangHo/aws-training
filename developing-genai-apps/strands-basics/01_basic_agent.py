"""기본 에이전트 — 도구 없이 LLM만으로 식당 추천을 시도합니다."""
from strands import Agent
from strands.models import BedrockModel

REGION = "us-west-2"

# Bedrock의 Claude Sonnet 4.6 모델 사용 (크로스 리전 추론 프로파일)
model = BedrockModel(
    model_id="us.anthropic.claude-sonnet-4-6",
    region_name=REGION,
)

# 시스템 프롬프트로 에이전트의 역할과 규칙을 정의
agent = Agent(
    model=model,
    system_prompt="""당신은 강남 지역 전문 식당 컨시어지 AI입니다.

역할:
- 고객의 요구사항(음식 종류, 예산, 인원, 분위기)을 파악합니다
- 조건에 맞는 식당을 추천합니다
- 고객이 원하면 예약을 진행합니다

규칙:
- 한국어로 답변합니다
- 정보가 부족하면 먼저 질문합니다
- 추천 시 식당명, 카테고리, 가격대, 특징을 포함합니다""",
    # 기본 콜백(응답 스트리밍 출력)을 끄고 마지막 print만 출력합니다 — 아래 출력 예시와 일치
    callback_handler=None,
)

# 에이전트에게 질문 — 도구가 없으므로 LLM 지식만으로 답변
response = agent("강남역 근처 이탈리안 식당 추천해주세요. 2명이고 예산은 1인 5만원입니다.")
print(response)