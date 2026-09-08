# agent.py — 세션 영속화 에이전트
import sys

from mcp import StdioServerParameters, stdio_client
from strands import Agent
from strands.agent.conversation_manager import SlidingWindowConversationManager
from strands.models import BedrockModel
from strands.session import FileSessionManager
from strands.tools.mcp import MCPClient

from tools import get_menu, search_restaurants

REGION = "us-west-2"
MODEL_ID = "us.anthropic.claude-sonnet-4-6"

model = BedrockModel(model_id=MODEL_ID, region_name=REGION)

reservation_mcp = MCPClient(
    lambda: stdio_client(StdioServerParameters(command=sys.executable, args=["mcp_server.py"]))
)

session_manager = FileSessionManager(session_id="dining-session-001", storage_dir="./sessions")
conversation_manager = SlidingWindowConversationManager(window_size=10)


def build_agent():
    """MCP 클라이언트를 연 상태에서 세션 영속화 에이전트를 생성합니다."""
    mcp_tools = reservation_mcp.list_tools_sync()
    return Agent(
        model=model,
        tools=[search_restaurants, get_menu, *mcp_tools],
        system_prompt=(
            "당신은 강남 다이닝 컨시어지입니다. 사용자의 요청에 따라 "
            "식당 검색, 메뉴 조회, 예약 가능 여부 확인 도구를 활용해 "
            "정확하고 친절하게 답변하세요."
        ),
        session_manager=session_manager,
        conversation_manager=conversation_manager,
        callback_handler=None,
    )


if __name__ == "__main__":
    with reservation_mcp:
        agent = build_agent()
        response = agent("강남역 근처 데이트하기 좋은 식당 추천해 주세요")
        print(response)
