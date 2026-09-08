# app.py — 선택한 워크플로(Graph)를 호출하는 Streamlit 미니 실행 뷰
import streamlit as st

from graph_pipeline import build_graph

st.set_page_config(page_title="다이닝 회식 플래너 (Graph)", page_icon="🍽️")
st.title("🍽️ 다이닝 회식 플래너 — Graph 파이프라인")
st.caption("검색 → 리뷰 → 코스 구성 → 검증 순으로 실행되며, 예산 초과 시 검색 단계로 되돌아갑니다.")

request = st.text_input("요청을 입력하세요", value="8명 팀 회식 코스 계획")

if st.button("실행", type="primary") and request:
    with st.spinner("에이전트들이 협업 중입니다..."):
        graph = build_graph()
        result = graph(request)

    st.subheader("📋 실행 단계 순서")
    step_labels = {
        "search": "🔍 검색",
        "review": "📝 리뷰",
        "course": "🍽️ 코스 구성",
        "validate": "✅ 검증",
    }
    order_str = " → ".join(step_labels.get(n.node_id, n.node_id) for n in result.execution_order)
    st.markdown(order_str)

    st.subheader("🍽️ 최종 코스")
    # 마지막으로 실행된 노드가 최종 결과(코스 구성 또는 검증 통과본)
    last_node = result.execution_order[-1]
    last_result = result.results[last_node.node_id]
    agent_results = last_result.get_agent_results()
    final_text = str(agent_results[-1]) if agent_results else "(결과 없음)"
    st.markdown(final_text)

    with st.expander("단계별 상세 결과 보기"):
        for node in result.execution_order:
            node_result = result.results[node.node_id]
            agent_results = node_result.get_agent_results()
            text = str(agent_results[-1]) if agent_results else ""
            st.markdown(f"**{step_labels.get(node.node_id, node.node_id)}**")
            st.markdown(text)
            st.divider()
