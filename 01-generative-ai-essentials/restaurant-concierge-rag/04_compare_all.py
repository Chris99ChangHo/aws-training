"""
04_compare_all.py

동일 질문 "회식하기 좋은 한식당 추천해 주세요"로 기본/필터/하이브리드/
리랭킹 4가지 결과를 나란히 비교한다.

사용법:
    python 04_compare_all.py
"""

from __future__ import annotations

import json
from pathlib import Path

import boto3

REGION = "us-west-2"
QUERY = "회식하기 좋은 한식당 추천해 주세요"
RERANK_MODEL_ARN = f"arn:aws:bedrock:{REGION}::foundation-model/cohere.rerank-v3-5:0"

HAN_SIK = {"restaurant-03.docx", "restaurant-08.docx"}


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


def run(client, kb_id: str, cfg: dict) -> list[dict]:
    resp = client.retrieve(
        knowledgeBaseId=kb_id,
        retrievalQuery={"text": QUERY},
        retrievalConfiguration={"vectorSearchConfiguration": cfg},
    )
    return resp["retrievalResults"]


def print_table(results: dict[str, list[tuple[str, float]]]) -> None:
    labels = list(results.keys())
    rows = max(len(v) for v in results.values())
    col = 26

    header = "순위".ljust(5) + "".join(l.ljust(col) for l in labels)
    print(header)
    print("-" * len(header))
    for i in range(rows):
        row = f"{i + 1:<5}"
        for label in labels:
            items = results[label]
            if i < len(items):
                n, s = items[i]
                tag = "*" if n in HAN_SIK else " "
                cell = f"{n}{tag}({s:.3f})"
            else:
                cell = "-"
            row += cell.ljust(col)
        print(row)
    print("\n(* = 한식당: 강남한우명가/서울갈비강남본점)")


def main() -> int:
    kb_info_path = Path(__file__).parent / "kb_info.json"
    with open(kb_info_path, encoding="utf-8") as fh:
        kb_id = json.load(fh)["knowledgeBaseId"]
    client = boto3.client("bedrock-agent-runtime", region_name=REGION)

    print(f"질의: {QUERY!r}\n")

    results: dict[str, list[tuple[str, float]]] = {}

    results["1.기본검색"] = dedupe(
        run(client, kb_id, {"numberOfResults": 10, "overrideSearchType": "SEMANTIC"})
    )
    results["2.필터(한식)"] = dedupe(
        run(
            client,
            kb_id,
            {
                "numberOfResults": 10,
                "filter": {"equals": {"key": "category", "value": "한식"}},
            },
        )
    )
    results["3.하이브리드"] = dedupe(
        run(client, kb_id, {"numberOfResults": 10, "overrideSearchType": "HYBRID"})
    )
    results["4.리랭킹"] = dedupe(
        run(
            client,
            kb_id,
            {
                "numberOfResults": 10,
                "rerankingConfiguration": {
                    "type": "BEDROCK_RERANKING_MODEL",
                    "bedrockRerankingConfiguration": {
                        "numberOfRerankedResults": 10,
                        "modelConfiguration": {"modelArn": RERANK_MODEL_ARN},
                    },
                },
            },
        )
    )

    print_table(results)

    print(f"\n{'=' * 70}")
    print("상위 3개 중 한식당 비율")
    print("-" * 70)
    baseline = None
    for label, items in results.items():
        top = [n for n, _ in items[:3]]
        hits = len(set(top) & HAN_SIK)
        if baseline is None:
            baseline = hits
        delta = hits - baseline
        sign = "(기준)" if label.startswith("1.") else f"({delta:+d})"
        print(f"  {label:14s} {hits}/3 {sign:8s} {top}")

    print(f"\n{'=' * 70}")
    print("해석")
    print("  - 기본 검색: 한식 무관 문서(restaurants-all.xlsx, restaurant-07)가")
    print("               섞여 1/3만 한식당.")
    print("  - 필터     : category='한식' equals로 정확히 2곳만 반환, 정밀도 최고.")
    print("  - 하이브리드: '한식당'은 일반 명사라 고유 키워드 효과가 약해")
    print("               기본 검색과 순위 변화가 거의 없음.")
    print("  - 리랭킹   : 필터처럼 자르지 않으면서 의미 기반으로 한식당을")
    print("               상위로 재배치 (1/3 -> 2/3).")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
