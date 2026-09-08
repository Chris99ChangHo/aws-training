"""Dockerfile+앱을 zip으로 묶어 S3에 올리고 MicroVM 이미지로 등록한다."""
from __future__ import annotations

import subprocess
import time

import boto3

REGION = "us-west-2"
ACCOUNT_ID = boto3.client("sts").get_caller_identity()["Account"]
BUCKET = f"microvm-artifacts-{ACCOUNT_ID}"
BASE_IMAGE_ARN = "arn:aws:lambda:us-west-2:aws:microvm-image:al2023-1"
BUILD_ROLE_ARN = f"arn:aws:iam::{ACCOUNT_ID}:role/MicroVMSandboxBuildRole"

microvms_client = boto3.client("lambda-microvms", region_name=REGION)
s3_client = boto3.client("s3", region_name=REGION)


def main() -> int:
    # Dockerfile은 zip 루트에 있어야 한다.
    subprocess.run(["zip", "-r", "sandbox-image.zip", "Dockerfile", "sandbox_server.py"], check=True)
    s3_client.upload_file("sandbox-image.zip", BUCKET, "sandbox-image.zip")

    create_response = microvms_client.create_microvm_image(
        name="python312-sandbox",
        baseImageArn=BASE_IMAGE_ARN,
        buildRoleArn=BUILD_ROLE_ARN,
        codeArtifact={"uri": f"s3://{BUCKET}/sandbox-image.zip"},
        resources=[{"minimumMemoryInMiB": 2048}],
        description="Python 3.12 + pytest sandbox for code execution",
    )
    image_arn = create_response["imageArn"]
    print(f"Image ARN: {image_arn}, state: {create_response['state']}")

    # 빌드는 비동기다 — CREATING → CREATED
    state = create_response["state"]
    while state == "CREATING":
        time.sleep(15)
        image = microvms_client.get_microvm_image(imageIdentifier=image_arn)
        state = image["state"]
        print(f"state: {state}")

    if state != "CREATED":
        raise SystemExit(f"빌드 실패: {image.get('stateReason')}")
    print(f"버전: {image['latestActiveImageVersion']}")
    print(f"IMAGE_ARN={image_arn}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
