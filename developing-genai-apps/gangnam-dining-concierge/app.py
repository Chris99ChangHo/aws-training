"""강남 다이닝 컨시어지 Streamlit 챗봇 UI.

agent.py의 build_agent()(도구+MCP+세션 통합 에이전트)를 채팅형 웹앱으로
감싼다. 사이드바에 도구 호출 로그를 실시간 표시하고, 대화에서 언급된
식당을 이름/요리 종류/가격대 카드로 보여준다.
"""

from __future__ import annotations

import asyncio
import json
import uuid

import streamlit as st

from agent import DEFAULT_SESSION_ID, build_agent, list_sessions
from tools import RESTAURANTS

st.set_page_config(page_title="강남 다이닝 컨시어지", page_icon="🍽️", layout="wide")

# 사이드바 도구 호출 로그에 유지할 최대 항목 수. 대화가 길어질수록
# 로그가 무한정 쌓여 사이드바가 계속 길어지는 것을 막기 위함이다.
MAX_TOOL_CALL_LOG_ENTRIES = 10


def _extract_mentioned_restaurants(text: str) -> list[dict]:
    """응답 텍스트에서 언급된 식당을 찾아 데이터를 반환한다.

    RESTAURANTS에 있는 display_name이 텍스트에 등장하는지 문자열
    포함 여부로 검사한다. 텍스트에서 먼저 언급된 식당이 먼저 나오도록
    정렬하고, 중복은 제거한다.

    Args:
        text: 에이전트 응답 텍스트.

    Returns:
        텍스트에서 언급된 순서대로 정렬된 식당 데이터 리스트.
    """
    positions = []
    for restaurant in RESTAURANTS:
        idx = text.find(restaurant["display_name"])
        if idx != -1:
            positions.append((idx, restaurant))
    positions.sort(key=lambda pair: pair[0])

    mentioned: list[dict] = []
    seen_names: set[str] = set()
    for _, restaurant in positions:
        if restaurant["display_name"] not in seen_names:
            mentioned.append(restaurant)
            seen_names.add(restaurant["display_name"])
    return mentioned


def _render_restaurant_card(restaurant: dict) -> None:
    """식당 하나를 카드로 렌더링한다. 이름/요리 종류/가격대/별점을 표시."""
    stars = "⭐" * round(restaurant["rating"])
    with st.container(border=True):
        st.markdown(f"#### 🍽️ {restaurant['display_name']}")
        st.markdown(
            f"**{restaurant['cuisine']}** · {restaurant['area']} · "
            f"가격대: {restaurant['price_range']}"
        )
        st.markdown(f"{stars} ({restaurant['rating']})")
        reservation_label = (
            "✅ 예약 가능" if restaurant["accepts_reservation"] else "❌ 예약 불가"
        )
        st.caption(reservation_label)


def _tool_display_name(tool_name: str) -> str:
    """도구 함수명을 사이드바에 표시할 한글 라벨로 변환한다."""
    labels = {
        "search_restaurants": "🔍 식당 검색",
        "get_menu": "📋 메뉴 조회",
        "check_availability": "📅 예약 가능 여부 조회",
    }
    return labels.get(tool_name, f"🔧 {tool_name}")


def _rebuild_display_messages(agent_messages: list[dict]) -> list[dict]:
    """에이전트의 원시 메시지 히스토리에서 화면에 표시할 텍스트만 뽑아낸다.

    도구 호출/결과 블록은 제외하고 순수 텍스트 블록만 모은다.
    """
    display_messages = []
    for message in agent_messages:
        role = message.get("role")
        content_blocks = message.get("content", [])
        text_parts = [
            block["text"]
            for block in content_blocks
            if isinstance(block, dict) and "text" in block
        ]
        if text_parts and role in ("user", "assistant"):
            display_messages.append({"role": role, "content": "\n".join(text_parts)})
    return display_messages


def _rebuild_tool_call_log(agent_messages: list[dict]) -> list[dict]:
    """에이전트의 원시 메시지 히스토리에서 과거 도구 호출 로그를 복원한다.

    FileSessionManager가 대화 텍스트를 복원해도 도구 호출 로그는 매번
    빈 상태로 시작해, 세션이 이어지는데도 사이드바만 끊긴 것처럼 보이는
    비대칭이 있었다. assistant 메시지의 toolUse 블록을 순서대로 뽑아
    같은 형태(``{"name", "input"}``)로 재구성해 그 비대칭을 없앤다.

    최근 항목만 남기는 정책(``MAX_TOOL_CALL_LOG_ENTRIES``)은
    ``_run_agent_streaming``에서 적용되므로 여기서는 전체를 반환한다.
    """
    tool_call_log = []
    for message in agent_messages:
        if message.get("role") != "assistant":
            continue
        for block in message.get("content", []):
            if isinstance(block, dict) and "toolUse" in block:
                tool_use = block["toolUse"]
                tool_input = tool_use.get("input")
                tool_call_log.append(
                    {
                        "name": str(tool_use.get("name", "")),
                        "input": tool_input if isinstance(tool_input, dict) else {},
                    }
                )
    return tool_call_log[-MAX_TOOL_CALL_LOG_ENTRIES:]


