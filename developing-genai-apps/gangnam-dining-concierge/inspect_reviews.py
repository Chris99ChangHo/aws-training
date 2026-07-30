"""리뷰 MCP 서버 도구 스키마 확인 스크립트.

review_server.py에 stdio로 연결해 list_tools()로 도구 이름, 설명,
파라미터(필수 여부)를 출력한다. 서버에 도구가 의도한 대로 등록됐는지
확인하는 용도다.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters, stdio_client

# 실행 위치(cwd)가 아니라 이 스크립트 위치를 기준으로 서버 경로를 잡는다.
_REVIEW_SERVER_PATH = Path(__file__).parent / "review_server.py"


async def inspect_tools() -> None:
    """리뷰 MCP 서버에 연결해 도구 스키마를 조회하고 출력한다."""
    # sys.executable로 현재 가상환경의 인터프리터를 그대로 재사용한다.
    server_params = StdioServerParameters(
        command=sys.executable, args=[str(_REVIEW_SERVER_PATH)]
    )

    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            tools_result = await session.list_tools()

            for tool in tools_result.tools:
                print(f"도구 이름: {tool.name}")
                print(f"설명: {tool.description}")

                input_schema = tool.inputSchema or {}
                properties = input_schema.get("properties", {})
                required_params = set(input_schema.get("required", []))

                print("파라미터:")
                for param_name, param_info in properties.items():
                    param_type = param_info.get("type", "unknown")
                    is_required = "필수" if param_name in required_params else "선택"
                    print(f"  - {param_name}: {param_type} ({is_required})")
                print()


if __name__ == "__main__":
    asyncio.run(inspect_tools())
