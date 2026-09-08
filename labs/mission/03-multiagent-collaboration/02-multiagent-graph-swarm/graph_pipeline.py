# graph_pipeline.py — Option A: Graph 조건 분기 파이프라인
#
# 검색 → 리뷰 → 코스 구성 → 검증 순으로 흐르되, 검증 노드가 예산 초과를
# 판정하면 검색 노드로 되돌아가 재검색합니다(조건 엣지로 배타 분기).
import re

from strands import Agent
from strands.models import BedrockModel
from strands.multiagent.graph import GraphBuilder

from tools import estimate_cost, get_menu, search_restaurants

REGION = "us-west-2"
MODEL_ID = "us.anthropic.claude-sonnet-4-6"

model = BedrockModel(model_id=MODEL_ID, region_name=REGION)

search_node_agent = Agent(
    model=model,
    name="search_node",
    tools=[search_restaurants],
    system_prompt=(
        "당신은 검색 담당입니다. search_restaurants 도구로 조건에 맞는 "
        "식당을 찾아 이름 목록을 제시하세요. 만약 이전에 예산 초과로 "
        "재검색 요청을 받았다면, 더 저렴한 예산 조건(max_budget을 낮춰서)으로 "
        "다시 검색하세요."
    ),
    callback_handler=None,
)

review_node_agent = Agent(
    model=model,
    name="review_node",
    tools=[get_menu],
    system_prompt=(
        "당신은 리뷰 담당입니다. 이전 검색 결과로 나온 식당들의 메뉴를 "
        "get_menu로 조회하고, 평점·특징을 정리해 코스 구성에 참고할 수 있게 "
        "요약하세요."
    ),
    callback_handler=None,
)

course_node_agent = Agent(
    model=model,
    name="course_node",
    tools=[estimate_cost],
    system_prompt=(
        "당신은 코스 구성 담당입니다. 검색·리뷰 결과를 바탕으로 회식 코스를 "
        "짜고, estimate_cost로 인원수에 따른 예상 총 비용을 계산해 명시하세요. "
        "응답에 반드시 '총 예상 비용: N원' 형식의 문구를 포함하세요."
    ),
    callback_handler=None,
)

validate_node_agent = Agent(
    model=model,
    name="validate_node",
    system_prompt=(
        "당신은 예산 검증 담당입니다. 코스 구성 결과에서 총 예상 비용과 "
        "사용자가 요청한 예산을 비교하세요. 예산을 초과하면 응답 맨 앞에 "
        "정확히 'BUDGET_EXCEEDED'라고 쓰고 이유를 설명하세요. 예산 이내면 "
        "'BUDGET_OK'라고 쓰고 최종 코스를 정리해 확정하세요."
    ),
    callback_handler=None,
)


def _validate_result_text(state) -> str:
    result = state.results.get("validate")
    if not result:
        return ""
    agent_results = result.get_agent_results()
    if not agent_results:
        return ""
    return str(agent_results[-1])


def is_budget_exceeded(state) -> bool:
    return _validate_result_text(state).strip().startswith("BUDGET_EXCEEDED")


def is_budget_ok(state) -> bool:
    return not is_budget_exceeded(state)


def build_graph():
    builder = GraphBuilder()

    builder.add_node(search_node_agent, node_id="search")
    builder.add_node(review_node_agent, node_id="review")
    builder.add_node(course_node_agent, node_id="course")
    builder.add_node(validate_node_agent, node_id="validate")

    builder.add_edge("search", "review")
    builder.add_edge("review", "course")
    builder.add_edge("course", "validate")

    # 배타 분기: 예산 초과면 검색으로 재순환, 예산 이내면 종료(엣지 없음 = 흐름 종료)
    builder.add_edge("validate", "search", condition=is_budget_exceeded)

    # 무한 루프 방지 상한
    builder.set_max_node_executions(8)
    builder.set_execution_timeout(120)
    builder.set_entry_point("search")

    return builder.build()


if __name__ == "__main__":
    graph = build_graph()
    task = "8명 팀 회식, 1인 예산 3만원. 강남역 근처로 코스를 짜 주세요."

    result = graph(task)

    print("=== 실행 순서 ===")
    for node in result.execution_order:
        print(f"- {node.node_id}")

    print("\n=== 각 노드 결과 ===")
    for node_id, node_result in result.results.items():
        agent_results = node_result.get_agent_results()
        text = str(agent_results[-1]) if agent_results else ""
        print(f"\n--- {node_id} ---")
        print(text[:500])
