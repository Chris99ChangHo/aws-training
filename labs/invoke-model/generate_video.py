"""Nova Reel로 텍스트 프롬프트에서 비디오를 생성한다(비동기 API).

이미지와 달리 비디오 생성은 StartAsyncInvoke로 작업을 제출하고 결과를
S3로 받는다. 응답 본문에 비디오가 담겨 오지 않으므로 출력 버킷이
반드시 필요하며, 버킷은 모델을 호출하는 리전과 같은 리전에 있어야 한다.
"""

from __future__ import annotations

import os
import time

import boto3
from botocore.exceptions import ClientError

REGION = os.environ.get("BEDROCK_REGION", "us-east-1")
MODEL_ID = "amazon.nova-reel-v1:1"

# 폴링 상한. 무한 대기를 막기 위해 최대 대기 시간을 명시한다.
POLL_INTERVAL_SECONDS = 30
MAX_WAIT_SECONDS = 900


def resolve_output_bucket() -> str:
    """출력 S3 버킷명을 결정한다.

    NOVA_REEL_BUCKET 환경변수가 있으면 그대로 쓰고, 없으면 호출자
    계정 ID로 기본 이름을 만든다. 계정 ID를 코드에 박지 않기 위해
    런타임에 STS로 조회한다.
    """
    bucket = os.environ.get("NOVA_REEL_BUCKET")
    if bucket:
        return bucket

    account_id = boto3.client("sts", region_name=REGION).get_caller_identity()[
        "Account"
    ]
    return f"workshop-nova-reel-{account_id}"


def main() -> int:
    """비디오 생성 작업을 제출하고 완료까지 폴링한다."""
    bedrock_runtime = boto3.client("bedrock-runtime", region_name=REGION)

    try:
        bucket = resolve_output_bucket()
    except ClientError as exc:
        print(f"❌ 계정 정보 조회 실패: {exc}")
        return 1

    s3_uri = f"s3://{bucket}/output/"
    print(f"비디오 생성 시작... (리전: {REGION}, 출력: {s3_uri})")

    try:
        response = bedrock_runtime.start_async_invoke(
            modelId=MODEL_ID,
            modelInput={
                "taskType": "TEXT_VIDEO",
                "textToVideoParams": {
                    "text": "드론이 한강 위를 날아가며 촬영하는 시네마틱 영상"
                },
                "videoGenerationConfig": {
                    "durationSeconds": 6,
                    "fps": 24,
                    "dimension": "1280x720",
                },
            },
            outputDataConfig={"s3OutputDataConfig": {"s3Uri": s3_uri}},
        )
    except ClientError as exc:
        print(f"❌ 작업 제출 실패: {exc}")
        print(
            "   ValidationException이면 이 리전에 Nova Reel이 없거나, "
            f"버킷 {bucket}이 없거나 리전이 다를 수 있다."
        )
        return 1

    invocation_arn = response["invocationArn"]
    print(f"비동기 작업 ARN: {invocation_arn}")

    deadline = time.monotonic() + MAX_WAIT_SECONDS
    while time.monotonic() < deadline:
        status = bedrock_runtime.get_async_invoke(invocationArn=invocation_arn)
        state = status["status"]
        print(f"  상태: {state}")

        if state == "Completed":
            output_uri = status["outputDataConfig"]["s3OutputDataConfig"]["s3Uri"]
            print(f"✅ 비디오 생성 완료: {output_uri}")
            return 0
        if state == "Failed":
            print(f"❌ 실패: {status.get('failureMessage', '알 수 없음')}")
            return 1

        time.sleep(POLL_INTERVAL_SECONDS)

    print(f"❌ {MAX_WAIT_SECONDS}초 내 완료되지 않음. 작업은 계속 진행 중일 수 있다.")
    print(f"   확인: aws bedrock-runtime get-async-invoke --invocation-arn {invocation_arn}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
