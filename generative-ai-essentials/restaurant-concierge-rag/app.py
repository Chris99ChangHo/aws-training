"""
app.py

강남 식당 컨시어지 Knowledge Base(restaurant-concierge-kb) 기반
대화형 추천 챗봇.

Streamlit 채팅 인터페이스에서 질문을 입력하면 Bedrock의
RetrieveAndGenerate API로 KB를 검색해 답변과 참조 식당을 표시한다.

실행:
    streamlit run app.py
"""

from __future__ import annotations

import json
from pathlib import Path

import boto3
import streamlit as st

REGION = "us-west-2"
KB_INFO_PATH = Path(__file__).parent / "kb_info.json"

# us-west-2의 claude-sonnet-4-6은 INFERENCE_PROFILE 타입이라
# inference profile ARN이 필요하다.
GEN_MODEL_ID = "us.anthropic.claude-sonnet-4-6"

# 사이드바 카테고리 드롭다운. 값은 실제 메타데이터의 category와 매핑된다.
CATEGORY_OPTIONS: dict[str, dict | None] = {
    "전체": None,
    "한식": {"equals": {"key": "category", "value": "한식"}},
    "일식": {"equals": {"key": "category", "value": "일식"}},
    "중식": {"equals": {"key": "category", "value": "중식"}},
    "이탈리안": {"equals": {"key": "category", "value": "이탈리안"}},
    "프렌치": {"equals": {"key": "category", "value": "프렌치"}},
    "채식/비건": {"equals": {"key": "category", "value": "채식/비건"}},
}

# 예약 가능 여부 필터
RESERVATION_OPTIONS: dict[str, dict | None] = {
    "전체": None,
    "예약 가능만": {"equals": {"key": "reservation_available", "value": "true"}},
}

# 테마별 색상 토큰 (WCAG 2.1 AA 대비 기준 검증됨 - ui-conventions.md 참고)
THEMES: dict[str, dict[str, str]] = {
    "light": {
        "bg": "#FFFFFF",
        "bg_secondary": "#F7F8FA",
        "text": "#1A1A2E",
        "text_muted": "#6B7280",
        "accent": "#1D4ED8",
        "accent_soft": "#DBEAFE",
        "card_bg": "#FFFFFF",
        "card_border": "#E5E7EB",
        "user_bubble": "#2563EB",
        "user_text": "#FFFFFF",
        "assistant_bubble": "#F1F3F6",
        "assistant_text": "#1A1A2E",
    },
    "dark": {
        "bg": "#0F1117",
        "bg_secondary": "#171A21",
        "text": "#E5E7EB",
        "text_muted": "#9CA3AF",
        "accent": "#60A5FA",
        "accent_soft": "#1E3A5F",
        "card_bg": "#1B1F27",
        "card_border": "#2A2F3A",
        "user_bubble": "#2563EB",
        "user_text": "#FFFFFF",
        "assistant_bubble": "#1B1F27",
        "assistant_text": "#E5E7EB",
    },
}


