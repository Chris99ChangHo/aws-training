# Developing Generative AI Applications on AWS

Strands Agents SDK로 에이전트 애플리케이션을 만드는 과정입니다. 도구 정의,
MCP 연결, 세션 영속화, Streamlit UI까지 하나의 앱으로 묶습니다.

## 실습

| 실습 | 폴더 | 내용 |
|---|---|---|
| 강남 다이닝 컨시어지 | [`gangnam-dining-concierge/`](./gangnam-dining-concierge) | Strands Agents 도구·MCP·세션 영속화·Streamlit 챗봇 UI |

기능 단위로 쪼갠 선행 랩은 [`labs/`](../labs)에 있습니다.

| 랩 | 내용 |
|---|---|
| [`labs/strands-basics/`](../labs/strands-basics) | 빌트인·커스텀 도구, 멀티턴, 콜백 관찰 |
| [`labs/strands-mcp-client/`](../labs/strands-mcp-client) | stdio·Streamable HTTP 트랜스포트, MCP 도구와 로컬 `@tool` 혼합 |

## 이론 정리

| 노트 | 내용 |
|---|---|
| [`notes/agent-app-design.md`](./notes/agent-app-design.md) | 에이전트 앱에서 실제로 걸리는 것들 — 도구 조합, 서브프로세스 환경 의존, 세션 영속화의 함정, 스트리밍 조각, 맥락 참조, 재현성 |

API 시그니처는 노트에 적지 않습니다. Strands는 릴리스가 잦아 정적 문서가 빠르게
낡으므로 `strands-agents` MCP 서버(`search_docs` / `fetch_doc`)나
[llms.txt](https://strandsagents.com/llms.txt)로 조회합니다. 이 판단의 근거는
`.kiro/skills/strands-agents/SKILL.md`에 있습니다.

`@tool`·Structured Output·모델 프로바이더 같은 API 수준 정리는 각 랩의
`notes/`에 있고, 위 과정 노트는 그것들과 중복하지 않고 **설계 판단**만 다룹니다.

## 이 과정에서 얻은 것

`[해석]` 에이전트 앱에서 막히는 지점은 대부분 모델이 아니라 **경계**였습니다.

| 걸린 곳 | 실제 원인 |
|---|---|
| 리뷰 도구가 "정보 없음"만 반환 | 두 데이터셋의 식당 목록이 1곳만 겹침 — 도구는 정상 |
| MCP 서버가 안 뜸 | `command="python"`과 cwd 상대 경로 — 환경 가정 |
| 이전 대화를 못 찾음 | 저장은 됐지만 UUID를 기억할 방법이 없음 |
| 도구 인자가 깨져 보임 | 스트리밍 조각을 그대로 렌더링 |
| "이전 추천 바꿔줘"가 무시됨 | 대화 관리 윈도우 밖 — 프롬프트 문제가 아님 |

`[해석]` 공통점은 **모델을 고쳐서 해결되는 것이 하나도 없다**는 점입니다.
프롬프트를 다듬기 전에 데이터·경로·상태·컨텍스트를 먼저 봐야 하는 부류이고,
그 구분을 하는 것이 이 과정에서 가장 실무에 남는 부분이었습니다.
