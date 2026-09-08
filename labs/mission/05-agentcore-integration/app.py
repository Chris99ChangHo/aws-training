"""강남 다이닝 컨시어지 — 프로덕션 Streamlit 앱."""
import uuid

import streamlit as st

from agent_client import invoke_agent, get_runtime_status
from memory_client import get_preferences
from reservation_client import get_reservations

ACTOR_ID = "user-001"


def new_session_id() -> str:
    return uuid.uuid4().hex + uuid.uuid4().hex


if "session_id" not in st.session_state:
    st.session_state.session_id = new_session_id()
if "messages" not in st.session_state:
    st.session_state.messages = []
if "tool_logs" not in st.session_state:
    st.session_state.tool_logs = []

st.title("🍽️ 강남 다이닝 컨시어지")

with st.sidebar:
    st.subheader("👤 고객 취향")
    try:
        prefs = get_preferences(ACTOR_ID)
        for p in prefs:
            st.write(f"- {p}")
        if not prefs:
            st.caption("저장된 취향 없음")
    except Exception as e:
        st.error(f"취향 조회 실패: {e}")

    st.subheader("🖥️ 시스템")
    st.write(f"Runtime: {get_runtime_status()}")
    st.caption(f"세션: {st.session_state.session_id[:12]}… · 사용자: {ACTOR_ID}")

    st.subheader("📋 예약 내역")
    try:
        reservations = get_reservations(ACTOR_ID, limit=5)
        for r in reservations:
            st.write(f"🍽️ **{r['restaurant']}** — {r['date']} {r['time']} ({r['party_size']}명)")
        if not reservations:
            st.caption("예약 없음")
    except Exception as e:
        st.caption(f"예약 조회 실패: {e}")

    st.subheader("🔧 도구 호출 로그")
    for log in st.session_state.tool_logs:
        st.caption(log)

    if st.button("새 대화 시작"):
        st.session_state.session_id = new_session_id()
        st.session_state.messages = []
        st.session_state.tool_logs = []
        st.rerun()

for msg in st.session_state.messages:
    st.chat_message(msg["role"]).write(msg["content"])

if prompt := st.chat_input("질문을 입력하세요"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.chat_message("user").write(prompt)

    try:
        response = invoke_agent(prompt, st.session_state.session_id, ACTOR_ID)
        answer = response.get("result", "")
        tool_calls = response.get("tool_calls", [])
    except Exception as e:
        answer, tool_calls = f"⚠️ 호출 실패: {e}", []

    for call in tool_calls:
        st.session_state.tool_logs.append(f"{call['name']} — {call['input']}")

    kb_calls = [c for c in tool_calls if "search_knowledge_base" in c["name"]]

    with st.chat_message("assistant"):
        if kb_calls:
            with st.container(border=True):
                head, body = st.columns([1, 3])
                head.markdown("**📚 식당 상세**")
                head.caption("Knowledge Base 근거")
                body.write(answer)
        else:
            st.write(answer)
    st.session_state.messages.append({"role": "assistant", "content": answer})
