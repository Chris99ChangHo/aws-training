"""InvokeModel API로 Llama 4 모델을 직접 호출한다.

Converse API와 달리 InvokeModel은 모델 제공자별 네이티브 요청 포맷을
그대로 요구한다. Llama는 Claude의 messages 배열이 아니라 특수 토큰이
박힌 단일 prompt 문자열을 받는다 — 이 차이를 확인하는 것이 목적이다.
"""

from __future__ import annotations

import json
import os

import boto3
from botocore.exceptions import ClientError

# 리전은 환경마다 다르고 모델 가용 리전도 리전별로 갈리므로 환경변수로 받는다.
REGION = os.environ.get("BEDROCK_REGION", "us-west-2")
MODEL_ID = "us.meta.llama4-scout-17b-instruct-v1:0"

# Llama 4 네이티브 프롬프트 포맷. 헤더 토큰으로 역할을 구분하고,
# 마지막에 assistant 헤더를 열어두면 모델이 그 뒤를 이어 생성한다.
PROMPT = """<|begin_of_text|><|start_header_id|>user<|end_header_id|>

서버리스 아키텍처의 장점 3가지를 설명하세요.<|eot_id|><|start_header_id|>assistant<|end_header_id|>
"""


def main() -> int:
    """Llama 4를 InvokeModel로 호출하고 응답과 토큰 사용량을 출력한다."""
    bedrock_runtime = boto3.client("bedrock-runtime", region_name=REGION)

    body = json.dumps(
        {
            "prompt": PROMPT,
            "max_gen_len": 512,
            "temperature": 0.7,
            "top_p": 0.9,
        }
    )

    try:
        response = bedrock_runtime.invoke_model(
            modelId=MODEL_ID,
            contentType="application/json",
            accept="application/json",
            body=body,
        )
    except ClientError as exc:
        # ValidationException은 대개 modelId가 이 리전 카탈로그에 없다는 뜻이다.
        print(f"❌ 호출 실패 ({REGION}): {exc}")
        return 1

    # Llama는 Claude의 content 블록 배열이 아니라 generation 문자열을 반환한다.
    result = json.loads(response["body"].read())
    print(result["generation"])
    print("\n--- 토큰 사용량 ---")
    print(f"입력: {result['prompt_token_count']} 토큰")
    print(f"출력: {result['generation_token_count']} 토큰")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
