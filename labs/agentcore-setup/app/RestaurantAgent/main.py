# app/RestaurantAgent/main.py
"""강남 다이닝 컨시어지 에이전트 — 도구 포함 버전.

check_reservations 도구로 식당의 예약 가능 상태를 조회합니다.
"""
from strands import Agent, tool
from strands.models import BedrockModel
from bedrock_agentcore import BedrockAgentCoreApp

REGION = "us-west-2"

app = BedrockAgentCoreApp()

@tool
def check_reservations(restaurant_name: str) -> str:
    """식당의 오늘 예약 가능 상태를 확인합니다.

    Args:
        restaurant_name: 확인할 식당 이름 (트라토리아 벨라, 한우명가, 르 비스트로, 스시 오마카세 하루)
    """
    status = {
        "트라토리아 벨라": "오늘 19:00 2인 테이블 예약 가능 (남은 테이블 3)",
        "한우명가": "오늘 저녁 예약 마감 — 내일 18:00부터 가능",
        "르 비스트로": "오늘 20:00 창가 2인석 예약 가능 (기념일 코스 제공)",
        "스시 오마카세 하루": "오늘 예약 대기 2팀 — 취소 알림 신청 가능",
    }
    return status.get(
        restaurant_name,
        f"{restaurant_name}: 조회 목록에 없는 식당입니다. 가능한 값: {', '.join(status.keys())}",
    )

@app.entrypoint
async def invoke(payload):
    """AgentCore Runtime 진입점."""
    agent = Agent(
        model=BedrockModel(model_id="us.anthropic.claude-sonnet-4-6", region_name=REGION),
        system_prompt="""당신은 강남 다이닝 컨시어지 AI입니다.
식당 추천과 예약 문의를 처리합니다.
예약 가능 상태를 확인할 때는 check_reservations 도구를 사용하세요.
한국어로 답변하고, 마지막에 대안 식당을 한 곳 제안합니다.""",
        tools=[check_reservations],
    )

    stream = agent.stream_async(payload.get("prompt"))
    async for event in stream:
        if "data" in event and isinstance(event["data"], str):
            yield event["data"]

if __name__ == "__main__":
    app.run()