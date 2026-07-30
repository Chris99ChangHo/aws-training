도전 과제 2

여러 MCP 서버 연결: 식당 검색 서버 + 리뷰 서버 2개를 동시에 연결해보세요. tools=[mcp1, mcp2, @tool함수] 패턴입니다.
Streamable HTTP 인증: httpx.AsyncClient(headers={"Authorization": "Bearer <API_KEY>"})를 만들어 streamable_http_client(url, http_client=...)로 주입하는 방식으로 인증을 구현해보세요.
AgentCore Gateway 연결: AgentCore Gateway에 MCP 서버를 등록하고 MCPClient로 연결해보세요. (→ AgentCore Gateway 실습에서 상세히 다룹니다)
