from datetime import datetime, timezone

import boto3
from strands import Agent, tool
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient
from mcp_proxy_for_aws.client import aws_iam_streamablehttp_client
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from bedrock_agentcore.memory.integrations.strands.config import (
    AgentCoreMemoryConfig,
    RetrievalConfig,
)
from bedrock_agentcore.memory.integrations.strands.session_manager import (
    AgentCoreMemorySessionManager,
)
from model.load import load_model

app = BedrockAgentCoreApp()
log = app.logger

REGION = "us-west-2"
GATEWAY_URL = "https://dining-gateway-jpfmqyvlti.gateway.bedrock-agentcore.us-west-2.amazonaws.com/mcp"
MEMORY_ID = "dining_memory-SZxGDnAT4j"
SEMANTIC_STRATEGY_ID = "semantic_builtin_yzwcl-Cb9E4o4096"

RESERVATIONS_TABLE = "dining-reservations"
_dynamodb = boto3.resource("dynamodb", region_name=REGION)
_reservations_table = _dynamodb.Table(RESERVATIONS_TABLE)

DEFAULT_SYSTEM_PROMPT = """당신은 강남 다이닝 컨시어지 AI입니다. 사용자의 이전 취향을 기억해 반영합니다.
search_restaurants와 get_menu 도구로 식당을 검색하고, Gateway의 search_knowledge_base로 상세 정보를 검색할 수 있습니다.
사용자가 예약을 원하면 make_reservation 도구로 예약을 생성하세요."""


RESTAURANTS = [
    {
        "name": "트라토리아 벨라",
        "cuisine": "이탈리안",
        "location": "강남역",
        "price_range": "3~6만원",
        "rating": 4.5,
        "menu": [
            {"item": "까르보나라", "price": 22000},
            {"item": "마르게리타 피자", "price": 25000},
        ],
    },
    {
        "name": "스시 오마카세 하루",
        "cuisine": "일식",
        "location": "강남역",
        "price_range": "6~9만원",
        "rating": 4.7,
        "menu": [
            {"item": "런치 오마카세", "price": 60000},
            {"item": "디너 오마카세", "price": 90000},
        ],
    },
    {
        "name": "한우명가",
        "cuisine": "한식",
        "location": "역삼역",
        "price_range": "4.5~7만원",
        "rating": 4.6,
        "menu": [
            {"item": "한우 등심", "price": 55000},
            {"item": "갈비탕", "price": 18000},
        ],
    },
    {
        "name": "르 비스트로",
        "cuisine": "프렌치",
        "location": "압구정역",
        "price_range": "5~8만원",
        "rating": 4.6,
        "menu": [
            {"item": "스테이크 프리츠", "price": 48000},
            {"item": "코스 메뉴", "price": 80000},
        ],
    },
    {
        "name": "매콤한 마라",
        "cuisine": "중식",
        "location": "강남역",
        "price_range": "2~3만원",
        "rating": 4.3,
        "menu": [
            {"item": "마라탕", "price": 12000},
            {"item": "마라샹궈", "price": 25000},
        ],
    },
]


@tool
def search_restaurants(location: str = "", cuisine: str = "") -> str:
    """조건(지역, 요리 종류)에 맞는 강남 일대 식당을 검색합니다.

    Args:
        location: 검색할 지역명(예: "강남역"). 비워두면 지역 조건 없이 검색합니다.
        cuisine: 검색할 요리 종류(예: "이탈리안"). 비워두면 요리 종류 조건 없이 검색합니다.

    Returns:
        조건에 맞는 식당들의 이름/요리 종류/지역/가격대/평점을 정리한 문자열.
    """
    results = [
        r
        for r in RESTAURANTS
        if (not location or location in r["location"])
        and (not cuisine or cuisine in r["cuisine"])
    ]
    if not results:
        return "조건에 맞는 식당을 찾지 못했습니다."
    lines = [
        f"- {r['name']} ({r['cuisine']}, {r['location']}) 가격대 {r['price_range']}, 평점 {r['rating']}"
        for r in results
    ]
    return "\n".join(lines)


@tool
def get_menu(restaurant_name: str) -> str:
    """식당 이름으로 대표 메뉴와 가격을 조회합니다.

    Args:
        restaurant_name: 조회할 식당의 정확한 이름(예: "트라토리아 벨라").

    Returns:
        대표 메뉴와 가격을 정리한 문자열. 식당을 찾지 못하면 안내 문자열.
    """
    for r in RESTAURANTS:
        if r["name"] == restaurant_name:
            lines = [f"{m['item']} — {m['price']:,}원" for m in r["menu"]]
            return f"{restaurant_name} 대표 메뉴:\n" + "\n".join(lines)
    return f"'{restaurant_name}'을 찾을 수 없습니다."


@tool
def make_reservation(restaurant_name: str, date: str, time: str, party_size: int) -> str:
    """식당 예약을 생성합니다.

    Args:
        restaurant_name: 예약할 식당 이름(예: "트라토리아 벨라").
        date: 예약 날짜(예: "2026-08-10").
        time: 예약 시간(예: "19:00").
        party_size: 인원 수.

    Returns:
        예약 확인 메시지.
    """
    known = {r["name"] for r in RESTAURANTS}
    if restaurant_name not in known:
        return f"'{restaurant_name}'은 카탈로그에 없는 식당입니다."

    now = datetime.now(timezone.utc).isoformat()
    item = {
        "actor_id": "user-001",
        "reserved_at": now,
        "restaurant": restaurant_name,
        "date": date,
        "time": time,
        "party_size": party_size,
        "status": "confirmed",
    }
    _reservations_table.put_item(Item=item)
    return f"✅ 예약 완료: {restaurant_name} {date} {time} {party_size}명"


local_tools = [search_restaurants, get_menu, make_reservation]


@app.entrypoint
def invoke(payload):
    log.info("Invoking Agent.....")

    session_id = payload.get("session_id", "session-dining-default-000000000000")
    actor_id = payload.get("actor_id", "user-001")

    config = AgentCoreMemoryConfig(
        memory_id=MEMORY_ID,
        actor_id=actor_id,
        session_id=session_id,
        retrieval_config={
            "/strategies/" + SEMANTIC_STRATEGY_ID + "/actors/{actorId}/":
                RetrievalConfig(top_k=5, relevance_score=0.3),
        },
    )
    session_manager = AgentCoreMemorySessionManager(
        agentcore_memory_config=config,
        region_name=REGION,
    )

    gateway_client = MCPClient(
        lambda: aws_iam_streamablehttp_client(
            endpoint=GATEWAY_URL,
            aws_region=REGION,
            aws_service="bedrock-agentcore",
        )
    )
    with gateway_client:
        agent = Agent(
            model=load_model(),
            system_prompt=DEFAULT_SYSTEM_PROMPT,
            tools=gateway_client.list_tools_sync() + local_tools,
            session_manager=session_manager,
        )
        before = len(agent.messages)
        result = agent(payload.get("prompt", ""))
        tool_calls = [
            {"name": b["toolUse"]["name"], "input": b["toolUse"]["input"]}
            for m in agent.messages[before:]
            for b in m.get("content", [])
            if isinstance(b, dict) and "toolUse" in b
        ]
        return {"result": str(result), "tool_calls": tool_calls}


if __name__ == "__main__":
    app.run()
