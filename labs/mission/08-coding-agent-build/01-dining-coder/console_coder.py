"""미니 코딩 콘솔 (미션 8-1용) — 코딩 요청을 넣으면 Coder 에이전트가
workspace/에 작성·실행한다. 리뷰·테스트 루프 없이 Coder 단독 호출.

미션 8-2의 자기 교정 루프 콘솔은 app.py를 참고.
"""
from pathlib import Path

import streamlit as st

from coder import agent

WORKSPACE = Path(__file__).parent / "workspace"

st.set_page_config(page_title="코딩 에이전트 콘솔", page_icon="🤖")
st.title("🤖 코딩 에이전트 콘솔")
st.caption("코딩 요청을 입력하면 에이전트가 코드를 작성·실행합니다.")

if prompt := st.chat_input("코딩 요청을 입력하세요"):
    with st.chat_message("user"):
        st.write(prompt)

    with st.chat_message("assistant"):
        with st.spinner("에이전트가 작업 중..."):
            result = agent(prompt)
        st.write(str(result))

    # workspace 파일 목록·내용 표시
    st.subheader("📁 workspace/ 파일")
    files = sorted(WORKSPACE.rglob("*.py"))
    if not files:
        st.info("아직 생성된 파일이 없습니다.")
    for f in files:
        with st.expander(f"📄 {f.relative_to(WORKSPACE)}"):
            st.code(f.read_text(encoding="utf-8"), language="python")
