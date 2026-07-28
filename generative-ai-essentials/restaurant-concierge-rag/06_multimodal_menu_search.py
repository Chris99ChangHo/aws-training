"""
06_multimodal_menu_search.py

메뉴판 데이터(이미지의 텍스트 대리 데이터, data/menu_data.json)를
캡셔닝·벡터 인덱싱하여 텍스트 질문으로 메뉴·가격·분위기를 검색하는
크로스모달 RAG 파이프라인.

3단계로 구성된다:
  1. Vision 분석  : 모델이 메뉴 데이터를 읽고 예산 내 추천을 도출
  2. 캡셔닝·인덱싱 : 식당별 캡션 생성 -> Titan Embed V2로 임베딩 -> FAISS 인덱싱
  3. 크로스모달 검색: 텍스트 질문으로 캡션 인덱스를 검색하고 근거 기반 답변

이 스크립트에서는 "메뉴판 이미지"를 실제 이미지 대신 텍스트 대리
데이터(JSON)로 받으므로, Converse API의 image 블록 대신 텍스트 블록으로
모델에 전달한다. (도전 과제: 실제 이미지 분석은 image 블록으로 확장)

완료 기준:
  - 트라토리아 벨라·한우명가 2곳을 Vision 패턴으로 분석해 예산 내
    데이트 추천 도출
  - 캡션 2건을 1024차원으로 임베딩해 FAISS 인덱스에 저장
  - 텍스트 질문 3종(데이트 분위기·2만원 이하 파스타·가족 모임)으로
    크로스모달 검색 및 근거 기반 답변
  - 데이터에 없는 내용은 "확인할 수 없습니다"로 답변

사용법:
    python 06_multimodal_menu_search.py
"""

from __future__ import annotations

import json
from pathlib import Path

import boto3
import faiss
import numpy as np

REGION = "us-west-2"
EMBED_MODEL_ID = "amazon.titan-embed-text-v2:0"
EMBED_DIMENSION = 1024

DATA_PATH = Path(__file__).parent / "data" / "menu_data.json"
INDEX_PATH = Path(__file__).parent / "data" / "menu_index.faiss"
CAPTIONS_PATH = Path(__file__).parent / "data" / "menu_captions.json"

_bedrock_runtime = boto3.client("bedrock-runtime", region_name=REGION)
_account_id = boto3.client("sts", region_name=REGION).get_caller_identity()["Account"]
GEN_MODEL_ARN = (
    f"arn:aws:bedrock:{REGION}:{_account_id}:"
    "inference-profile/us.anthropic.claude-sonnet-4-6"
)


def log(msg: str) -> None:
    print(msg, flush=True)


def load_menu_data() -> list[dict]:
    with open(DATA_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def invoke_claude(prompt: str) -> str:
    resp = _bedrock_runtime.converse(
        modelId=GEN_MODEL_ARN,
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"maxTokens": 1000, "temperature": 0.2},
    )
    return resp["output"]["message"]["content"][0]["text"]


# ------------------------------------------------------------ 1. Vision 분석


def analyze_for_budget_date(restaurant: dict, budget: int) -> str:
    """메뉴 데이터를 모델이 '읽고' 예산 내 데이트 추천을 도출한다.

    실제 이미지라면 Converse API의 image 블록으로 전달하지만, 여기서는
    메뉴판의 텍스트 대리 데이터를 그대로 모델에 준다 - 이미지를 텍스트로
    옮겨 적은 캡션이 아니라 모델이 원본 데이터를 직접 해석하게 하는 것이
    'Vision 분석' 단계의 핵심이다 (실제 이미지 확장 시 image 블록만
    교체하면 동일한 프롬프트 구조를 재사용할 수 있다).
    """
    menu_json = json.dumps(restaurant, ensure_ascii=False, indent=2)
    prompt = f"""다음은 식당 메뉴판 데이터입니다.

{menu_json}

이 식당에서 예산 {budget:,}원 이내로 2인 데이트 메뉴를 구성해 추천해
주세요. 메뉴 이름과 가격을 근거로 제시하고, 예산을 초과하면 안 됩니다.
데이터에 없는 메뉴는 언급하지 마세요."""
    return invoke_claude(prompt)


# ------------------------------------------------------ 2. 캡셔닝·임베딩·인덱싱


def generate_caption(restaurant: dict) -> str:
    """식당 데이터를 하나의 자연어 캡션으로 요약한다 (이미지 캡셔닝에
    대응하는 단계 - 구조화된 메뉴 데이터를 검색 가능한 텍스트로 변환).
    """
    items_text = ", ".join(
        f"{item['name']}({item['price']:,}원, {item['description']})"
        for item in restaurant["items"]
    )
    return (
        f"{restaurant['restaurant']} ({restaurant['cuisine']}) - "
        f"메뉴: {items_text}. 분위기: {restaurant['atmosphere']}"
    )


def embed_text(text: str) -> np.ndarray:
    resp = _bedrock_runtime.invoke_model(
        modelId=EMBED_MODEL_ID,
        body=json.dumps({"inputText": text, "dimensions": EMBED_DIMENSION}),
    )
    body = json.loads(resp["body"].read())
    return np.array(body["embedding"], dtype="float32")


