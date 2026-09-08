# app.py — 통합 에이전트의 최소 확인용 Streamlit 미니 챗
import sys

import streamlit as st
from mcp import StdioServerParameters, stdio_client
from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient

from tools import get_menu, search_restaurants

REGION = "us-west-2"
MODEL_ID = "us.anthropic.claude-sonnet-4-6"

st.title("🍽️ 강남 다이닝 컨시어지")

question = st.chat_input("무엇을 도와드릴까요?")
if question:
    with st.chat_message("user"):
        st.markdown(question)

    model = BedrockModel(model_id=MODEL_ID, region_name=REGION)
    reservation_mcp = MCPClient(
        lambda: stdio_client(StdioServerParameters(command=sys.executable, args=["mcp_server.py"]))
    )

    with reservation_mcp:
        mcp_tools = reservation_mcp.list_tools_sync()
        agent = Agent(
            model=model,
            tools=[search_restaurants, get_menu, *mcp_tools],
            system_prompt=(
                "당신은 강남 다이닝 컨시어지입니다. 사용자의 요청에 따라 "
                "식당 검색, 메뉴 조회, 예약 가능 여부 확인 도구를 순서대로 "
                "활용해 정확하고 친절하게 답변하세요."
            ),
            callback_handler=None,
        )
        response = agent(question)

    with st.chat_message("assistant"):
        st.markdown(str(response))
