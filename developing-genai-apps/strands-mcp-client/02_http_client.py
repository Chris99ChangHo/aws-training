"""Streamable HTTP로 원격 MCP 서버에 연결합니다."""
from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient
from mcp.client.streamable_http import streamable_http_client

REGION = "us-west-2"

# Streamable HTTP로 원격 MCP 서버에 연결
mcp = MCPClient(
    lambda: streamable_http_client(
        url="http://127.0.0.1:8000/mcp"
    )
)

agent = Agent(
    model=BedrockModel(model_id="us.anthropic.claude-sonnet-4-6", region_name=REGION),
    system_prompt="식당 컨시어지입니다. MCP 도구를 사용합니다. 한국어로 답변합니다.",
    tools=[mcp],
    callback_handler=None,  # 스트리밍 콜백 끄기 — print 결과만 출력
)

response = agent("역삼역 한식 추천해 주세요")
print(response)