# dining_agent_memory.py — Memory 연동 강남 식당 추천 에이전트
import os

from strands import Agent, tool
from strands.models import BedrockModel
from bedrock_agentcore.memory.integrations.strands.config import (
    AgentCoreMemoryConfig,
    RetrievalConfig,
)
from bedrock_agentcore.memory.integrations.strands.session_manager import (
    AgentCoreMemorySessionManager,
)

REGION = "us-west-2"
# 04번 미션에서 생성한 Memory ID·Semantic 전략 ID를 환경변수로 주입한다:
#   MEMORY_ID="dining_memory-..." SEMANTIC_STRATEGY_ID="semantic_builtin_..." \
#     python3 dining_agent_memory.py
MEMORY_ID = os.environ.get("MEMORY_ID", "<YOUR_MEMORY_ID>")
SEMANTIC_STRATEGY_ID = os.environ.get("SEMANTIC_STRATEGY_ID", "<YOUR_SEMANTIC_STRATEGY_ID>")

# --- 도구 ---
@tool
def search_restaurants(location: str, cuisine: str) -> str:
    """식당을 검색합니다."""
    data = {
        "이탈리안": "트라토리아 벨라 (강남역 3분, 45,000원, ★4.5)",
        "한식": "한우명가 (역삼역 5분, 65,000원, ★4.3)",
        "프렌치": "르 비스트로 (압구정역 2분, 90,000원, ★4.6)",
    }
    return data.get(cuisine, f"{cuisine} 식당을 찾지 못했습니다.")

# --- 에이전트 생성 함수 — session_id/actor_id를 바꿔 끼울 수 있게 ---
def create_agent(session_id: str, actor_id: str = "user-001") -> Agent:
    #      키 = 검색할 네임스페이스(빌트인 기본형: /strategy/{전략ID}/actors/{actorId}/)
    #      {actorId}는 실행 시 actor_id 값으로 자동 치환됩니다
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
    return Agent(
        model=BedrockModel(model_id="us.anthropic.claude-sonnet-4-6"),
        system_prompt="강남 식당 추천 전문가. 사용자의 이전 취향을 기억해 반영합니다.",
        tools=[search_restaurants],
        session_manager=session_manager,  # ← Memory 연결
        callback_handler=None,  # 스트리밍 중간 출력 억제 — 최종 print만 표시
    )

if __name__ == "__main__":
    agent = create_agent(session_id="session-dining-000")
    print(agent("강남에서 어떤 식당을 추천해 줄 수 있나요?"))