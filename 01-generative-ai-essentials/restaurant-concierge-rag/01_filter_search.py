"""
01_filter_search.py

메타데이터 필터 검색.

세부 절차·코드 원리는 seoul-travel-planner-kb/01_filter_search.py
참고. 이 스크립트는 이 미션의 고유 값(필터 조건·데이터)만 담는다.

케이스:
  0. 필터 없음 (baseline)
  1. equals   : category == "한식"
  2. andAll   : category == "한식" AND max_party_size >= 20
                (greaterThanOrEquals)

사용법:
    python 01_filter_search.py
"""

from __future__ import annotations

import json
from pathlib import Path

import boto3

REGION = "us-west-2"
QUERY = "회식하기 좋은 한식당 추천해 주세요"


def name_of(uri: str) -> str:
    return uri.rsplit("/", 1)[-1]


def search(client, kb_id: str, filter_: dict | None) -> list[tuple[str, float]]:
    cfg: dict = {"numberOfResults": 10}
    if filter_ is not None:
        cfg["filter"] = filter_

    resp = client.retrieve(
        knowledgeBaseId=kb_id,
        retrievalQuery={"text": QUERY},
        retrievalConfiguration={"vectorSearchConfiguration": cfg},
    )

    best: dict[str, float] = {}
    order: list[str] = []
    for r in resp["retrievalResults"]:
        n = name_of(r["location"]["s3Location"]["uri"])
        s = r.get("score", 0.0)
        if n not in best:
            best[n] = s
            order.append(n)
        else:
            best[n] = max(best[n], s)
    return [(n, best[n]) for n in order]


def show(title: str, filter_: dict | None, results: list[tuple[str, float]]) -> None:
    print(f"\n{'=' * 70}")
    print(title)
    if filter_ is not None:
        print(f"filter: {json.dumps(filter_, ensure_ascii=False)}")
    else:
        print("filter: (없음)")
    print("-" * 70)
    if not results:
        print("  (결과 없음)")
    for i, (n, s) in enumerate(results, 1):
        print(f"  {i}. {n:14s} score={s:.4f}")


def main() -> int:
    kb_info_path = Path(__file__).parent / "kb_info.json"
    with open(kb_info_path, encoding="utf-8") as fh:
        kb_id = json.load(fh)["knowledgeBaseId"]
    client = boto3.client("bedrock-agent-runtime", region_name=REGION)

    print(f"질의: {QUERY!r}")

    cases: list[tuple[str, dict | None]] = [
        ("0. 필터 없음 (baseline)", None),
        (
            "1. equals - category == '한식'",
            {"equals": {"key": "category", "value": "한식"}},
        ),
        (
            "2. andAll - category == '한식' AND max_party_size >= 20",
            {
                "andAll": [
                    {"equals": {"key": "category", "value": "한식"}},
                    {"greaterThanOrEquals": {"key": "max_party_size", "value": 20}},
                ]
            },
        ),
    ]

    for title, filter_ in cases:
        results = search(client, kb_id, filter_)
        show(title, filter_, results)

    print(f"\n{'=' * 70}")
    print("정리: category='한식' 필터로 한식당만 남기고, max_party_size>=20을")
    print("      추가하면 대규모 회식이 가능한 곳(예: 서울갈비 강남본점, 40명)만")
    print("      남는다. 강남한우명가(30명)도 조건을 만족하면 함께 남는다.")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
