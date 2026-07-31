# Strands Agents 기초 — 도구·멀티턴·관찰성

![AWS](https://img.shields.io/badge/AWS-Bedrock-01A88D)
![Python](https://img.shields.io/badge/Python-3.14-3776AB?logo=python&logoColor=white)
![Strands Agents](https://img.shields.io/badge/Strands_Agents-1.50-4B32C3)
![Streamlit](https://img.shields.io/badge/Streamlit-1.60-FF4B4B?logo=streamlit&logoColor=white)
![Pydantic](https://img.shields.io/badge/Pydantic-2.13-E92063?logo=pydantic&logoColor=white)

강남 식당 컨시어지를 소재로 Strands Agents SDK의 기능을 단계적으로 쌓아
올린 실습입니다. 도구 없는 LLM 호출에서 시작해 커스텀 도구, 멀티턴 세션,
관찰성, Streamlit 챗봇까지 확장합니다.

## 아키텍처

```
BedrockModel (us.anthropic.claude-sonnet-4-6, us-west-2)
   │
   ▼
Agent(system_prompt, tools=[...], callback_handler=None)
   │
   ├── 01_basic_agent.py        도구 없음 — LLM 지식만
   ├── 02_builtin_tools.py      strands_tools 내장 도구
   ├── 03_web_search_agent.py   @tool 커스텀 도구 (DuckDuckGo)
   ├── 04_concierge_agent.py    tools.py의 도구 묶음 연결
   ├── 05_multi_turn.py         대화 히스토리 유지
   ├── 06_observe_agent.py      토큰·지연 등 실행 지표 관찰
   └── 07_chat_app.py           Streamlit 챗봇 UI

tools.py — 여러 스크립트가 공유하는 @tool 도구 정의
restaurants.txt — 파일 기반 도구가 읽는 식당 데이터
```

스크립트마다 `REGION`과 `model_id`를 각자 선언해 중복이 있습니다.
학습용 코드라 파일 하나만 열어도 전체가 읽히는 편이 낫다고 판단해
공통 모듈로 빼지 않았습니다.

## 실행 방법

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python 01_basic_agent.py          # 번호 순서대로 실행
streamlit run 07_chat_app.py      # 챗봇만 별도 실행
```

## 사전 조건

- `us-west-2`에서 Claude Sonnet 4.6 크로스 리전 추론 프로필 접근 권한
- `03_web_search_agent.py`는 DuckDuckGo에 외부 네트워크 요청을 보냅니다

## 설계 결정

이 실습은 Kiro CLI(모델: claude-opus-5)와 함께 진행했습니다. 아래 내용은
AI 에이전트가 실행한 도구 결과를 근거로 정리했으며, 판단은 사람이
검토·승인했습니다.

**`callback_handler=None`을 왜 넣었는지** — Strands 기본 콜백은 토큰을
스트리밍으로 즉시 출력합니다. 그대로 두면 스트리밍 출력과 마지막
`print(response)`가 중복돼 같은 답변이 두 번 보입니다. 콜백을 끄고
최종 결과만 출력하도록 통일했습니다.

**웹검색 도구의 예외 처리** — `03_web_search_agent.py`의 `web_search`는
예외를 잡아 문자열로 반환합니다. 도구가 예외를 그대로 올리면 에이전트가
복구할 기회 없이 중단되지만, 문자열로 돌려주면 LLM이 "검색에 실패했다"는
사실을 읽고 다른 방식을 시도할 수 있습니다. 다만 현재는 로그를 남기지
않아 원인 추적이 어렵다는 한계가 있습니다.

## 이론 정리

- [`notes/tool-decorator.md`](./notes/tool-decorator.md) — `@tool` 데코레이터 동작
- [`notes/model-provider.md`](./notes/model-provider.md) — 모델 프로바이더 선택
- [`notes/structured-output.md`](./notes/structured-output.md) — Pydantic 구조화 출력
- [`notes/challenge-tasks.md`](./notes/challenge-tasks.md) — 추가 과제 메모

과정 수준의 설계 판단 정리는
[`developing-genai-apps/notes/practice/agent-app-design.md`](../../developing-genai-apps/notes/practice/agent-app-design.md)에
있습니다. 이 폴더의 노트는 API 수준, 그쪽은 앱을 만들 때의 판단을 다룹니다.

## 검증 결과

각 스크립트가 무엇을 확인하는지와, 실제로 확인한 것을 구분해서 적습니다.

| 스크립트 | 확인 대상 | 상태 |
|---|---|---|
| `01_basic_agent.py` | 최소 구성 에이전트 호출과 응답 | 확인 |
| `02_builtin_tools.py` | 빌트인 도구 호출, Pydantic 구조화 출력 수신 | 확인 |
| `03_web_search_agent.py` | 커스텀 `@tool` 등록, 도구 예외를 문자열로 반환해 에이전트가 복구 시도 | 확인 |
| `04_concierge_agent.py` | 도구 여러 개를 놓고 모델이 선택 | 확인 |
| `05_multi_turn.py` | 멀티턴에서 이전 턴 참조 | 확인 |
| `06_observe_agent.py` | 토큰 사용량·도구 호출 관찰 | 확인 |
| `07_chat_app.py` | Streamlit UI에서 스트리밍 출력 | 확인 |

**중복 출력 문제**는 실행 중에 드러난 것입니다. Strands 기본 콜백이 토큰을
스트리밍으로 출력하는데 마지막에 `print(response)`가 한 번 더 나가서 같은
답변이 두 번 보였습니다. `callback_handler=None`으로 콜백을 끄고 최종 결과만
출력하도록 통일했습니다. 자세한 내용은 위 "설계 결정" 절에 있습니다.

### 확인하지 못한 것

정직하게 남깁니다.

| 항목 | 이유 |
|---|---|
| 응답 품질의 정량 비교 | LLM 응답은 비결정적이라 같은 프롬프트로도 매번 다릅니다. 이 랩은 "동작하는가"만 확인했고 품질 지표는 측정하지 않았습니다 |
| 모델 프로바이더 교체 실측 | `notes/model-provider.md`의 Anthropic 직접·Ollama 경로는 API 키·로컬 모델이 없어 실행하지 않았습니다. Bedrock 경로만 확인했습니다 |
| 도구 실패 시 로그 | `web_search`가 예외를 문자열로 돌려주지만 로그를 남기지 않아 원인 추적이 안 됩니다. 알려진 한계입니다 |
| 자동화된 테스트 | 이 랩에는 테스트가 없습니다. 사람이 실행해 출력을 보는 방식입니다 |

## 비용 주의사항

상시 과금되는 리소스는 없습니다. Bedrock 모델 호출량만큼만 과금되며,
`06_observe_agent.py`가 출력하는 토큰 수로 호출당 비용을 가늠할 수 있습니다.
