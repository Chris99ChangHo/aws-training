# 도전 과제 (MCP 클라이언트)

| 과제 | 내용 | 상태 |
|---|---|---|
| 여러 MCP 서버 연결 | 검색 서버 + 리뷰 서버를 동시에 연결. `tools=[mcp1, mcp2, @tool함수]` 패턴 | 리뷰 서버는 [`gangnam-dining-concierge`](../../../developing-genai-apps/gangnam-dining-concierge)에서 별도 구현 |
| Streamable HTTP 인증 | `httpx.AsyncClient(headers={"Authorization": "Bearer <API_KEY>"})`를 만들어 `streamable_http_client(url, http_client=...)`로 주입 | 미착수 |
| AgentCore Gateway 연결 | Gateway에 MCP 서버를 등록하고 `MCPClient`로 연결 | 미착수 ([`agentcore-setup`](../../agentcore-setup)은 Runtime만 다룸) |

HTTP 인증 과제는 `02_http_client.py`가 인증 없이 `127.0.0.1:8000`에
붙는 구성이라, 원격 배포로 확장할 때 반드시 선행돼야 하는 항목이다.