def inject_theme_css(mode: str) -> None:
    """선택된 테마 색상으로 커스텀 CSS를 주입해 UI를 다시 그린다.

    html/body와 Streamlit 표준 위젯(selectbox, button, toggle) 내부까지
    명시적으로 덮어써야 한다. 그렇지 않으면 시스템 다크 모드가 일부
    영역에만 적용되어 배경/텍스트 색이 충돌한다. (seoul-travel-planner-kb
    실습에서 실제로 재현되어 발견한 문제 - .streamlit/config.toml의
    base="light"와 이 CSS로 함께 해결.)
    """
    t = THEMES[mode]
    st.markdown(
        f"""
        <style>
        html, body, .stApp, [data-testid="stAppViewContainer"] {{
            background-color: {t['bg']} !important;
            color: {t['text']};
        }}
        [data-testid="stHeader"] {{
            background-color: {t['bg']} !important;
        }}
        [data-testid="stBottomBlockContainer"] {{
            background-color: {t['bg']} !important;
        }}
        section[data-testid="stSidebar"] {{
            background-color: {t['bg_secondary']} !important;
            border-right: 1px solid {t['card_border']};
        }}
        section[data-testid="stSidebar"] * {{
            color: {t['text']} !important;
        }}
        h1, h2, h3, h4, p, span, label, div {{
            color: {t['text']};
        }}
        .app-header {{
            padding: 0.5rem 0 1.2rem 0;
            border-bottom: 1px solid {t['card_border']};
            margin-bottom: 1.2rem;
        }}
        .app-header .subtitle {{
            color: {t['text_muted']} !important;
            font-size: 0.92rem;
        }}
        div[data-testid="stChatMessage"] {{
            background-color: {t['assistant_bubble']};
            border-radius: 14px;
            padding: 0.4rem 0.2rem;
            margin-bottom: 0.4rem;
        }}
        .restaurant-card {{
            background-color: {t['card_bg']};
            border: 1px solid {t['card_border']};
            border-radius: 12px;
            padding: 14px 16px;
            margin-bottom: 8px;
        }}
        .restaurant-card h4 {{
            margin: 0 0 6px 0;
            font-size: 1.02rem;
            color: {t['text']} !important;
        }}
        .restaurant-card .meta-row {{
            font-size: 0.86rem;
            color: {t['text_muted']} !important;
            margin: 2px 0;
        }}
        .restaurant-card .badge {{
            display: inline-block;
            background-color: {t['accent_soft']};
            color: {t['accent']} !important;
            font-size: 0.76rem;
            font-weight: 600;
            padding: 2px 9px;
            border-radius: 999px;
            margin-bottom: 6px;
            margin-right: 4px;
        }}
        .restaurant-card .uri {{
            font-size: 0.72rem;
            color: {t['text_muted']} !important;
            word-break: break-all;
            margin-top: 6px;
        }}
        div[data-testid="stChatInput"] {{
            background-color: {t['bg']} !important;
        }}
        div[data-testid="stChatInput"] textarea {{
            background-color: {t['bg_secondary']} !important;
            color: {t['text']} !important;
        }}
        div[data-baseweb="select"] > div {{
            background-color: {t['card_bg']} !important;
            border-color: {t['card_border']} !important;
            color: {t['text']} !important;
        }}
        div[data-baseweb="popover"] li {{
            background-color: {t['card_bg']} !important;
            color: {t['text']} !important;
        }}
        div[data-baseweb="popover"] li:hover {{
            background-color: {t['bg_secondary']} !important;
        }}
        .stButton>button {{
            border-radius: 8px;
            background-color: {t['card_bg']} !important;
            color: {t['text']} !important;
            border: 1px solid {t['card_border']} !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


@st.cache_resource
def get_gen_model_arn() -> str:
    account_id = boto3.client("sts", region_name=REGION).get_caller_identity()["Account"]
    return f"arn:aws:bedrock:{REGION}:{account_id}:inference-profile/{GEN_MODEL_ID}"


@st.cache_resource
def get_kb_id() -> str:
    with open(KB_INFO_PATH, encoding="utf-8") as fh:
        return json.load(fh)["knowledgeBaseId"]


@st.cache_resource
def get_client():
    return boto3.client("bedrock-agent-runtime", region_name=REGION)


def build_filter(category_filter: dict | None, reservation_filter: dict | None) -> dict | None:
    """카테고리 필터와 예약 필터를 andAll로 결합한다. 둘 다 없으면 None."""
    parts = [f for f in (category_filter, reservation_filter) if f is not None]
    if not parts:
        return None
    if len(parts) == 1:
        return parts[0]
    return {"andAll": parts}


def render_source_cards(sources: list[str]) -> None:
    """참조 문서를 식당 카드 형태로 렌더링한다.

    전체 S3 URI에는 AWS 계정 ID가 포함되므로(s3://<bucket>-<account_id>/...)
    화면에는 파일명만 표시한다. 계정 ID를 화면에 노출하면 스크린샷이나
    데모 캡처 시 그대로 유출되기 때문이다 (git-conventions.md 참고).
    """
    if not sources:
        return

    st.markdown("**🍽️ 참조 식당 문서**")
    cols = st.columns(min(len(sources), 3))
    for idx, uri in enumerate(sources):
        name = uri.rsplit("/", 1)[-1]
        with cols[idx % len(cols)]:
            st.markdown(
                f"""
                <div class="restaurant-card">
                    <h4>📄 {name}</h4>
                </div>
                """,
                unsafe_allow_html=True,
            )


def query_kb(
    client,
    kb_id: str,
    question: str,
    search_filter: dict | None = None,
    session_id: str | None = None,
) -> tuple[str, list[str], str]:
    """RetrieveAndGenerate를 호출해 (답변 텍스트, 참조 문서 URI 목록, sessionId)를 반환한다."""
    kb_config: dict = {
        "knowledgeBaseId": kb_id,
        "modelArn": get_gen_model_arn(),
    }
    if search_filter is not None:
        kb_config["retrievalConfiguration"] = {
            "vectorSearchConfiguration": {"filter": search_filter}
        }

    request: dict = {
        "input": {"text": question},
        "retrieveAndGenerateConfiguration": {
            "type": "KNOWLEDGE_BASE",
            "knowledgeBaseConfiguration": kb_config,
        },
    }
    if session_id:
        request["sessionId"] = session_id

    resp = client.retrieve_and_generate(**request)
    answer = resp["output"]["text"]
    new_session_id = resp["sessionId"]

    uris: list[str] = []
    for citation in resp.get("citations", []):
        for ref in citation.get("retrievedReferences", []):
            uri = ref.get("location", {}).get("s3Location", {}).get("uri", "")
            if uri and uri not in uris:
                uris.append(uri)

    return answer, uris, new_session_id


def main() -> None:
    st.set_page_config(
        page_title="강남 식당 컨시어지 챗봇",
        page_icon="🍽️",
        layout="centered",
    )

    if "theme" not in st.session_state:
        st.session_state.theme = "light"

    inject_theme_css(st.session_state.theme)

    try:
        kb_id = get_kb_id()
    except FileNotFoundError:
        st.error(
            "kb_info.json을 찾을 수 없습니다. 먼저 setup_02_create_kb.py를 "
            "실행해 Knowledge Base를 생성해 주세요."
        )
        return

    client = get_client()

    with st.sidebar:
        st.header("⚙️ 설정")

        is_dark = st.session_state.theme == "dark"
        toggled = st.toggle("🌙 다크 모드", value=is_dark)
        new_theme = "dark" if toggled else "light"
        if new_theme != st.session_state.theme:
            st.session_state.theme = new_theme
            st.rerun()

        st.divider()
        st.subheader("검색 필터")
        selected_category = st.selectbox(
            "카테고리", options=list(CATEGORY_OPTIONS.keys()), index=0
        )
        selected_reservation = st.selectbox(
            "예약", options=list(RESERVATION_OPTIONS.keys()), index=0
        )
        st.caption("선택한 조건에 맞는 식당만 검색 대상에 포함됩니다.")

        st.divider()
        if st.button("🗑️ 대화 초기화", use_container_width=True):
            st.session_state.messages = []
            st.session_state.bedrock_session_id = None
            st.rerun()

    search_filter = build_filter(
        CATEGORY_OPTIONS[selected_category], RESERVATION_OPTIONS[selected_reservation]
    )

    st.markdown(
        """
        <div class="app-header">
            <h1 style="margin-bottom:0.2rem;">🍽️ 강남 식당 컨시어지 챗봇</h1>
            <div class="subtitle">Amazon Bedrock Knowledge Base 기반 대화형 추천</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "bedrock_session_id" not in st.session_state:
        st.session_state.bedrock_session_id = None

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("sources"):
                render_source_cards(msg["sources"])

    question = st.chat_input(
        "강남 식당에 대해 물어보세요 (예: 데이트하기 좋은 이탈리안 식당? / 예약 가능한 곳은?)"
    )
    if not question:
        return

    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Knowledge Base 검색 중..."):
            try:
                answer, sources, session_id = query_kb(
                    client,
                    kb_id,
                    question,
                    search_filter,
                    st.session_state.bedrock_session_id,
                )
            except Exception as exc:  # noqa: BLE001 - 사용자에게 오류 표시
                st.error(f"검색 중 오류가 발생했습니다: {exc}")
                return

        st.session_state.bedrock_session_id = session_id

        st.markdown(answer)
        render_source_cards(sources)

    st.session_state.messages.append(
        {"role": "assistant", "content": answer, "sources": sources}
    )


if __name__ == "__main__":
    main()
