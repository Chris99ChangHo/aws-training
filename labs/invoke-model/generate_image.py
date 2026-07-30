"""Nova Canvas로 텍스트 프롬프트에서 이미지를 생성한다.

응답은 base64 문자열이므로 디코딩해 PNG로 저장한다.
"""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

# Nova Canvas는 일부 리전에만 있다(확인 시점 기준 us-east-1에 존재,
# us-west-2에는 없음). 리전이 다르면 modelId가 유효하지 않다는 오류가 난다.
REGION = os.environ.get("BEDROCK_REGION", "us-east-1")
MODEL_ID = "amazon.nova-canvas-v1:0"

# 실행 위치(cwd)가 아니라 스크립트 위치 기준으로 저장한다.
OUTPUT_PATH = Path(__file__).parent / "generated_image.png"


def main() -> int:
    """Nova Canvas를 호출해 이미지를 생성하고 PNG로 저장한다."""
    bedrock_runtime = boto3.client("bedrock-runtime", region_name=REGION)

    body = json.dumps(
        {
            "taskType": "TEXT_IMAGE",
            "textToImageParams": {
                "text": "서울 남산타워가 보이는 야경, 사이버펑크 스타일, 고해상도"
            },
            "imageGenerationConfig": {
                "numberOfImages": 1,
                "height": 1024,
                "width": 1024,
                "cfgScale": 8.0,
                # seed를 고정해 같은 프롬프트로 같은 결과를 재현할 수 있게 한다.
                "seed": 42,
            },
        }
    )

    print(f"이미지 생성 중... (리전: {REGION})")
    try:
        response = bedrock_runtime.invoke_model(modelId=MODEL_ID, body=body)
    except ClientError as exc:
        print(f"❌ 호출 실패: {exc}")
        print(
            "   ValidationException이면 이 리전에 Nova Canvas가 없을 수 있다. "
            "BEDROCK_REGION 환경변수로 다른 리전을 지정해 볼 것."
        )
        return 1

    result = json.loads(response["body"].read())
    image_data = base64.b64decode(result["images"][0])
    OUTPUT_PATH.write_bytes(image_data)

    print(f"✅ {OUTPUT_PATH.name} 저장 완료")
    print(f"   크기: {len(image_data) / 1024:.0f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
