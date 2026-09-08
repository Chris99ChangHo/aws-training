"""
03_rerank_search.py

리랭킹 적용 전/후 비교.

두 가지 리랭커를 지원한다.

  A. Bedrock 관리형 리랭커 (Cohere Rerank v3.5)
     Retrieve API의 vectorSearchConfiguration.rerankingConfiguration 으로
     지정하면 Bedrock이 검색 결과를 재정렬해 준다. 가장 간단하지만
     Cohere는 서드파티(AWS Marketplace) 모델이라 계정에
     aws-marketplace:Subscribe / ViewSubscriptions 권한이 필요하다.

  B. LLM 기반 리랭커 (폴백)
     A가 권한 문제로 막힌 환경을 위한 대안. 벡터 검색으로 후보를 넓게
     가져온 뒤, Claude에게 (질의, 후보 문서) 쌍의 관련도를 0~10으로
     채점하게 하고 그 점수로 재정렬한다. Cross-encoder 리랭커와 같은
     "질의와 문서를 함께 보고 판단한다"는 원리를 LLM으로 구현한 것이다.

이 스크립트는 A를 먼저 시도하고, 권한 오류가 나면 자동으로 B로 넘어간다.

사용법:
    python 03_rerank_search.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

REGION = "us-east-1"
ACCOUNT_ID = boto3.client("sts", region_name=REGION).get_caller_identity()["Account"]

QUERY = "서울에서 반나절 역사 코스"

RERANK_MODEL_ARN = f"arn:aws:bedrock:{REGION}::foundation-model/cohere.rerank-v3-5:0"
LLM_MODEL_ID = (
    f"arn:aws:bedrock:{REGION}:{ACCOUNT_ID}:"
    "inference-profile/us.anthropic.claude-sonnet-4-5-20250929-v1:0"
)

# 질문 의도(역사 체험)에 부합하는 관광지
HISTORY_RELATED = {"경복궁", "북촌한옥마을", "DMZ", "창덕궁", "국립중앙박물관"}


def name_of(uri: str) -> str:
    return uri.rsplit("/", 1)[-1].replace(".txt", "")


# ------------------------------------------------------------------ baseline


def retrieve_plain(client, kb_id: str, n: int = 10) -> list[dict]:
    resp = client.retrieve(
        knowledgeBaseId=kb_id,
        retrievalQuery={"text": QUERY},
        retrievalConfiguration={"vectorSearchConfiguration": {"numberOfResults": n}},
    )
    return resp["retrievalResults"]


# ------------------------------------------------------- A. 관리형 리랭커


def retrieve_managed_rerank(client, kb_id: str, n: int = 10) -> list[dict]:
    resp = client.retrieve(
        knowledgeBaseId=kb_id,
        retrievalQuery={"text": QUERY},
        retrievalConfiguration={
            "vectorSearchConfiguration": {
                "numberOfResults": n,
                "rerankingConfiguration": {
                    "type": "BEDROCK_RERANKING_MODEL",
                    "bedrockRerankingConfiguration": {
                        "numberOfRerankedResults": n,
                        "modelConfiguration": {"modelArn": RERANK_MODEL_ARN},
                    },
                },
            }
        },
    )
    return resp["retrievalResults"]


# ------------------------------------------------------- B. LLM 리랭커


SCORE_PROMPT = """당신은 검색 결과 재정렬(reranking) 시스템입니다.

사용자 질의와 후보 문서들이 주어집니다. 각 문서가 질의 의도에 얼마나
부합하는지 0에서 10 사이 정수로 채점하세요.

채점 기준:
- 질의의 핵심 의도(주제, 조건)에 직접 부합하면 높은 점수
- 주제가 다르면 낮은 점수 (예: 역사 코스 질의에 맛집 문서)
- 단순히 단어가 겹치는 것만으로는 높은 점수를 주지 마세요

출력 형식은 아래 JSON만 출력하세요. 설명을 덧붙이지 마세요.
{{"scores": [{{"id": 0, "score": 8}}, {{"id": 1, "score": 3}}]}}

## 사용자 질의
{query}

