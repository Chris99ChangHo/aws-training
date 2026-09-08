"""강남 다이닝 컨시어지 에이전트 모듈.

2-1의 도구(식당 검색, 메뉴 조회)와 예약 MCP 서버, 2-2의 세션 저장을
모두 통합한 에이전트 모듈. Streamlit 앱(app.py)이 build_agent()를
가져다 쓴다.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

from mcp import StdioServerParameters, stdio_client
from strands import Agent
from strands.models import BedrockModel
from strands.session.file_session_manager import FileSessionManager
from strands.tools.mcp import MCPClient

from tools import get_menu, search_restaurants

REGION = "us-west-2"
MODEL_ID = "us.anthropic.claude-sonnet-4-6"

_BASE_DIR = Path(__file__).parent
_MCP_SERVER_PATH = _BASE_DIR / "mcp_server.py"
_SESSIONS_DIR = _BASE_DIR / "sessions"
DEFAULT_SESSION_ID = "gangnam-dining-concierge-session"

SYSTEM_PROMPT_TEMPLATE = """\
당신은 강남 다이닝 컨시어지 "강남 다이닝"의 AI 식당 도우미입니다.
오늘 날짜는 {today}입니다. "내일", "이번 주말" 같은 상대 날짜 표현은
이 기준으로 계산해 "YYYY-MM-DD" 형식으로 변환한 뒤 도구에 전달하세요.

사용자의 요청에 따라 다음 순서로 도구를 사용하세요.

1. search_restaurants로 지역·음식 종류 조건에 맞는 식당을 찾습니다.
2. get_menu로 필요하면 메뉴를 확인합니다.
3. check_availability로 날짜·시간·인원에 맞는 예약 가능 여부와 남은
   좌석 수를 확인합니다.

대화 중 사용자가 밝힌 취향(매운 음식 기피, 선호 음식 종류 등)은
이후 추천에도 계속 반영하세요. "지난번에 추천받은 식당" 같은 회상
요청이 오거나 "거기 말고 X로 바꿔 주세요"처럼 이전 추천을 다른 식당
이름으로 바꿔 달라는 요청이 오면:

- 새로 지정된 식당 이름(X)으로 get_menu 또는 check_availability를
  즉시 시도해 보세요. 이전에 area/cuisine 조건으로 검색한 목록에
  없다는 이유만으로 존재하지 않는다고 단정하지 마세요 — 다른
  지역이나 음식 종류의 식당일 수 있습니다.
- 도구가 "식당을 찾지 못했다"고 응답하면 그때 사용자에게 위치나
  음식 종류를 물어보세요.

식당을 추천할 때는 예약 가능 여부를 반드시 함께 안내하세요. 예약이
불가능하면 다른 대안을 제시하세요.
"""


def build_agent(session_id: str = DEFAULT_SESSION_ID) -> Agent:
    """도구, MCP 예약 조회, 세션 영속화가 통합된 다이닝 컨시어지 에이전트를 생성한다.

    Args:
        session_id: 세션을 식별하는 고유 ID. 같은 ID로 다시 생성하면
            FileSessionManager가 이전 대화 히스토리를 복원한다.

    Returns:
        도구(search_restaurants, get_menu), MCP 도구(check_availability),
        세션 매니저가 모두 통합된 Agent.
    """
    reservation_mcp_client = MCPClient(
        lambda: stdio_client(
            StdioServerParameters(command=sys.executable, args=[str(_MCP_SERVER_PATH)])
        )
    )
    reservation_mcp_client.start()
    reservation_tools = reservation_mcp_client.list_tools_sync()

    model = BedrockModel(model_id=MODEL_ID, region_name=REGION)
    today = datetime.now().strftime("%Y-%m-%d")

    session_manager = FileSessionManager(
        session_id=session_id, storage_dir=str(_SESSIONS_DIR)
    )

    return Agent(
        model=model,
        system_prompt=SYSTEM_PROMPT_TEMPLATE.format(today=today),
        tools=[search_restaurants, get_menu, *reservation_tools],
        session_manager=session_manager,
        callback_handler=None,
    )


def list_sessions() -> list[dict]:
    """저장된 모든 세션의 요약 정보를 최근 갱신 순으로 반환한다.

    ``FileSessionManager``는 세션마다 ``sessions/session_<id>/session.json``에
    ``session_id``·``created_at``·``updated_at``을 남긴다. "새 대화 시작"으로
    세션 ID를 바꿔도 이전 세션 파일은 지워지지 않고 그대로 남으므로, 이
    함수로 그 파일들을 다시 찾아 사이드바의 "이전 대화" 목록에 쓴다.

    첫 사용자 메시지를 미리보기 텍스트로 함께 반환한다. 메시지 파일이나
    session.json이 손상되어 있으면(수동 삭제·비정상 종료 등) 그 세션은
    조용히 건너뛴다 — 목록 표시는 최선을 다한 결과면 충분하고, 손상된
    세션 하나 때문에 전체 목록이 깨지면 안 되기 때문이다.

    Returns:
        각 세션의 ``session_id``, ``updated_at``, ``preview``(첫 사용자
        메시지 요약, 없으면 빈 문자열)를 담은 dict 리스트. ``updated_at``
        내림차순(최근 것 먼저)으로 정렬된다.
    """
    if not _SESSIONS_DIR.exists():
        return []

    summaries: list[dict] = []
    for session_dir in _SESSIONS_DIR.iterdir():
        session_json_path = session_dir / "session.json"
        if not session_json_path.is_file():
            continue

        try:
            with session_json_path.open(encoding="utf-8") as f:
                session_data = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue

        session_id = session_data.get("session_id")
        updated_at = session_data.get("updated_at", "")
        if not session_id:
            continue

        summaries.append(
            {
                "session_id": session_id,
                "updated_at": updated_at,
                "preview": _first_user_message_preview(session_dir),
            }
        )

    summaries.sort(key=lambda s: s["updated_at"], reverse=True)
    return summaries


def _first_user_message_preview(session_dir: Path, max_length: int = 30) -> str:
    """세션 디렉토리에서 가장 이른 사용자 메시지를 미리보기 텍스트로 뽑는다.

    ``message_0.json``이 항상 존재한다고 가정하지 않는다 — 도구 결과만
    있는 메시지가 0번일 수도 있으므로, message_id 순으로 실제로 뒤져
    role이 "user"이고 텍스트 블록이 있는 첫 메시지를 찾는다.
    """
    messages_dir = session_dir / "agents" / "agent_default" / "messages"
    if not messages_dir.is_dir():
        return ""

    message_files = sorted(
        messages_dir.glob("message_*.json"),
        key=lambda p: int(p.stem.removeprefix("message_")),
    )
    for message_file in message_files:
        try:
            with message_file.open(encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue

        message = data.get("message", {})
        if message.get("role") != "user":
            continue

        text_parts = [
            block["text"]
            for block in message.get("content", [])
            if isinstance(block, dict) and "text" in block
        ]
        if text_parts:
            preview = " ".join(text_parts)
            if len(preview) > max_length:
                return preview[:max_length] + "…"
            return preview

    return ""


def main() -> None:
    """에이전트를 단독으로 한 번 호출해 응답과 세션 파일 생성을 확인한다."""
    agent = build_agent()

    print(f"[세션 ID] {DEFAULT_SESSION_ID}")
    print(f"[복원된 메시지 수] {len(agent.messages)}\n")

    query = "강남역 근처 이탈리안 식당 추천해 주세요"
    print(f"[사용자] {query}\n")
    result = agent(query)
    print(f"\n[응답 텍스트 길이] {len(str(result))}자")


if __name__ == "__main__":
    main()
