"""Nova Canvas로 이미지 생성."""
import boto3
import json
import base64

REGION = "us-west-2"
bedrock_runtime = boto3.client("bedrock-runtime", region_name=REGION)

body = json.dumps({
    "taskType": "TEXT_IMAGE",
    "textToImageParams": {
        "text": "서울 남산타워가 보이는 야경, 사이버펑크 스타일, 고해상도"
    },
    "imageGenerationConfig": {
        "numberOfImages": 1,
        "height": 1024,
        "width": 1024,
        "cfgScale": 8.0,
        "seed": 42
    }
})

print("이미지 생성 중...")
response = bedrock_runtime.invoke_model(
    modelId="amazon.nova-canvas-v1:0",
    body=body
)

# --- base64 디코딩 → 파일 저장 ---
result = json.loads(response["body"].read())
image_data = base64.b64decode(result["images"][0])

with open("generated_image.png", "wb") as f:
    f.write(image_data)

print("✅ generated_image.png 저장 완료")
print(f"   크기: {len(image_data) / 1024:.0f} KB")