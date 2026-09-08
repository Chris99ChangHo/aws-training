# app.py — dining-web Lambda 핸들러
#
# event["routeKey"](HTTP API payload 2.0)로 GET /·POST /ask를 분기합니다.
import json
import os

import boto3

REGION = "us-west-2"

_CHAT_PAGE_HTML = """\
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8" />
<title>강남 다이닝 컨시어지 (임시 확인용)</title>
<style>
  body { font-family: sans-serif; max-width: 640px; margin: 40px auto; padding: 0 16px; }
  h1 { font-size: 1.4rem; }
  #answer { white-space: pre-wrap; border: 1px solid #ddd; border-radius: 8px;
             padding: 16px; margin-top: 16px; min-height: 60px; background: #fafafa; }
  form { display: flex; gap: 8px; margin-top: 16px; }
  input[type="text"] { flex: 1; padding: 8px; font-size: 1rem; }
  button { padding: 8px 16px; font-size: 1rem; cursor: pointer; }
</style>
</head>
<body>
  <h1>🍽️ 강남 다이닝 컨시어지 (임시 확인용)</h1>
  <form id="chat-form">
    <input type="text" id="prompt" placeholder="질문을 입력하세요" autocomplete="off" />
    <button type="submit">전송</button>
  </form>
  <div id="answer">응답이 여기에 표시됩니다.</div>

<script>
  const form = document.getElementById("chat-form");
  const promptInput = document.getElementById("prompt");
  const answerDiv = document.getElementById("answer");

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const prompt = promptInput.value.trim();
    if (!prompt) return;
    answerDiv.textContent = "응답을 기다리는 중...";
    try {
      const res = await fetch("/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: prompt }),
      });
      const data = await res.json();
      answerDiv.textContent = data.answer || JSON.stringify(data);
    } catch (err) {
      answerDiv.textContent = "오류: " + err;
    }
  });
</script>
</body>
</html>
"""


def _handle_get_root():
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "text/html"},
        "body": _CHAT_PAGE_HTML,
    }


def _extract_answer_text(raw_body: bytes) -> str:
    """invoke_agent_runtime 응답 본문에서 텍스트를 추출합니다.

    04번 미션 계열 Runtime(동기 엔트리포인트)은 순수 JSON
    {"result": "...", "tool_calls": [...]}을 반환하고, 06번 계열
    Runtime(스트리밍 엔트리포인트)은 SSE 프레이밍(data: 줄)을 반환한다.
    두 형식을 모두 처리해야 이 API가 어느 Runtime을 가리키든 동작한다.
    """
    text = raw_body.decode("utf-8")

    # 1) 순수 JSON 응답(동기 엔트리포인트)
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict) and "result" in parsed:
            return parsed["result"]
    except json.JSONDecodeError:
        pass

    # 2) SSE 프레이밍(스트리밍 엔트리포인트)
    answer_parts = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue
        data_str = line[len("data:"):].strip()
        try:
            event = json.loads(data_str)
        except json.JSONDecodeError:
            continue
        delta = event.get("event", {}).get("contentBlockDelta", {}).get("delta", {})
        if "text" in delta:
            answer_parts.append(delta["text"])

    if answer_parts:
        return "".join(answer_parts)
    return text


def _handle_post_ask(event):
    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "요청 본문이 올바른 JSON이 아닙니다."}),
        }

    prompt = body.get("prompt", "")
    if not prompt:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "prompt가 필요합니다."}),
        }

    client = boto3.client("bedrock-agentcore", region_name=REGION)
    response = client.invoke_agent_runtime(
        agentRuntimeArn=os.environ["AGENT_RUNTIME_ARN"],
        qualifier="DEFAULT",
        payload=json.dumps({"prompt": prompt}),
    )
    raw_body = response["response"].read()
    answer = _extract_answer_text(raw_body)

    return {
        "statusCode": 200,
        "body": json.dumps({"answer": answer}),
    }


def lambda_handler(event, context):
    route_key = event.get("routeKey", "")

    if route_key == "GET /":
        return _handle_get_root()
    if route_key == "POST /ask":
        return _handle_post_ask(event)

    return {
        "statusCode": 404,
        "body": json.dumps({"error": f"알 수 없는 라우트: {route_key}"}),
    }