def _init_session_state() -> None:
    """Streamlit 세션 상태를 최초 1회 초기화한다."""
    if "chat_session_id" not in st.session_state:
        st.session_state.chat_session_id = DEFAULT_SESSION_ID

    if "agent" not in st.session_state:
        st.session_state.agent = build_agent(session_id=st.session_state.chat_session_id)

    if "tool_call_log" not in st.session_state:
        # FileSessionManager가 복원한 과거 도구 호출도 함께 복원한다.
        # 대화 텍스트는 복원되는데 로그만 비어 있으면 세션이 끊긴 것처럼
        # 보이는 비대칭이 생긴다.
        st.session_state.tool_call_log = _rebuild_tool_call_log(
            st.session_state.agent.messages
        )

    if "display_messages" not in st.session_state:
        # FileSessionManager가 복원한 기존 대화를 화면에도 그대로 반영한다.
        st.session_state.display_messages = _rebuild_display_messages(
            st.session_state.agent.messages
        )


def _render_sidebar() -> None:
    """사이드바: 세션 정보, 이전 대화 목록, 도구 호출 로그, 새 대화 시작 버튼."""
    with st.sidebar:
        st.header("🛠️ 도구 호출 로그")

        if st.button("🔄 새 대화 시작", use_container_width=True):
            st.session_state.chat_session_id = f"gangnam-dining-concierge-{uuid.uuid4()}"
            for key in ("agent", "display_messages", "tool_call_log"):
                st.session_state.pop(key, None)
            st.rerun()

        st.divider()
        _render_previous_sessions()

        st.divider()
        st.subheader("호출된 도구")

        if not st.session_state.tool_call_log:
            st.caption("채팅으로 질문하면 여기에 호출된 도구가 표시됩니다.")
        else:
            for entry in reversed(st.session_state.tool_call_log):
                with st.container(border=True):
                    st.markdown(f"**{_tool_display_name(entry['name'])}**")
                    if entry["input"]:
                        st.json(entry["input"])


def _render_previous_sessions() -> None:
    """사이드바: 지금 세션을 제외한 이전 대화 목록과 전환 버튼.

    "새 대화 시작"은 세션 파일을 지우지 않고 session_id만 새로 발급한다.
    이 함수가 그 파일들을 다시 찾아 목록으로 보여줘, 전에는 UUID를
    잊으면 다시 접근할 수 없었던 이전 대화를 클릭 한 번으로 이어갈 수
    있게 한다.
    """
    st.subheader("💬 이전 대화")

    other_sessions = [
        s
        for s in list_sessions()
        if s["session_id"] != st.session_state.chat_session_id
    ]

    if not other_sessions:
        st.caption("아직 다른 대화 기록이 없습니다.")
        return

    for session in other_sessions:
        label = session["preview"] or "(내용 없음)"
        if st.button(f"🕑 {label}", key=f"session_{session['session_id']}", use_container_width=True):
            st.session_state.chat_session_id = session["session_id"]
            for key in ("agent", "display_messages", "tool_call_log"):
                st.session_state.pop(key, None)
            st.rerun()


def _render_welcome_guide() -> None:
    """대화 시작 전 첫 화면: 이 앱으로 무엇을 할 수 있는지 안내한다."""
    st.info(
        "강남 일대 식당을 검색하고, 메뉴·예약 가능 여부를 대화로 물어보세요. "
        "왼쪽 사이드바에서 어떤 도구가 호출됐는지 실시간으로 볼 수 있습니다."
    )

    st.markdown("**이렇게 물어보세요**")
    example_queries = [
        "강남역 근처 이탈리안 식당 추천해 주세요",
        "강남 파스타 하우스 메뉴 좀 보여주세요",
        "내일 저녁 7시에 2명 예약 가능해요?",
        "매운 건 못 먹어요, 다른 곳으로 추천해 주세요",
    ]
    cols = st.columns(2)
    for idx, query in enumerate(example_queries):
        with cols[idx % 2]:
            st.markdown(f"- {query}")


