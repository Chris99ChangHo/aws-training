"""stdio로 로컬 MCP 서버에 연결합니다."""
from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient
from mcp.client.stdio import stdio_client
from mcp import StdioServerParameters

REGION = "us-west-2"

# MCPClient 생성 — transport factory(callable)를 전달
mcp = MCPClient(
    lambda: stdio_client(
        StdioServerParameters(
            command="python",
            args=["restaurant_server.py"]
        )
    )
)

# Managed 방식 — Agent가 MCP 세션의 열기/닫기를 자동 관리
agent = Agent(
    model=BedrockModel(model_id="us.anthropic.claude-sonnet-4-6", region_name=REGION),
    system_prompt="식당 컨시어지입니다. MCP 도구를 사용하여 식당을 검색합니다. 한국어로 답변합니다.",
    tools=[mcp],
    callback_handler=None,  # 스트리밍 콜백 끄기 — print 결과만 출력
)

# 에이전트에게 질문 — MCP 서버의 도구를 자동 호출
response = agent("강남역 이탈리안 추천해 주세요. 1인 6만원 이하로.")
print(response)

# 도구 자동 발견 — Agent가 MCP에서 로드한 도구 목록 확인
print("\n📋 MCP 서버에서 발견한 도구:")
for tool_spec in agent.tool_registry.get_all_tool_specs():
    description = tool_spec["description"].splitlines()[0]
    print(f"  🔧 {tool_spec['name']}: {description}")