"""Gateway 생성 + Lambda 타깃 추가 (콘솔 대안)."""
from __future__ import annotations

import boto3

client = boto3.client("bedrock-agentcore-control", region_name="us-west-2")

GATEWAY_ROLE_ARN = "<YOUR_GATEWAY_ROLE_ARN>"  # 콘솔 Create default role이 만든 역할
LAMBDA_ARN = "<YOUR_LAMBDA_ARN>"              # dining-kb-search 함수의 ARN

# Gateway 생성
gw = client.create_gateway(
    name="dining-gateway",
    protocolType="MCP",
    authorizerType="AWS_IAM",
    roleArn=GATEWAY_ROLE_ARN,
)
gateway_id = gw["gatewayId"]
print(f"Gateway ID: {gateway_id}, Status: {gw['status']}")

# Lambda 타깃 추가
tool_schema = [{
    "name": "search_knowledge_base",
    "description": "Knowledge Base에서 식당 정보를 검색합니다",
    "inputSchema": {
        "type": "object",
        "properties": {"query": {"type": "string", "description": "검색 질의"}},
        "required": ["query"],
    },
}]

client.create_gateway_target(
    gatewayIdentifier=gateway_id,
    name="dining-kb-search",
    targetConfiguration={
        "mcp": {
            "lambda": {
                "lambdaArn": LAMBDA_ARN,
                "toolSchema": {"inlinePayload": tool_schema},
            }
        }
    },
    credentialProviderConfigurations=[
        {"credentialProviderType": "GATEWAY_IAM_ROLE"}
    ],
)
print("Target 'dining-kb-search' added.")
