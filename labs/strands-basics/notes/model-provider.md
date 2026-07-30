# 모델 프로바이더 교체

`Agent(model=...)`에 넘기는 프로바이더만 바꾸면 나머지 코드(도구, 프롬프트,
대화 관리)는 그대로 둘 수 있다.

```python
# Bedrock — AWS 자격 증명 사용
from strands.models import BedrockModel
agent = Agent(model=BedrockModel(model_id="us.anthropic.claude-sonnet-4-6"))

# Anthropic 직접 — ANTHROPIC_API_KEY 필요
from strands.models.anthropic import AnthropicModel
agent = Agent(model=AnthropicModel(model_id="claude-sonnet-4-6"))

# Ollama — 로컬 실행, 네트워크·과금 없음
from strands.models.ollama import OllamaModel
agent = Agent(model=OllamaModel(model_id="llama3.1"))
```

Bedrock 모델 ID의 `us.` 접두어는 크로스 리전 인퍼런스 프로필을 뜻한다.
접두어 없는 ID는 온디맨드가 지원되는 리전에서만 호출된다.
