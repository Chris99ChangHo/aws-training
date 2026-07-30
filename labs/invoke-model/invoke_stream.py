# """InvokeModelWithResponseStream으로 실시간 스트리밍."""
# import boto3
# import json

# REGION = "us-west-2"
# bedrock_runtime = boto3.client("bedrock-runtime", region_name=REGION)

# body = json.dumps({
#     "anthropic_version": "bedrock-2023-05-31",
#     "messages": [
#         {"role": "user", "content": "Python의 장점 5가지를 상세히 설명하세요."}
#     ],
#     "max_tokens": 1024
# })

# # --- 스트리밍 호출 ---
# response = bedrock_runtime.invoke_model_with_response_stream(
#     modelId="us.anthropic.claude-sonnet-4-6",
#     contentType="application/json",
#     accept="application/json",
#     body=body
# )

# # --- EventStream에서 청크 추출 ---
# for event in response["body"]:
#     chunk = json.loads(event["chunk"]["bytes"])
#     if chunk["type"] == "content_block_delta":
#         print(chunk["delta"]["text"], end="", flush=True)

# print()  # 마지막 줄바꿈

"""스트리밍 이벤트 구조 확인."""
import boto3
import json

REGION = "us-west-2"
bedrock_runtime = boto3.client("bedrock-runtime", region_name=REGION)

body = json.dumps({
    "anthropic_version": "bedrock-2023-05-31",
    "messages": [{"role": "user", "content": "안녕하세요"}],
    "max_tokens": 100
})

response = bedrock_runtime.invoke_model_with_response_stream(
    modelId="us.anthropic.claude-sonnet-4-6",
    contentType="application/json",
    accept="application/json",
    body=body
)

# --- 모든 이벤트 타입 출력 ---
for event in response["body"]:
    chunk = json.loads(event["chunk"]["bytes"])
    print(f"[{chunk['type']}] {json.dumps(chunk, ensure_ascii=False)[:100]}")