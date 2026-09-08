"""
05_agentic_rag_router.py

Corrective RAG 라우터 에이전트.

KB 검색 결과의 품질을 스스로 분류(correct / ambiguous / incorrect)하고,
KB에 없는 질문이면 웹 검색으로 폴백한다.

  - correct    : KB 결과만으로 답변
  - ambiguous  : KB + 웹 검색 결합
  - incorrect  : 웹 검색만으로 답변

Strands Agents SDK의 @tool로 도구 3개를 구현한다:
  1. search_knowledge_base : restaurant-concierge-kb에서 청크 검색
  2. classify_quality      : 검색 결과 품질을 correct/ambiguous/incorrect로 분류
  3. web_search            : 웹 검색 시뮬레이션 (준비된 기사 딕셔너리)

API 문서는 strandsagents.com MCP로 확인:
  - BedrockModel의 model_id는 "us." 프리픽스 짧은 문자열을 그대로 쓰면
    SDK가 내부적으로 inference profile로 처리한다 (전체 ARN 조립 불필요).
    https://strandsagents.com/docs/user-guide/concepts/model-providers/amazon-bedrock
  - @tool 데코레이터는 docstring의 Args 섹션에서 파라미터 설명을 추출한다.
    https://strandsagents.com/docs/user-guide/concepts/tools/custom-tools

환경 변수:
    KNOWLEDGE_BASE_ID : 기본값은 kb_info.json에서 읽음

사용법:
    python 05_agentic_rag_router.py
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import boto3
from strands import Agent, tool
from strands.models import BedrockModel

REGION = "us-west-2"
MODEL_ID = "us.anthropic.claude-sonnet-4-6"

KB_INFO_PATH = Path(__file__).parent / "kb_info.json"


def _default_kb_id() -> str:
    with open(KB_INFO_PATH, encoding="utf-8") as fh:
        return json.load(fh)["knowledgeBaseId"]


KNOWLEDGE_BASE_ID = os.environ.get("KNOWLEDGE_BASE_ID", _default_kb_id())

_kb_runtime = boto3.client("bedrock-agent-runtime", region_name=REGION)

# 웹 검색 시뮬레이션 - "미쉐린" 키워드에 준비된 기사를 반환한다.
# 실제 검색 API(Tavily, DuckDuckGo 등)는 불필요하다는 미션 제약을 따른다.
_WEB_SEARCH_DB: dict[str, list[dict[str, str]]] = {
    "미쉐린": [
        {
            "title": "2026 미쉐린 가이드 서울, 강남 신규 선정 식당 3곳 공개",
            "snippet": (
                "미쉐린 가이드는 2026년 개정판에서 강남 지역 신규 선정 식당으로 "
                "'정식당', '주옥', '알라프리마' 3곳을 발표했다. 이번 개정에서는 "
                "특히 모던 한식과 퓨전 요리를 다루는 레스토랑이 강세를 보였다."
            ),
            "url": "https://example.com/michelin-guide-2026-gangnam",
        },
        {
            "title": "미쉐린 스타 레스토랑, 강남 다이닝 씬의 변화",
            "snippet": (
                "최근 강남 지역은 파인다이닝 수요 증가로 미쉐린 가이드 등재 "
                "식당이 늘고 있다. 전문가들은 예약 경쟁이 더 치열해질 것으로 "
                "전망한다."
            ),
            "url": "https://example.com/michelin-gangnam-dining-trend",
        },
    ],
}


@tool
def search_knowledge_base(query: str) -> str:
    """강남 식당 컨시어지 Knowledge Base(restaurant-concierge-kb)에서
    질의와 관련된 문서 청크를 검색한다.

    Args:
        query: 검색할 질문 또는 키워드

    Returns:
        검색된 청크 목록을 유사도 점수·출처와 함께 JSON 문자열로 반환.
        결과가 없으면 빈 리스트를 반환한다.
    """
    resp = _kb_runtime.retrieve(
        knowledgeBaseId=KNOWLEDGE_BASE_ID,
        retrievalQuery={"text": query},
        retrievalConfiguration={"vectorSearchConfiguration": {"numberOfResults": 5}},
    )

    chunks = []
    for r in resp.get("retrievalResults", []):
        chunks.append(
            {
                "text": r.get("content", {}).get("text", "")[:500],
                "score": round(r.get("score", 0.0), 4),
                "source": r.get("location", {})
                .get("s3Location", {})
                .get("uri", "")
                .rsplit("/", 1)[-1],
            }
        )
    return json.dumps({"query": query, "results": chunks}, ensure_ascii=False)


@tool
def classify_quality(query: str, kb_results_json: str) -> str:
    """KB 검색 결과가 질문에 답하기 충분한지 스스로 판정한다.

    다음 기준으로 correct / ambiguous / incorrect 중 하나로 분류한다:
      - correct   : 최고 유사도 점수가 0.45 이상이고, 청크 내용이 질문과
                     직접 관련됨 (KB만으로 신뢰할 수 있는 답변 가능)
      - ambiguous : 점수가 0.25~0.45 사이거나, 청크가 부분적으로만 관련됨
                     (KB 정보를 보조 근거로 쓰되 웹 검색으로 보강 필요)
      - incorrect : 점수가 0.25 미만이거나 결과가 없음
                     (KB에 관련 정보가 없다고 판단, 웹 검색으로 전환)

    Args:
        query: 원본 질문
        kb_results_json: search_knowledge_base가 반환한 JSON 문자열

    Returns:
        {"classification": "correct|ambiguous|incorrect", "reason": "...",
         "top_score": float} 형태의 JSON 문자열
    """
    data = json.loads(kb_results_json)
    results = data.get("results", [])

    if not results:
        return json.dumps(
            {
                "classification": "incorrect",
                "reason": "KB에서 관련 청크를 찾지 못했다.",
                "top_score": 0.0,
            },
            ensure_ascii=False,
        )

    top_score = max(r["score"] for r in results)

    if top_score >= 0.45:
        classification = "correct"
        reason = f"최고 유사도 {top_score}로 질문과 직접 관련된 청크를 찾았다."
    elif top_score >= 0.25:
        classification = "ambiguous"
        reason = f"최고 유사도 {top_score}로 부분적으로만 관련된 청크를 찾았다."
    else:
        classification = "incorrect"
        reason = f"최고 유사도 {top_score}로 관련성이 낮아 KB에 없는 정보로 판단."

    return json.dumps(
        {"classification": classification, "reason": reason, "top_score": top_score},
        ensure_ascii=False,
    )


@tool
def web_search(query: str) -> str:
    """웹 검색을 시뮬레이션한다 (실제 API 호출 없음, 준비된 기사 반환).

    Args:
        query: 검색할 질문 또는 키워드

    Returns:
        관련 기사 목록을 JSON 문자열로 반환. 준비된 키워드와 매칭되는
        기사가 없으면 빈 리스트를 반환한다.
    """
    matched: list[dict[str, str]] = []
    for keyword, articles in _WEB_SEARCH_DB.items():
        if keyword in query:
            matched.extend(articles)

    return json.dumps(
        {"query": query, "articles": matched, "simulated": True}, ensure_ascii=False
    )


SYSTEM_PROMPT = """당신은 강남 식당 컨시어지 "강남 다이닝"의 Corrective RAG
라우터입니다. 사용자 질문에 답하기 위해 다음 절차를 반드시 따르세요.

