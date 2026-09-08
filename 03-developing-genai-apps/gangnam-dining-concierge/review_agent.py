"""리뷰 MCP 서버를 연결한 강남 식당 컨시어지 에이전트.

review_server.py가 노출하는 restaurant_reviews 도구를 MCPClient로
연결해, 자연어 질의에 도구가 자동 호출되는지 확인한다.
"""

from __future__ import annotations

import sys
from pathlib import Path

from mcp import StdioServerParameters, stdio_client
from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient

REGION = "us-west-2"
MODEL_ID = "us.anthropic.claude-sonnet-4-6"

# 실행 위치(cwd)가 아니라 이 스크립트 위치를 기준으로 서버 경로를 잡는다.
# 리포 루트에서 실행해도 깨지지 않게 하기 위함이다.
_REVIEW_SERVER_PATH = Path(__file__).parent / "review_server.py"

review_mcp_client = MCPClient(
    lambda: stdio_client(
        # sys.executable을 쓰면 현재 가상환경의 인터프리터를 그대로
        # 재사용한다. "python"은 PATH에 없거나 다른 버전을 가리킬 수 있다.
        StdioServerParameters(
            command=sys.executable, args=[str(_REVIEW_SERVER_PATH)]
        )
    )
)


def main() -> None:
    """리뷰 MCP 서버에 연결한 에이전트를 만들고 질의를 실행한다."""
    model = BedrockModel(model_id=MODEL_ID, region_name=REGION)

    with review_mcp_client:
        tools = review_mcp_client.list_tools_sync()

        agent = Agent(
            model=model,
            tools=tools,
            system_prompt="당신은 강남 식당 컨시어지입니다. 한국어로 답변합니다.",
            callback_handler=None,
        )

        query = "트라토리아 벨라 리뷰 어때요? 평점도 알려 주세요"
        print(f"[질의] {query}\n")
        result = agent(query)
        print(f"[응답]\n{result}")


if __name__ == "__main__":
    main()
