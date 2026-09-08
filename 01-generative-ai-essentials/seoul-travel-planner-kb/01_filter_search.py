"""
01_filter_search.py

메타데이터 필터 검색 - equals / andAll / orAll / 부분일치

메타데이터 키: category, location, duration_hours

케이스:
  0. 필터 없음 (baseline)
  1. equals        : category == "역사/문화"
  2. 부분일치      : category 에 "역사" 포함 (역사/문화 + 역사/안보)
  3. andAll        : category == "역사/문화" AND duration_hours <= 2   <- 도전 과제
  4. orAll         : category == "자연/공원" OR category == "랜드마크"
  5. andAll(3중)   : 역사/문화 AND 종로구 AND 2시간 이하

사용법:
    python 01_filter_search.py
"""

from __future__ import annotations

import json
from pathlib import Path

import boto3

REGION = "us-east-1"
QUERY = "서울에서 반나절 역사 코스"


def name_of(uri: str) -> str:
    return uri.rsplit("/", 1)[-1].replace(".txt", "")


def search(client, kb_id: str, query: str, filter_: dict | None) -> list[tuple[str, float, str]]:
    cfg: dict = {"numberOfResults": 10}
    if filter_ is not None:
        cfg["filter"] = filter_

    resp = client.retrieve(
        knowledgeBaseId=kb_id,
        retrievalQuery={"text": query},
        retrievalConfiguration={"vectorSearchConfiguration": cfg},
    )

    # 같은 문서의 여러 청크가 올 수 있으므로 문서 단위로 최고 점수만 남긴다.
    best: dict[str, tuple[float, str]] = {}
    for r in resp["retrievalResults"]:
        n = name_of(r["location"]["s3Location"]["uri"])
        score = r.get("score", 0.0)
        meta = r.get("metadata", {})
        label = f"{meta.get('category', '?')} / {meta.get('location', '?')} / {meta.get('duration_hours', '?')}h"
        if n not in best or score > best[n][0]:
            best[n] = (score, label)

    return sorted(
        ((n, s, l) for n, (s, l) in best.items()), key=lambda x: -x[1]
    )


def show(title: str, filter_: dict | None, results: list[tuple[str, float, str]]) -> None:
    print(f"\n{'=' * 70}")
    print(f"{title}")
    if filter_ is not None:
        print(f"filter: {json.dumps(filter_, ensure_ascii=False)}")
    else:
        print("filter: (없음)")
    print("-" * 70)
    if not results:
        print("  (결과 없음)")
    for i, (n, s, label) in enumerate(results, 1):
        print(f"  {i}. {n:14s} score={s:.4f}  [{label}]")


def main() -> int:
    kb_info_path = Path(__file__).parent / "kb_info.json"
    with open(kb_info_path, encoding="utf-8") as fh:
        kb_id = json.load(fh)["knowledgeBaseId"]
    client = boto3.client("bedrock-agent-runtime", region_name=REGION)

    print(f"질의: {QUERY!r}")

    cases: list[tuple[str, dict | None]] = [
        ("0. 필터 없음 (baseline)", None),
        (
            "1. equals - category == '역사/문화'",
            {"equals": {"key": "category", "value": "역사/문화"}},
        ),
        (
            "2. 부분일치 - category 에 '역사' 포함",
            {"stringContains": {"key": "category", "value": "역사"}},
        ),
        (
            "3. andAll - 역사/문화 AND 소요시간 2시간 이하  [도전 과제]",
            {
                "andAll": [
                    {"equals": {"key": "category", "value": "역사/문화"}},
                    {"lessThanOrEquals": {"key": "duration_hours", "value": 2}},
                ]
            },
        ),
        (
            "4. orAll - 자연/공원 OR 랜드마크",
            {
                "orAll": [
                    {"equals": {"key": "category", "value": "자연/공원"}},
                    {"equals": {"key": "category", "value": "랜드마크"}},
                ]
            },
        ),
        (
            "5. andAll(3중) - 역사/문화 AND 종로구 AND 2시간 이하",
            {
                "andAll": [
                    {"equals": {"key": "category", "value": "역사/문화"}},
                    {"equals": {"key": "location", "value": "종로구"}},
                    {"lessThanOrEquals": {"key": "duration_hours", "value": 2}},
                ]
            },
        ),
    ]

    for title, filter_ in cases:
        results = search(client, kb_id, QUERY, filter_)
        show(title, filter_, results)

    print(f"\n{'=' * 70}")
    print("정리: 필터를 좁힐수록 무관한 카테고리가 제거되고, andAll로")
    print("      카테고리와 소요시간 조건을 동시에 만족하는 결과만 남는다.")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
