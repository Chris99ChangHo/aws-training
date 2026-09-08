# agent.py — @tool + MCP 통합 에이전트
import sys

from mcp import StdioServerParameters, stdio_client
from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient

from tools import get_menu, search_restaurants

REGION = "us-west-2"
MODEL_ID = "us.anthropic.claude-sonnet-4-6"

model = BedrockModel(model_id=MODEL_ID, region_name=REGION)

#      "python"이 PATH에 없는 환경(예: macOS 기본)도 있어 현재 인터프리터(sys.executable)를 사용합니다
reservation_mcp = MCPClient(
    lambda: stdio_client(StdioServerParameters(command=sys.executable, args=["mcp_server.py"]))
)


def main():
    with reservation_mcp:
        mcp_tools = reservation_mcp.list_tools_sync()

        agent = Agent(
            model=model,
            tools=[search_restaurants, get_menu, *mcp_tools],
            system_prompt=(
                "당신은 강남 다이닝 컨시어지입니다. 사용자의 요청에 따라 "
                "식당 검색, 메뉴 조회, 예약 가능 여부 확인 도구를 순서대로 "
                "활용해 정확하고 친절하게 답변하세요."
            ),
            #      기본 콜백이 토큰을 스트리밍 출력하므로 끄고 최종 결과만 print
            callback_handler=None,
        )

        question = "내일 저녁 7시에 2명이 갈 만한 강남역 이탈리안 식당 찾고, 예약 가능한지 확인해 주세요"
        response = agent(question)
        print(response)


if __name__ == "__main__":
    main()