## 후보 문서
{documents}
"""


def llm_rerank(runtime, results: list[dict], query: str = QUERY) -> list[dict]:
    """LLM에게 (질의, 문서) 관련도를 채점하게 해서 재정렬한다.

    query를 인자로 받아, 이 스크립트를 단독 실행할 때는 기본값(QUERY)을
    쓰고, 04_compare_all.py처럼 다른 질의로 재사용할 때는 전역 변수를
    건드리지 않고 인자로 넘길 수 있게 한다.
    """
    docs_text = "\n\n".join(
        f"[id={i}] 문서명: {name_of(r['location']['s3Location']['uri'])}\n"
        f"내용: {r['content']['text'][:600]}"
        for i, r in enumerate(results)
    )

    prompt = SCORE_PROMPT.format(query=query, documents=docs_text)

    resp = runtime.converse(
        modelId=LLM_MODEL_ID,
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"maxTokens": 1000, "temperature": 0.0},
    )
    text = resp["output"]["message"]["content"][0]["text"]

    # 모델이 코드블록으로 감쌀 수 있으니 JSON 부분만 추출
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise RuntimeError(f"리랭커 응답 파싱 실패: {text[:200]}")
    scores = {s["id"]: s["score"] for s in json.loads(match.group())["scores"]}

    ranked = sorted(
        enumerate(results), key=lambda pair: -scores.get(pair[0], 0)
    )
    out = []
    for idx, r in ranked:
        item = dict(r)
        item["_rerank_score"] = scores.get(idx, 0)
        out.append(item)
    return out


# ------------------------------------------------------------------ 출력


def dedupe(results: list[dict], score_key: str | None = None) -> list[tuple[str, float]]:
    """문서 단위로 최고 점수만 남긴다."""
    best: dict[str, float] = {}
    order: list[str] = []
    for r in results:
        n = name_of(r["location"]["s3Location"]["uri"])
        s = r.get(score_key) if score_key else r.get("score", 0.0)
        s = float(s if s is not None else 0.0)
        if n not in best:
            best[n] = s
            order.append(n)
        else:
            best[n] = max(best[n], s)
    return [(n, best[n]) for n in order]


def show(title: str, ranking: list[tuple[str, float]]) -> None:
    print(f"\n{'=' * 70}")
    print(title)
    print("-" * 70)
    for i, (n, s) in enumerate(ranking, 1):
        tag = " [역사]" if n in HISTORY_RELATED else ""
        print(f"  {i}. {n:14s} score={s:.4f}{tag}")


def hits_in_top(ranking: list[tuple[str, float]], k: int = 3) -> int:
    return len({n for n, _ in ranking[:k]} & HISTORY_RELATED)


def main() -> int:
    kb_info_path = Path(__file__).parent / "kb_info.json"
    with open(kb_info_path, encoding="utf-8") as fh:
        kb_id = json.load(fh)["knowledgeBaseId"]

    client = boto3.client("bedrock-agent-runtime", region_name=REGION)
    runtime = boto3.client("bedrock-runtime", region_name=REGION)

    print(f"질의: {QUERY!r}")

    before_raw = retrieve_plain(client, kb_id)
    before = dedupe(before_raw)
    show("리랭킹 전 (벡터 유사도만)", before)

    # A. 관리형 리랭커 시도
    used = None
    after: list[tuple[str, float]] = []
    try:
        after_raw = retrieve_managed_rerank(client, kb_id)
        after = dedupe(after_raw)
        used = "Bedrock 관리형 리랭커 (Cohere Rerank v3.5)"
    except ClientError as err:
        msg = str(err)
        if "marketplace" in msg.lower() or "AccessDenied" in msg:
            print("\n[!] Cohere Rerank 사용 불가 (AWS Marketplace 구독이 계정 정책으로 차단됨)")
            print("    -> LLM 기반 리랭커로 대체합니다.")
            after_raw = llm_rerank(runtime, before_raw)
            after = dedupe(after_raw, score_key="_rerank_score")
            used = "LLM 리랭커 (Claude Sonnet 4.5, 폴백)"
        else:
            raise

    show(f"리랭킹 후 - {used}", after)

    b, a = hits_in_top(before), hits_in_top(after)
    print(f"\n{'=' * 70}")
    print("비교 요약")
    print(f"  사용한 리랭커            : {used}")
    print(f"  리랭킹 전 상위3          : {[n for n, _ in before[:3]]} (역사 {b}/3)")
    print(f"  리랭킹 후 상위3          : {[n for n, _ in after[:3]]} (역사 {a}/3)")

    ok = a >= b and a >= 2
    print(f"\n  질문 의도에 맞는 관광지가 상위로 올라옴: {ok}")
    print("=" * 70)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
