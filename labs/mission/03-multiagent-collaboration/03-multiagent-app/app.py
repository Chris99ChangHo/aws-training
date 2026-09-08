# app.py — 멀티에이전트 다이닝 플래너 Streamlit 앱
import nest_asyncio

nest_asyncio.apply()

import re

import streamlit as st

from planner_engine import DiningPlannerEngine

st.set_page_config(page_title="다이닝 플래너", page_icon="🍽️", layout="wide")
st.title("🍽️ 멀티에이전트 다이닝 플래너")
st.caption("검색 · 메뉴 · 예약 전문가에게 위임하며 회식/기념일 코스를 구성합니다.")

if "delegation_log" not in st.session_state:
    st.session_state.delegation_log = []
if "messages" not in st.session_state:
    st.session_state.messages = []
if "last_total_cost" not in st.session_state:
    st.session_state.last_total_cost = None


def extract_total_cost(text: str) -> int | None:
    """응답 텍스트에서 '총 ... 원' 형태의 금액을 찾아 원 단위 정수로 반환합니다."""
    # "384,000원", "약 384,000원", "40만원" 등 다양한 표기를 최대한 커버
    matches = re.findall(r"([\d,]{4,})\s*원", text)
    if matches:
        nums = [int(m.replace(",", "")) for m in matches]
        return max(nums)
    man_matches = re.findall(r"(\d+)\s*만\s*원", text)
    if man_matches:
        return max(int(m) for m in man_matches) * 10000
    return None


with st.sidebar:
    st.header("📋 위임 로그")
    log_container = st.container()
    for entry in st.session_state.delegation_log:
        log_container.markdown(f"**오케스트레이터 → {entry['agent']}**")
        log_container.caption(entry["query"])
        log_container.divider()

col_main, col_metric = st.columns([3, 1])

with col_metric:
    if st.session_state.last_total_cost is not None:
        st.metric("💰 총 비용(추정)", f"{st.session_state.last_total_cost:,}원")

with col_main:
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    question = st.chat_input("예: 다음 주 금요일 저녁 8명 팀 회식 코스를 만들어 주세요. 예산은 총 40만원입니다.")

if question:
    st.session_state.messages.append({"role": "user", "content": question})

    _log_buffer = []

    def on_delegation(agent_name: str, query: str):
        _log_buffer.append({"agent": agent_name, "query": query})

    engine = DiningPlannerEngine(on_delegation=on_delegation)
    answer = engine.ask(question)

    st.session_state.delegation_log.extend(_log_buffer)

    total_cost = extract_total_cost(answer)
    if total_cost is not None:
        st.session_state.last_total_cost = total_cost

    st.session_state.messages.append({"role": "assistant", "content": answer})
    st.rerun()
