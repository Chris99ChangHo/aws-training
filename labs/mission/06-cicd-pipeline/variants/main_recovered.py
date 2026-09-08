# main_recovered.py — 복구 + 개선 버전
#
# 사용법: 이 파일 내용을 DiningConcierge/app/DiningConcierge/main.py에
# 덮어쓰고 재업로드하면, 추측 금지 규칙이 되살아나 게이트를 다시 통과하고
# (평균 0.7 이상), 추가로 식당 추천 시 가격대·위치를 함께 안내하는 개선이
# 적용됩니다.
from typing import Any
from collections import OrderedDict
from strands import Agent, tool
import asyncio
from strands.agent.conversation_manager.null_conversation_manager import NullConversationManager
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from model.load import load_model

app = BedrockAgentCoreApp()
log = app.logger

# ✅ 복구: 추측 금지 규칙 되살림 + 개선: 가격대·위치 안내 규칙 추가
DEFAULT_SYSTEM_PROMPT = """\
당신은 강남 다이닝 컨시어지 AI 어시스턴트입니다. 강남 일대 식당 추천, 메뉴 안내,
예약 문의를 도와줍니다. 모르는 정보는 추측하지 말고 "확인 후 안내하겠습니다"라고
답하세요. 식당을 추천할 때는 반드시 가격대와 위치를 함께 안내하세요.
"""


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
        "name": "매콤한 마라",
        "cuisine": "중식",
        "location": "강남역",
        "price_range": "2~3만원",
        "rating": 4.3,
        "spice_level": "아주 매움",
        "menu": [
            {"item": "마라탕", "price": 12000},
            {"item": "마라샹궈", "price": 25000},
        ],
    },
]


@tool
def search_restaurants(location: str = "", cuisine: str = "") -> str:
    """조건(지역, 요리 종류)에 맞는 강남 일대 식당을 검색합니다."""
    results = [
        r
        for r in RESTAURANTS
        if (not location or location in r["location"])
        and (not cuisine or cuisine in r["cuisine"])
    ]
    if not results:
        return "조건에 맞는 식당을 찾지 못했습니다."
    lines = []
    for r in results:
        line = (
            f"- {r['name']} ({r['cuisine']}, {r['location']}) "
            f"가격대 {r['price_range']}, 평점 {r['rating']}"
        )
        if r.get("spice_level"):
            line += f", 맵기: {r['spice_level']}"
        lines.append(line)
    return "\n".join(lines)


@tool
def get_menu(restaurant_name: str) -> str:
    """식당 이름으로 대표 메뉴와 가격을 조회합니다."""
    for r in RESTAURANTS:
        if r["name"] == restaurant_name:
            lines = [f"{m['item']} — {m['price']:,}원" for m in r["menu"]]
            return f"{restaurant_name} 대표 메뉴:\n" + "\n".join(lines)
    return f"'{restaurant_name}'을 찾을 수 없습니다."


tools = [search_restaurants, get_menu]

_INLINE_FUNCTION_NAMES = set()


def _make_conversation_manager():
    return NullConversationManager()


def agent_factory():
    cache = OrderedDict()

    def get_or_create_agent(session_id):
        if session_id in cache:
            cache.move_to_end(session_id)
            return cache[session_id]
        if len(cache) >= 128:
            cache.popitem(last=False)
        cache[session_id] = Agent(
            model=load_model(),
            system_prompt=DEFAULT_SYSTEM_PROMPT,
            tools=tools,
            conversation_manager=_make_conversation_manager(),
            hooks=[],
        )
        return cache[session_id]

    return get_or_create_agent


get_or_create_agent = agent_factory()


def _extract_prompt(payload: dict):
    if "messages" in payload:
        return payload["messages"]
    if "tool_results" in payload:
        return [{"role": "user", "content": [{"toolResult": {
            "toolUseId": tr["toolUseId"],
            "status": tr.get("status", "success"),
            "content": tr.get("content", []),
        }} for tr in payload["tool_results"]]}]
    return payload.get("prompt", "")


@app.entrypoint
async def invoke(payload, context):
    log.info("Invoking Agent.....")
    session_id = getattr(context, "session_id", "default-session")
    agent = get_or_create_agent(session_id)
    prompt = _extract_prompt(payload)

    async for event in agent.stream_async(prompt):
        if not isinstance(event, dict) or "event" not in event:
            continue
        cbs = event["event"].get("contentBlockStart")
        if cbs is not None and not cbs.get("start"):
            continue
        yield event


if __name__ == "__main__":
    app.run()
