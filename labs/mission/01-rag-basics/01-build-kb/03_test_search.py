# 03_test_search.py — RetrieveAndGenerate API 검색 테스트
import os
import boto3

KNOWLEDGE_BASE_ID = os.environ.get("KNOWLEDGE_BASE_ID", "<YOUR_KNOWLEDGE_BASE_ID>")
REGION = "us-west-2"

#      추론 프로파일 ID를 modelArn에 그대로 전달합니다
INFERENCE_PROFILE_ID = "us.anthropic.claude-sonnet-4-6"

agent_rt = boto3.client("bedrock-agent-runtime", region_name=REGION)

response = agent_rt.retrieve_and_generate(
    input={"text": "데이트하기 좋은 식당 추천해 주세요. 예산은 1인 5만원이에요."},
    retrieveAndGenerateConfiguration={
        "type": "KNOWLEDGE_BASE",
        "knowledgeBaseConfiguration": {
            "knowledgeBaseId": KNOWLEDGE_BASE_ID,
            "modelArn": INFERENCE_PROFILE_ID,
        },
    },
)

print(f"답변: {response['output']['text']}\n")

print("참조 문서:")
for citation in response.get("citations", []):
    for ref in citation.get("retrievedReferences", []):
        print(f"- {ref['location']['s3Location']['uri']}")