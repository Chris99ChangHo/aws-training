# agent.py — Streamlit 앱용 에이전트 모듈
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


def create_agent(session_id: str, callback_handler=None) -> tuple[Agent, MCPClient]:
    """세션 ID로 다이닝 컨시어지 에이전트를 생성합니다.

    Args:
        session_id: 대화 히스토리를 유지할 세션 식별자.
        callback_handler: 도구 사용 등 실행 이벤트를 받을 콜백(Streamlit 로그 수집용).

    Returns:
        (agent, mcp_client) 튜플. mcp_client는 호출부에서 `with`로 열어둔 채
        agent를 사용해야 합니다(도구 목록이 그 컨텍스트에서 로드되기 때문).
    """
    model = BedrockModel(model_id=MODEL_ID, region_name=REGION)
    reservation_mcp = MCPClient(
        lambda: stdio_client(StdioServerParameters(command=sys.executable, args=["mcp_server.py"]))
    )
    session_manager = FileSessionManager(session_id=session_id, storage_dir="./sessions")
    conversation_manager = SlidingWindowConversationManager(window_size=10)

    reservation_mcp.start()
    mcp_tools = reservation_mcp.list_tools_sync()

    agent = Agent(
        model=model,
        tools=[search_restaurants, get_menu, *mcp_tools],
        system_prompt=(
            "당신은 강남 다이닝 컨시어지입니다. 사용자의 요청에 따라 "
            "식당 검색, 메뉴 조회, 예약 가능 여부 확인 도구를 활용해 "
            "정확하고 친절하게 답변하세요."
        ),
        session_manager=session_manager,
        conversation_manager=conversation_manager,
        callback_handler=callback_handler,
    )
    return agent, reservation_mcp


if __name__ == "__main__":
    # 단독 호출 테스트: create_agent()가 정상 생성되는지 확인
    agent, mcp_client = create_agent(session_id="strands-app-test")
    try:
        response = agent("강남역 근처 이탈리안 식당 추천해 주세요")
        print(response)
    finally:
        mcp_client.stop(None, None, None)