1. search_knowledge_base로 restaurant-concierge-kb를 검색한다.
2. classify_quality로 검색 결과 품질을 correct/ambiguous/incorrect로
   분류한다.
3. 분류 결과에 따라 라우팅한다:
   - correct   : KB 검색 결과만 근거로 답변한다. 웹 검색을 하지 않는다.
   - ambiguous : web_search도 호출해 KB 결과와 결합하여 답변한다.
   - incorrect : web_search만 근거로 답변한다. web_search 결과도 없으면
                 "확인할 수 없습니다"라고 답한다.

답변 마지막에는 반드시 어떤 전략을 사용했는지 명시한다.
예: "[전략: KB 검색만 사용]" 또는 "[전략: KB+웹 검색 결합]" 또는
"[전략: 웹 검색만 사용]".

절대 근거 없이 답을 지어내지 않는다.
"""


def build_router_agent(verbose: bool = True) -> Agent:
    """Corrective RAG 라우터 에이전트를 만든다.

    verbose=True면 도구 호출 과정을 콘솔에 실시간으로 보여준다(기본
    콜백 핸들러). verbose=False면 조용히 실행하고 최종 결과만 반환한다
    (콘솔 출력과 최종 답변이 중복 표시되는 것을 피하고 싶을 때 사용).
    """
    model = BedrockModel(model_id=MODEL_ID, region_name=REGION)
    kwargs: dict = {
        "model": model,
        "system_prompt": SYSTEM_PROMPT,
        "tools": [search_knowledge_base, classify_quality, web_search],
    }
    if not verbose:
        kwargs["callback_handler"] = None
    return Agent(**kwargs)


def strategy_tag(answer: str) -> str | None:
    match = re.search(r"\[전략:\s*(.+?)\]", answer)
    return match.group(1) if match else None


def main() -> int:
    agent = build_router_agent(verbose=False)

    cases = [
        ("트라토리아 벨라는 어디에 있고 가격대가 어떻게 되나요?", "KB에 있는 질문", "KB 검색만"),
        ("최근 미쉐린 가이드에 새로 선정된 강남 식당은 어디인가요?", "KB에 없는 질문", "웹 검색"),
    ]

    all_ok = True
    for query, label, expected_strategy_hint in cases:
        print(f"\n{'=' * 70}")
        print(f"[{label}] 질문: {query!r}")
        print("-" * 70)
        result = agent(query)
        answer = str(result)
        print(answer)

        tag = strategy_tag(answer)
        ok = tag is not None and expected_strategy_hint in tag
        all_ok = all_ok and ok
        mark = "✅" if ok else "❌"
        print(f"\n{mark} 감지된 전략 태그: {tag!r} (기대: {expected_strategy_hint!r} 포함)")

    print(f"\n{'=' * 70}")
    print("✅ 완료 기준 충족" if all_ok else "❌ 완료 기준 미충족")
    print("=" * 70)
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
