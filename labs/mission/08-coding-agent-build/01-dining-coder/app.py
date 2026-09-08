"""미니 코딩 콘솔 — 코딩 요청을 넣으면 자기 교정 루프(Coder→Reviewer→Tester)가
라운드별 판정을 보여주고, 최종 통과 코드를 workspace/ 파일로 확인시켜준다.
"""
import streamlit as st

from orchestrator import build_with_review

st.set_page_config(page_title="코딩 리뷰 루프", page_icon="🔄")
st.title("🔄 리뷰·테스트 자기 교정 루프")
st.caption("Coder가 쓰고, Reviewer가 지적하고, Tester가 실행으로 증명합니다. 최대 3라운드.")

if prompt := st.chat_input("코딩 요청을 입력하세요"):
    with st.chat_message("user"):
        st.write(prompt)

    with st.chat_message("assistant"):
        with st.spinner("에이전트 루프 실행 중... (라운드마다 Coder→Reviewer→Tester 순으로 호출되어 시간이 걸립니다)"):
            result = build_with_review(prompt)

        # 최종 상태 표시
        if result["state"] == "APPROVED":
            st.success(f"✅ 통과 (라운드 {result['rounds']})")
        else:
            st.warning(f"⚠️ 최선 결과 (라운드 {result['rounds']} — 상한 초과)")
            st.text("남은 지적:")
            st.text(result.get("remaining", ""))

        # 라운드별 판정 — 품질/보안 Reviewer·Tester 결과와 토큰 사용량을 순서대로 표시
        for h in result["history"]:
            icon = "✅" if h["approved"] and h["passed"] else "🔁"
            st.write(
                f"{icon} 라운드 {h['round']} — 품질: "
                f"{'APPROVED' if h['approved_quality'] else 'NEEDS_CHANGES'} · 보안: "
                f"{'APPROVED' if h['approved_security'] else 'NEEDS_CHANGES'} · Tester: {h['test']}"
            )
            if not h["approved"]:
                col1, col2 = st.columns(2)
                with col1:
                    with st.expander(f"라운드 {h['round']} 품질 리뷰 지적"):
                        st.text(h["review"])
                with col2:
                    with st.expander(f"라운드 {h['round']} 보안 리뷰 지적"):
                        st.text(h["security_review"])
            with st.expander(f"라운드 {h['round']} 토큰 사용량"):
                st.json(h["token_usage"])

        # 최종 코드 표시
        st.subheader("최종 코드")
        try:
            with open("workspace/reservation.py") as f:
                st.code(f.read(), language="python")
        except FileNotFoundError:
            st.error("workspace/reservation.py를 찾을 수 없습니다.")

