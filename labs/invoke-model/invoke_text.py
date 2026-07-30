# """InvokeModel API로 Claude 모델 직접 호출."""
# import boto3
# import json

# REGION = "us-west-2"

# # --- Bedrock Runtime 클라이언트 초기화 ---
# bedrock_runtime = boto3.client("bedrock-runtime", region_name=REGION)

# # --- Claude 네이티브 요청 body 구성 ---
# # 최신 Claude 모델은 adaptive thinking이 기본이므로 temperature/top_p 없이 호출합니다
# body = json.dumps({
#     "anthropic_version": "bedrock-2023-05-31",
#     "messages": [
#         {"role": "user", "content": "서버리스 아키텍처의 장점 3가지를 설명하세요."}
#     ],
#     "max_tokens": 512
# })

# # --- InvokeModel 호출 ---
# response = bedrock_runtime.invoke_model(
#     modelId="us.anthropic.claude-sonnet-4-6",
#     contentType="application/json",
#     accept="application/json",
#     body=body
# )

# # --- 응답 파싱 ---
# result = json.loads(response["body"].read())
# print(result["content"][0]["text"])
# print(f"\n--- 토큰 사용량 ---")
# print(f"입력: {result['usage']['input_tokens']} 토큰")
# print(f"출력: {result['usage']['output_tokens']} 토큰")

"""InvokeModel API로 Llama 4 모델 직접 호출 — 포맷이 Claude와 완전히 다름."""
import boto3
import json

REGION = "us-west-2"
bedrock_runtime = boto3.client("bedrock-runtime", region_name=REGION)

# --- Llama 4 네이티브 요청 body (prompt 문자열 + 특수 토큰 형식) ---
prompt = """<|begin_of_text|><|start_header_id|>user<|end_header_id|>

서버리스 아키텍처의 장점 3가지를 설명하세요.<|eot_id|><|start_header_id|>assistant<|end_header_id|>
"""

body = json.dumps({
    "prompt": prompt,
    "max_gen_len": 512,
    "temperature": 0.7,
    "top_p": 0.9
})

response = bedrock_runtime.invoke_model(
    modelId="us.meta.llama4-scout-17b-instruct-v1:0",
    contentType="application/json",
    accept="application/json",
    body=body
)

# --- 응답 파싱 (Llama는 generation 문자열로 반환) ---
result = json.loads(response["body"].read())
print(result["generation"])
print(f"\n--- 토큰 사용량 ---")
print(f"입력: {result['prompt_token_count']} 토큰")
print(f"출력: {result['generation_token_count']} 토큰")