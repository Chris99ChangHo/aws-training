# agents.py — 전문가 에이전트 3개
from strands import Agent
from strands.models import BedrockModel

from tools import check_reservations, create_reservation, estimate_cost, get_menu, search_restaurants

REGION = "us-west-2"
MODEL_ID = "us.anthropic.claude-sonnet-4-6"

model = BedrockModel(model_id=MODEL_ID, region_name=REGION)

search_agent = Agent(
    model=model,
    tools=[search_restaurants],
    system_prompt=(
        "당신은 강남 다이닝 검색 전문가입니다. 지역, 요리 종류, 예산 조건으로 "
        "식당을 검색하는 데만 집중하세요. search_restaurants 도구를 사용해 "
        "조건에 맞는 식당 목록을 간결하게 정리해 답하세요."
    ),
    callback_handler=None,
)

menu_agent = Agent(
    model=model,
    tools=[get_menu, estimate_cost],
    system_prompt=(
        "당신은 메뉴·비용 전문가입니다. get_menu로 대표 메뉴를 조회하고, "
        "estimate_cost로 인원 수에 따른 예상 비용을 계산하는 데 집중하세요. "
        "가격 정보를 표로 정리해 명확하게 답하세요."
    ),
    callback_handler=None,
)

reservation_agent = Agent(
    model=model,
    tools=[check_reservations, create_reservation],
    system_prompt=(
        "당신은 예약 전문가입니다. check_reservations로 예약 가능 여부를 "
        "확인하고, 요청 시 create_reservation으로 예약을 확정하는 데 집중하세요. "
        "예약 상태를 명확하고 간결하게 답하세요."
    ),
    callback_handler=None,
)


if __name__ == "__main__":
    print("=== 검색 전문가 ===")
    print(search_agent("강남역 근처 가성비 좋은 중식당 추천해 주세요"))

    print("\n=== 메뉴 전문가 ===")
    print(menu_agent("한우명가 메뉴랑 4명 기준 예상 비용 알려주세요"))

    print("\n=== 예약 전문가 ===")
    print(reservation_agent("트라토리아 벨라 내일 저녁 7시에 2명 예약 가능한가요?"))