def build_index(restaurants: list[dict]) -> tuple[faiss.IndexFlatL2, list[dict]]:
    captions = []
    vectors = []
    for r in restaurants:
        caption = generate_caption(r)
        vec = embed_text(caption)
        captions.append({"restaurant": r["restaurant"], "caption": caption})
        vectors.append(vec)
        log(f"  [캡션] {r['restaurant']}: {caption[:60]}...")

    matrix = np.vstack(vectors)
    index = faiss.IndexFlatL2(EMBED_DIMENSION)
    index.add(matrix)

    return index, captions


def save_index(index: faiss.IndexFlatL2, captions: list[dict]) -> None:
    faiss.write_index(index, str(INDEX_PATH))
    with open(CAPTIONS_PATH, "w", encoding="utf-8") as fh:
        json.dump(captions, fh, ensure_ascii=False, indent=2)


def load_index() -> tuple[faiss.IndexFlatL2, list[dict]]:
    index = faiss.read_index(str(INDEX_PATH))
    with open(CAPTIONS_PATH, encoding="utf-8") as fh:
        captions = json.load(fh)
    return index, captions


# ------------------------------------------------------------ 3. 크로스모달 검색


def search(
    index: faiss.IndexFlatL2, captions: list[dict], query: str, k: int = 2
) -> list[tuple[dict, float]]:
    query_vec = embed_text(query).reshape(1, -1)
    distances, indices = index.search(query_vec, k)
    results = []
    for dist, idx in zip(distances[0], indices[0]):
        if idx < 0:
            continue
        results.append((captions[idx], float(dist)))
    return results


def answer_with_grounding(query: str, hits: list[tuple[dict, float]], restaurants: list[dict]) -> str:
    """검색된 캡션만 근거로 답변한다. 근거가 없으면 확인할 수 없다고 답한다."""
    if not hits:
        return "확인할 수 없습니다. (관련 데이터를 찾지 못했습니다)"

    context = "\n\n".join(f"- {h[0]['caption']}" for h in hits)
    prompt = f"""아래는 식당 메뉴/분위기 데이터에서 검색된 캡션입니다.
이 정보에 있는 내용만 근거로 답변하세요. 캡션에 없는 내용은 절대
지어내지 말고 "확인할 수 없습니다"라고 답하세요.

## 검색된 캡션
{context}

## 질문
{query}
"""
    return invoke_claude(prompt)


def main() -> int:
    restaurants = load_menu_data()
    log(f"[data] 메뉴 데이터 {len(restaurants)}곳 로드: "
        f"{[r['restaurant'] for r in restaurants]}")

    # 1. Vision 분석 - 예산 내 데이트 추천
    log("\n" + "=" * 70)
    log("1단계: Vision 분석 - 예산 내 데이트 추천")
    log("=" * 70)
    for r in restaurants:
        log(f"\n--- {r['restaurant']} (예산 50,000원) ---")
        recommendation = analyze_for_budget_date(r, budget=50000)
        log(recommendation)

    # 2. 캡셔닝 -> 임베딩 -> FAISS 인덱싱
    log("\n" + "=" * 70)
    log("2단계: 캡셔닝 -> 임베딩(Titan Embed V2, 1024차원) -> FAISS 인덱싱")
    log("=" * 70)
    index, captions = build_index(restaurants)
    save_index(index, captions)
    log(f"\n[index] FAISS 인덱스 저장: {INDEX_PATH} (문서 {index.ntotal}건, {EMBED_DIMENSION}차원)")

    # 3. 크로스모달 검색 - 텍스트 질문 3종
    log("\n" + "=" * 70)
    log("3단계: 크로스모달 검색 (텍스트 질문 -> 캡션 인덱스 검색 -> 근거 기반 답변)")
    log("=" * 70)

    queries = [
        "2인 데이트하기 좋은 분위기의 식당은 어디인가요?",
        "2만원 이하로 먹을 수 있는 파스타가 있는 곳은?",
        "가족 모임하기 좋은 식당 추천해주세요",
    ]

    ok = True
    for q in queries:
        log(f"\n--- 질문: {q!r} ---")
        hits = search(index, captions, q, k=2)
        log("검색된 캡션:")
        for cap, dist in hits:
            log(f"  - [{cap['restaurant']}] distance={dist:.4f}")
        answer = answer_with_grounding(q, hits, restaurants)
        log(f"답변: {answer}")

    # 데이터에 없는 내용 검증 - 근거 기반 응답 확인
    log(f"\n--- 데이터에 없는 질문 검증: '이 식당에 발렛 파킹이 있나요?' ---")
    oos_query = "이 식당에 발렛 파킹이 있나요?"
    hits = search(index, captions, oos_query, k=2)
    answer = answer_with_grounding(oos_query, hits, restaurants)
    log(f"답변: {answer}")
    # 모델이 "정보가 없다/포함되어 있지 않다/확인할 수 없다" 등 다양한
    # 표현으로 답할 수 있으므로, 근거 부재를 인정하는 패턴을 넓게 잡는다.
    # (2026-07-28: "확인할 수 없" 단일 패턴만 썼다가 "포함되어 있지
    # 않습니다"라는 정답 표현을 놓쳐 오탐이 발생한 것을 발견하고 수정.)
    refusal_patterns = ["확인할 수 없", "포함되어 있지 않", "정보가 없", "언급되어 있지 않", "찾을 수 없"]
    has_refusal = any(p in answer for p in refusal_patterns)
    ok = ok and has_refusal
    log(f"{'✅' if has_refusal else '❌'} 근거 없는 정보에 대해 정직하게 답변: {has_refusal}")

    log("\n" + "=" * 70)
    log("✅ 완료" if ok else "❌ 완료 기준 미충족")
    log("=" * 70)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
