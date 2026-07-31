# `MCPClient` 생성 패턴

`MCPClient`는 트랜스포트 객체나 URL이 아니라 **트랜스포트를 만드는
callable**을 받는다. 클라이언트가 세션을 다시 열 때 트랜스포트를 새로
만들 수 있어야 하기 때문이다.

```python
# ✅ 올바른 패턴 — transport factory callable
MCPClient(lambda: stdio_client(StdioServerParameters(...)))
MCPClient(lambda: streamable_http_client(url="https://.../mcp"))

# ❌ 잘못된 패턴 — url= 키워드 인자는 없다
MCPClient(url="https://...")
```

## stdio 서버 경로 주의

`StdioServerParameters`에 서버 스크립트를 넘길 때 두 값을 실행 환경에
의존하지 않게 잡는다.

```python
import sys
from pathlib import Path

StdioServerParameters(
    command=sys.executable,  # "python"은 PATH에 없을 수 있다
    args=[str(Path(__file__).parent / "restaurant_server.py")],  # cwd 무관
)
```
