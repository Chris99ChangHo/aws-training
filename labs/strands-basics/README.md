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

## 비용 주의사항

상시 과금되는 리소스는 없습니다. Bedrock 모델 호출량만큼만 과금되며,
`06_observe_agent.py`가 출력하는 토큰 수로 호출당 비용을 가늠할 수 있습니다.
