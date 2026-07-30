"""@tool + MCPClient 혼합 — 외부 검색 + 로컬 예약 조합."""
from strands import Agent, tool
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient
from mcp.client.stdio import stdio_client
from mcp import StdioServerParameters
import random

REGION = "us-west-2"

# MCP 서버에서 검색 도구를 가져옴
mcp = MCPClient(
    lambda: stdio_client(
        StdioServerParameters(command="python", args=["restaurant_server.py"])
    )
)

# 로컬 @tool — 예약은 내부 시스템이라 MCP로 분리하지 않음
@tool
def create_reservation(restaurant_name: str, date: str, time: str, party_size: int) -> str:
    """식당 예약을 생성합니다.

    Args:
        restaurant_name: 식당 이름
        date: 예약 날짜 (YYYY-MM-DD)
        time: 예약 시간 (HH:MM)
        party_size: 인원 수
    """
    reservation_id = f"RSV-{random.randint(10000, 99999)}"
    return (
        f"✅ 예약 완료!\n"
        f"  예약번호: {reservation_id}\n"
        f"  식당: {restaurant_name}\n"
        f"  일시: {date} {time}\n"
        f"  인원: {party_size}명"
    )

# tools 리스트에 MCP와 @tool을 함께 전달
agent = Agent(
    model=BedrockModel(model_id="us.anthropic.claude-sonnet-4-6", region_name=REGION),
    system_prompt="""식당 컨시어지입니다.
- 검색은 MCP 서버 도구를 사용합니다.
- 예약은 create_reservation 도구를 사용합니다.
- 한국어로 답변합니다.""",
    tools=[mcp, create_reservation],
    callback_handler=None,  # 스트리밍 콜백 끄기 — print 결과만 출력
)

response = agent(
    "강남역 이탈리안 검색하고, 가장 평점 높은 곳으로 "
    "내일(2026-07-26) 저녁 7시에 2명 예약해 주세요. 이름은 김민수."
)
print(response) 

# 도구 소스 확인 — Agent가 이미 로드해 둔 tool_registry에서 조회 (MCP 세션을 또 열면 충돌 발생)
print("\n📋 에이전트에 등록된 도구:")
print("  [MCP 서버]")
for tool_spec in agent.tool_registry.get_all_tool_specs():
    if tool_spec["name"] != "create_reservation":
        print(f"    🔧 {tool_spec['name']}")
print("  [로컬 @tool]")
print("    🔧 create_reservation")