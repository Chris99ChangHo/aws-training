# orchestrator.py — agents-as-tools 오케스트레이터
from strands import Agent, tool
from strands.models import BedrockModel

from agents import menu_agent, reservation_agent, search_agent

REGION = "us-west-2"
MODEL_ID = "us.anthropic.claude-sonnet-4-6"

#      위임이 일어날 때마다 전문가 이름이 쌓이는 전역 로그.
#      Streamlit app.py가 매 요청 전에 비우고, 응답 후 읽어 라벨로 표시합니다.
delegation_log: list[str] = []


@tool
def ask_search_expert(query: str) -> str:
    """식당 검색(지역·요리 종류·예산 조건)이 필요할 때 검색 전문가에게 위임합니다.

    Args:
        query: 검색 전문가에게 전달할 질문.

    Returns:
        검색 전문가의 응답.
    """
    print(f"[위임] 검색 전문가에게 위임 — 이유: 식당 검색 요청 감지 | 질문: {query}")
    delegation_log.append("검색 전문가")
    return str(search_agent(query))


@tool
def ask_menu_expert(query: str) -> str:
    """메뉴 조회나 비용 추정이 필요할 때 메뉴 전문가에게 위임합니다.

    Args:
        query: 메뉴 전문가에게 전달할 질문.

    Returns:
        메뉴 전문가의 응답.
    """
    print(f"[위임] 메뉴 전문가에게 위임 — 이유: 메뉴/비용 관련 요청 감지 | 질문: {query}")
    delegation_log.append("메뉴 전문가")
    return str(menu_agent(query))


@tool
def ask_reservation_expert(query: str) -> str:
    """예약 가능 여부 확인이나 예약 생성이 필요할 때 예약 전문가에게 위임합니다.

    Args:
        query: 예약 전문가에게 전달할 질문.

    Returns:
        예약 전문가의 응답.
    """
    print(f"[위임] 예약 전문가에게 위임 — 이유: 예약 관련 요청 감지 | 질문: {query}")
    delegation_log.append("예약 전문가")
    return str(reservation_agent(query))


model = BedrockModel(model_id=MODEL_ID, region_name=REGION)

orchestrator = Agent(
    model=model,
    tools=[ask_search_expert, ask_menu_expert, ask_reservation_expert],
    system_prompt=(
        "당신은 강남 다이닝 컨시어지 오케스트레이터입니다. 사용자의 요청을 "
        "분석해 검색/메뉴·비용/예약 중 적절한 전문가 도구에 위임하세요. "
        "복합 요청(예: 회식 코스 계획)은 필요한 전문가들을 순서대로 여러 번 "
        "호출해 정보를 모은 뒤 하나의 통합된 답변으로 정리하세요."
    ),
    callback_handler=None,
)


if __name__ == "__main__":
    print("=== 질문 1: 검색형 ===")
    print(orchestrator("강남역 근처 가성비 좋은 중식당 추천해 주세요"))

    print("\n=== 질문 2: 복합형(메뉴+예약 포함 코스 계획) ===")
    print(orchestrator("8명 팀 회식 코스를 짜 주세요. 예산은 총 40만원입니다."))
