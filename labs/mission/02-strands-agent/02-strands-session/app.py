# app.py — 세션 에이전트의 최소 확인용 Streamlit 미니 챗
import uuid

import streamlit as st
from mcp import StdioServerParameters, stdio_client
from strands import Agent
from strands.agent.conversation_manager import SlidingWindowConversationManager
from strands.models import BedrockModel
from strands.session import FileSessionManager
from strands.tools.mcp import MCPClient

from tools import get_menu, search_restaurants

import sys

REGION = "us-west-2"
MODEL_ID = "us.anthropic.claude-sonnet-4-6"

st.title("🍽️ 강남 다이닝 컨시어지 (세션 유지)")

if "session_id" not in st.session_state:
    st.session_state.session_id = "dining-session-001"
if "messages" not in st.session_state:
    st.session_state.messages = []

with st.sidebar:
    st.caption(f"session_id: `{st.session_state.session_id}`")
    if st.button("🔄 세션 초기화 (새 대화 시작)"):
        st.session_state.session_id = f"dining-session-{uuid.uuid4().hex[:8]}"
        st.session_state.messages = []
        st.rerun()

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

question = st.chat_input("무엇을 도와드릴까요?")
if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    model = BedrockModel(model_id=MODEL_ID, region_name=REGION)
    reservation_mcp = MCPClient(
        lambda: stdio_client(StdioServerParameters(command=sys.executable, args=["mcp_server.py"]))
    )
    session_manager = FileSessionManager(
        session_id=st.session_state.session_id, storage_dir="./sessions"
    )
    conversation_manager = SlidingWindowConversationManager(window_size=10)

    with reservation_mcp:
        mcp_tools = reservation_mcp.list_tools_sync()
        agent = Agent(
            model=model,
            tools=[search_restaurants, get_menu, *mcp_tools],
            system_prompt=(
                "당신은 강남 다이닝 컨시어지입니다. 사용자의 요청에 따라 "
                "식당 검색, 메뉴 조회, 예약 가능 여부 확인 도구를 활용해 "
                "정확하고 친절하게 답변하세요."
            ),
            session_manager=session_manager,
            conversation_manager=conversation_manager,
            callback_handler=None,
        )
        response = agent(question)

    answer = str(response)
    with st.chat_message("assistant"):
        st.markdown(answer)
    st.session_state.messages.append({"role": "assistant", "content": answer})
