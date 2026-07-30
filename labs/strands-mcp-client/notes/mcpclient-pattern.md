# ✅ 올바른 패턴 — transport factory callable
MCPClient(lambda: stdio_client(StdioServerParameters(...)))

# ❌ 잘못된 패턴 — url= 키워드 인자 없음
MCPClient(url="https://...")