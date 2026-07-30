"""InvokeModelWithResponseStream의 이벤트 구조를 확인한다.

스트리밍 응답은 텍스트 델타만 오는 것이 아니라 message_start,
content_block_delta, message_stop 등 타입이 다른 이벤트가 섞여 온다.
UI에 붙이려면 어떤 타입을 골라 써야 하는지 알아야 하므로, 여기서는
모든 이벤트 타입을 그대로 출력한다.
"""

from __future__ import annotations

import json
import os

import boto3
from botocore.exceptions import ClientError

REGION = os.environ.get("BEDROCK_REGION", "us-west-2")
MODEL_ID = "us.anthropic.claude-sonnet-4-6"

# 이벤트 타입 확인이 목적이므로 응답이 길 필요가 없다.
MAX_TOKENS = 100


def main() -> int:
    """스트리밍 호출을 실행하고 수신 이벤트 타입을 순서대로 출력한다."""
    bedrock_runtime = boto3.client("bedrock-runtime", region_name=REGION)

    body = json.dumps(
        {
            "anthropic_version": "bedrock-2023-05-31",
            "messages": [{"role": "user", "content": "안녕하세요"}],
            "max_tokens": MAX_TOKENS,
        }
    )

    try:
        response = bedrock_runtime.invoke_model_with_response_stream(
            modelId=MODEL_ID,
            contentType="application/json",
            accept="application/json",
            body=body,
        )
    except ClientError as exc:
        print(f"❌ 호출 실패 ({REGION}): {exc}")
        return 1

    for event in response["body"]:
        chunk = json.loads(event["chunk"]["bytes"])
        # 이벤트 원문이 길 수 있어 앞부분만 잘라 타입 구분만 확인한다.
        preview = json.dumps(chunk, ensure_ascii=False)[:100]
        print(f"[{chunk['type']}] {preview}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
