# lambda_function.py
import os
import boto3

agent_rt = boto3.client("bedrock-agent-runtime", region_name="us-west-2")

def lambda_handler(event, context):
    tool_name = context.client_context.custom["bedrockAgentCoreToolName"].split("___")[-1]
    if tool_name == "search_knowledge_base":
        resp = agent_rt.retrieve(
            knowledgeBaseId=os.environ["KB_ID"],
            retrievalQuery={"text": event["query"]},
        )
        chunks = [r["content"]["text"] for r in resp["retrievalResults"]]
        return {"content": [{"type": "text", "text": "\n\n".join(chunks)}]}
    return {"content": [{"type": "text", "text": f"알 수 없는 도구: {tool_name}"}]}