def _render_chat_history() -> None:
    """메인 영역: 지금까지의 채팅 히스토리와 추천 식당 카드를 렌더링한다."""
    if not st.session_state.display_messages:
        _render_welcome_guide()
        return

    for message in st.session_state.display_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message["role"] == "assistant":
                mentioned = _extract_mentioned_restaurants(message["content"])
                if mentioned:
                    cols = st.columns(len(mentioned))
                    for col, restaurant in zip(cols, mentioned):
                        with col:
                            _render_restaurant_card(restaurant)


async def _run_agent_streaming(
    user_input: str, response_placeholder: "st.delta_generator.DeltaGenerator"
) -> str:
    """에이전트 응답을 스트리밍으로 받아 화면에 표시하고, 도구 호출을 로깅한다.

    ``agent.stream_async()``의 이벤트를 Streamlit 스크립트의 메인 실행
    흐름(asyncio.run) 안에서 직접 순회한다. callback_handler를 쓰면
    별도 스레드에서 위젯을 갱신하려다 NoSessionContext 오류가 나기
    때문에 이 방식을 쓴다.

    도구 입력은 스트리밍 중 JSON 문자열이 델타로 누적되며 도착하므로,
    ``toolUseId``를 키로 로그 항목을 매번 최신 입력으로 갱신(upsert)한다.

    Args:
        user_input: 사용자 입력 텍스트.
        response_placeholder: 스트리밍 텍스트를 표시할 st.empty() 컨테이너.

    Returns:
        누적된 최종 응답 텍스트.
    """
    streamed_text = ""
    log_index_by_tool_use_id: dict[str, int] = {}

    async for event in st.session_state.agent.stream_async(user_input):
        current_tool_use = event.get("current_tool_use")
        if isinstance(current_tool_use, dict):
            tool_use_id = current_tool_use.get("toolUseId")
            tool_name = current_tool_use.get("name")
            raw_input = current_tool_use.get("input")

            if tool_use_id and tool_name:
                parsed_input: dict = {}
                if isinstance(raw_input, dict):
                    parsed_input = raw_input
                elif isinstance(raw_input, str) and raw_input:
                    try:
                        parsed = json.loads(raw_input)
                        if isinstance(parsed, dict):
                            parsed_input = parsed
                    except json.JSONDecodeError:
                        pass  # 아직 완성되지 않은 중간 상태의 JSON 조각

                entry = {"name": str(tool_name), "input": parsed_input}
                if tool_use_id in log_index_by_tool_use_id:
                    idx = log_index_by_tool_use_id[tool_use_id]
                    st.session_state.tool_call_log[idx] = entry
                else:
                    log_index_by_tool_use_id[tool_use_id] = len(
                        st.session_state.tool_call_log
                    )
                    st.session_state.tool_call_log.append(entry)

        chunk = event.get("data")
        if isinstance(chunk, str):
            streamed_text += chunk
            response_placeholder.markdown(streamed_text)

    # 턴이 끝난 뒤에 자른다. 스트리밍 도중 자르면 log_index_by_tool_use_id가
    # 가리키는 인덱스가 어긋난다.
    if len(st.session_state.tool_call_log) > MAX_TOOL_CALL_LOG_ENTRIES:
        st.session_state.tool_call_log = st.session_state.tool_call_log[
            -MAX_TOOL_CALL_LOG_ENTRIES:
        ]

    return streamed_text


def _render_chat_input() -> None:
    """채팅 입력을 받아 에이전트를 스트리밍으로 호출하고 결과를 화면에 반영한다."""
    user_input = st.chat_input("예: 강남역 근처 이탈리안 식당 추천해 주세요")
    if not user_input:
        return

    st.session_state.display_messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        response_placeholder = st.empty()
        final_text = asyncio.run(_run_agent_streaming(user_input, response_placeholder))

        mentioned = _extract_mentioned_restaurants(final_text)
        if mentioned:
            cols = st.columns(len(mentioned))
            for col, restaurant in zip(cols, mentioned):
                with col:
                    _render_restaurant_card(restaurant)

    st.session_state.display_messages.append({"role": "assistant", "content": final_text})


def main() -> None:
    """Streamlit 앱 진입점."""
    _init_session_state()

    st.title("🍽️ 강남 다이닝 컨시어지")
    st.caption("강남 일대 식당 검색, 메뉴 조회, 예약 가능 여부를 대화로 확인하세요.")
    st.caption("화면 우측 상단 메뉴(≡) → Settings에서 라이트/다크 테마를 바꿀 수 있습니다.")

    _render_sidebar()
    _render_chat_history()
    _render_chat_input()


if __name__ == "__main__":
    main()
