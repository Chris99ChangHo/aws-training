"""Nova Reel로 비디오 생성 (비동기)."""
import boto3
import json
import time

REGION = "us-west-2"
bedrock_runtime = boto3.client("bedrock-runtime", region_name=REGION)

# --- S3 출력 경로 ---
account_id = boto3.client("sts").get_caller_identity()["Account"]
s3_uri = f"s3://workshop-nova-reel-{account_id}/output/"

print("비디오 생성 시작...")
response = bedrock_runtime.start_async_invoke(
    modelId="amazon.nova-reel-v1:1",
    modelInput={
        "taskType": "TEXT_VIDEO",
        "textToVideoParams": {
            "text": "드론이 한강 위를 날아가며 촬영하는 시네마틱 영상"
        },
        "videoGenerationConfig": {
            "durationSeconds": 6,
            "fps": 24,
            "dimension": "1280x720"
        }
    },
    outputDataConfig={
        "s3OutputDataConfig": {"s3Uri": s3_uri}
    }
)

invocation_arn = response["invocationArn"]
print(f"비동기 작업 ARN: {invocation_arn}")

# --- 완료까지 폴링 ---
while True:
    status = bedrock_runtime.get_async_invoke(invocationArn=invocation_arn)
    state = status["status"]
    print(f"  상태: {state}")

    if state == "Completed":
        output_uri = status["outputDataConfig"]["s3OutputDataConfig"]["s3Uri"]
        print(f"✅ 비디오 생성 완료: {output_uri}")
        break
    elif state == "Failed":
        print(f"❌ 실패: {status.get('failureMessage', '알 수 없음')}")
        break

    time.sleep(30)