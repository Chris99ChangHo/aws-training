# planner_engine.py — Streamlit 콜백 연동 오케스트레이터
from typing import Callable, Optional

from strands import Agent, tool
from strands.models import BedrockModel

from tools import check_reservations, create_reservation, estimate_cost, get_menu, search_restaurants

REGION = "us-west-2"
MODEL_ID = "us.anthropic.claude-sonnet-4-6"


class DiningPlannerEngine:
    """전문가 에이전트 3개(검색/메뉴/예약) + 오케스트레이터를 구성하는 엔진.

    위임이 일어날 때마다 on_delegation(agent_name, query) 콜백을 호출해
    외부(Streamlit 등)에서 위임 이벤트를 실시간으로 수집할 수 있게 합니다.
    """

    def __init__(self, on_delegation: Optional[Callable[[str, str], None]] = None):
        self.on_delegation = on_delegation
        self.model = BedrockModel(model_id=MODEL_ID, region_name=REGION)

        self.search_agent = Agent(
            model=self.model,
            tools=[search_restaurants],
            system_prompt=(
                "당신은 강남 다이닝 검색 전문가입니다. search_restaurants 도구로 "
                "조건에 맞는 식당을 찾아 간결하게 정리해 답하세요."
            ),
            callback_handler=None,
        )
        self.menu_agent = Agent(
            model=self.model,
            tools=[get_menu, estimate_cost],
            system_prompt=(
                "당신은 메뉴·비용 전문가입니다. get_menu와 estimate_cost로 "
                "메뉴와 인원별 예상 비용을 표로 정리해 답하세요."
            ),
            callback_handler=None,
        )
        self.reservation_agent = Agent(
            model=self.model,
            tools=[check_reservations, create_reservation],
            system_prompt=(
                "당신은 예약 전문가입니다. check_reservations로 예약 가능 여부를 "
                "확인하고, 필요 시 create_reservation으로 예약을 확정하세요."
            ),
            callback_handler=None,
        )

        self.orchestrator = self._build_orchestrator()

    def _notify(self, agent_name: str, query: str) -> None:
        print(f"[위임] 오케스트레이터 → {agent_name}: {query}")
        if self.on_delegation:
            self.on_delegation(agent_name, query)

    def _build_orchestrator(self) -> Agent:
        engine = self

        @tool
        def ask_search_expert(query: str) -> str:
            """식당 검색(지역·요리 종류·예산 조건)이 필요할 때 검색 전문가에게 위임합니다.

            Args:
                query: 검색 전문가에게 전달할 질문.

            Returns:
                검색 전문가의 응답.
            """
            engine._notify("검색 전문가", query)
            return str(engine.search_agent(query))

        @tool
        def ask_menu_expert(query: str) -> str:
            """메뉴 조회나 비용 추정이 필요할 때 메뉴 전문가에게 위임합니다.

            Args:
                query: 메뉴 전문가에게 전달할 질문.

            Returns:
                메뉴 전문가의 응답.
            """
            engine._notify("메뉴 전문가", query)
            return str(engine.menu_agent(query))

        @tool
        def ask_reservation_expert(query: str) -> str:
            """예약 가능 여부 확인이나 예약 생성이 필요할 때 예약 전문가에게 위임합니다.

            Args:
                query: 예약 전문가에게 전달할 질문.

            Returns:
                예약 전문가의 응답.
            """
            engine._notify("예약 전문가", query)
            return str(engine.reservation_agent(query))

        return Agent(
            model=self.model,
            tools=[ask_search_expert, ask_menu_expert, ask_reservation_expert],
            system_prompt=(
                "당신은 강남 다이닝 컨시어지 오케스트레이터입니다. 회식·기념일 코스 "
                "요청을 분석해 검색/메뉴·비용/예약 전문가에게 필요한 만큼 순서대로 "
                "위임하세요. 결과를 통합해 최종 답변에 반드시 markdown 표로 "
                "'순서 | 식당 · 메뉴 | 비용' 형식의 코스표를 포함하고, 마지막 줄에 "
                "'총 비용: N원' 형식으로 인원수 × 메뉴 예산을 합산한 총액을 "
                "명시하세요."
            ),
            callback_handler=None,
        )

    def ask(self, query: str) -> str:
        return str(self.orchestrator(query))


if __name__ == "__main__":
    events = []
    engine = DiningPlannerEngine(on_delegation=lambda name, q: events.append((name, q)))
    answer = engine.ask("8명 팀 회식 코스를 짜 주세요. 예산은 총 40만원입니다.")
    print(answer)
    print("\n=== 콜백으로 수집된 위임 이벤트 ===")
    for name, q in events:
        print(f"- {name} <- {q}")
