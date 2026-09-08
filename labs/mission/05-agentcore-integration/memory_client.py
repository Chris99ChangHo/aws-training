"""Memory 취향 조회 클라이언트."""
from __future__ import annotations

import os

from bedrock_agentcore.memory import MemoryClient

REGION = "us-west-2"
# 04번 미션에서 생성한 Memory ID·Semantic 전략 ID를 환경변수로 주입한다.
MEMORY_ID = os.environ.get("MEMORY_ID", "<YOUR_MEMORY_ID>")
SEMANTIC_STRATEGY_ID = os.environ.get("SEMANTIC_STRATEGY_ID", "<YOUR_SEMANTIC_STRATEGY_ID>")

client = MemoryClient(region_name=REGION)


def get_preferences(actor_id: str) -> list[str]:
    """actor_id의 장기 기억(취향)을 검색해 텍스트 목록으로 반환한다."""
    memories = client.retrieve_memories(
        memory_id=MEMORY_ID,
        namespace=f"/strategies/{SEMANTIC_STRATEGY_ID}/actors/{actor_id}/",
        query="고객의 음식 취향",
    )
    return [m["content"]["text"] for m in memories]


if __name__ == "__main__":
    prefs = get_preferences("user-001")
    print(f"취향 {len(prefs)}건:")
    for p in prefs:
        print(f"  - {p}")
