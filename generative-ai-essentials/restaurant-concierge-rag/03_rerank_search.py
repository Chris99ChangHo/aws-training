"""
03_rerank_search.py

리랭킹 적용 전/후 비교. Cohere Rerank v3.5 사용.

세부 절차·원리(Cohere Marketplace 차단 시 LLM 리랭커 폴백 로직 등)는
seoul-travel-planner-kb/03_rerank_search.py 참고. 이 스크립트는 이
미션의 고유 질문·모델만 담는다.

사용법:
    python 03_rerank_search.py
"""

from __future__ import annotations

import json
from pathlib import Path

import boto3

REGION = "us-west-2"
QUERY = "회식하기 좋은 한식당 추천해 주세요"
RERANK_MODEL_ARN = f"arn:aws:bedrock:{REGION}::foundation-model/cohere.rerank-v3-5:0"

HISTORY_RELATED = {"restaurant-03.docx", "restaurant-08.docx"}  # 한식당 2곳


def name_of(uri: str) -> str:
    return uri.rsplit("/", 1)[-1]


def dedupe(results: list[dict]) -> list[tuple[str, float]]:
    best: dict[str, float] = {}
    order: list[str] = []
    for r in results:
        n = name_of(r["location"]["s3Location"]["uri"])
        s = r.get("score", 0.0)
        if n not in best:
            best[n] = s
            order.append(n)
        else:
            best[n] = max(best[n], s)
    return [(n, best[n]) for n in order]


def retrieve_plain(client, kb_id: str) -> list[dict]:
    resp = client.retrieve(
        knowledgeBaseId=kb_id,
        retrievalQuery={"text": QUERY},
        retrievalConfiguration={"vectorSearchConfiguration": {"numberOfResults": 10}},
    )
    return resp["retrievalResults"]


def retrieve_reranked(client, kb_id: str) -> list[dict]:
    resp = client.retrieve(
        knowledgeBaseId=kb_id,
        retrievalQuery={"text": QUERY},
        retrievalConfiguration={
            "vectorSearchConfiguration": {
                "numberOfResults": 10,
                "rerankingConfiguration": {
                    "type": "BEDROCK_RERANKING_MODEL",
                    "bedrockRerankingConfiguration": {
                        "numberOfRerankedResults": 10,
                        "modelConfiguration": {"modelArn": RERANK_MODEL_ARN},
                    },
                },
            }
        },
    )
    return resp["retrievalResults"]


def show(title: str, results: list[tuple[str, float]]) -> None:
    print(f"\n{'=' * 60}")
    print(title)
    print("-" * 60)
    for i, (n, s) in enumerate(results, 1):
        tag = " [한식]" if n in HISTORY_RELATED else ""
        print(f"  {i}. {n:20s} score={s:.4f}{tag}")


def main() -> int:
    kb_info_path = Path(__file__).parent / "kb_info.json"
    with open(kb_info_path, encoding="utf-8") as fh:
        kb_id = json.load(fh)["knowledgeBaseId"]
    client = boto3.client("bedrock-agent-runtime", region_name=REGION)

    print(f"질의: {QUERY!r}")

    before = dedupe(retrieve_plain(client, kb_id))
    show("리랭킹 전 (벡터 유사도만)", before)

    after = dedupe(retrieve_reranked(client, kb_id))
    show("리랭킹 후 (Cohere Rerank v3.5)", after)

    b = len({n for n, _ in before[:3]} & HISTORY_RELATED)
    a = len({n for n, _ in after[:3]} & HISTORY_RELATED)
    print(f"\n{'=' * 60}")
    print(f"상위 3개 중 한식당 비율: 전 {b}/3 -> 후 {a}/3")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
