# Day 2 — 에이전트 상태 관리, 프롬프트 설계, Strands SDK

> 교육일: 2026-07-29
> 문서 확인일: 2026-07-31
> 범위: 에이전틱 루프, 세션·상태·장기 기억, 프롬프트 4블록, Strands Agents
> SDK, MCP 아키텍처와 2026-07-28 개정, 멀티에이전트 패턴

표기 규칙: `[문서]` 공식 문서 인용(링크 있음) · `[해석]` 문서를 놓고 내린
판단. 수업 필기 원본은 별도 문서(Google Docs)로 관리한다.
API 시그니처는 이 노트에 적지 않는다 — 이유는
[`agent-app-design.md`](../practice/agent-app-design.md) 상단, `strands-agents` 스킬 참고.

## 학습 목표

- 에이전틱 루프(추론 → 호출 → 관찰)의 구조를 설명한다.
- 세션(`messages[]`)과 에이전트 상태(`agent.state`), 호출 컨텍스트의 수명과
  방향 차이를 구분한다.
- 시스템 프롬프트 4블록 구조와 도구 description의 역할 분담을 안다.
- HITL 3패턴(승인 게이트·에스컬레이션·감사 로그)과 설계 원칙을 안다.
- Strands Agents SDK의 최소 구성(Model + Tools + System Prompt)을 안다.
- 에이전트 개발의 3세대 진화(직접 구현 → 프레임워크 → Model-Driven)를
  구분한다.
- MCP·A2A·AG-UI가 각각 어떤 방향의 연결을 표준화하는지 구분한다.
- MCP 아키텍처(stdio/HTTP)와 2026-07-28 개정의 방향을 안다.
- 멀티에이전트 패턴을 실제 SDK 분류(Graph/Swarm/Workflow) 기준으로 정리한다.

## 1. 에이전틱 루프와 인메모리 상태의 문제

`[해석]` 에이전트의 기본 동작은 **추론(Reason) → 호출(Act) → 관찰(Observe)**을
목표 달성까지 반복하는 것이다. 이 루프에서 핵심 전제는 "모델은 아무것도
기억하지 않는다"는 것 — 매 호출마다 지금까지의 대화 전체(`messages[]`)가
다시 전송된다.

이 전제에서 네 가지 문제가 나온다.

| 문제 | 원인 |
|---|---|
| 기억 상실 | 프로세스 종료 시 `messages[]` 전체 유실 (서버 재시작, 배포, Lambda 콜드스타트) |
| 토큰 폭발 | 대화가 길어질수록 매 호출마다 수만 토큰 재전송 — 비용·지연 증가 |
| 윈도우 초과 | 컨텍스트 윈도우를 넘으면 API 에러로 에이전트가 멈춤 |
| 멀티유저 혼선 | `session_id` 없이 여러 사용자의 `messages[]`가 섞임 |

`[해석]` 네 문제 모두 **상태를 프로세스 메모리에만 둔 것**이 원인이다. 아래
상태 관리 구성요소가 각각의 해법이다.

## 2. 세션, 상태, 호출 컨텍스트 — 수명과 방향이 다른 세 가지

`[문서]` Strands에서 "세션"은 에이전트·멀티에이전트 시스템이 동작하는 데
필요한 상태 정보 전체를 뜻한다.
([session-management](https://strandsagents.com/docs/user-guide/concepts/agents/session-management/index.md))

`[해석]` 실제로 이 상태는 수명과 노출 범위가 다른 세 계층으로 나뉜다.

| 계층 | 수명 | 모델에 보임? | 용도 |
|---|---|---|---|
| `messages[]` (세션) | 세션 전체 | 보임 (매번 전체 전송) | 대화 맥락 유지 |
| `agent.state` (에이전트 상태) | 세션 전체 | 안 보임 | 도구·훅이 읽고 쓰는 내부 저장소 (인증 토큰, 호출 카운터) |
| 호출 컨텍스트(invocation state) | 1턴만 | 안 보임 | 호출자가 외부에서 주입하는 파라미터 (API 키, user_id, 역할) |

`[해석]` `agent.state`와 호출 컨텍스트의 차이는 **누가, 언제 채우는가**다 —
`agent.state`는 세션 동안 누적되며 세션 스토어와 함께 영속화되지만, 호출
컨텍스트는 매 호출마다 호출자가 새로 주입해야 하고 저장되지 않는다. 민감
정보(API 키, 세션 비밀)는 모델 컨텍스트에 노출되지 않도록 이 둘 중 하나로
분리해서 관리한다.

`[문서]` 세션의 영속화는 `SessionManager`가 맡는다. 파일시스템(`FileSessionManager`),
S3(`S3SessionManager`), 저장소 인터페이스(`RepositorySessionManager`) 등 백엔드를
교체할 수 있다.
([session_manager API](https://strandsagents.com/docs/api/python/strands.session.session_manager/index.md))

`[해석]` `SessionManager`가 대화를 **저장·복원**하는 계층이라면,
`ConversationManager`는 매 호출마다 모델에 보낼 `messages[]`의 **길이**를
정책으로 관리하는 별도 계층이다. 원본 필기는 세 가지를 든다.

| 종류 | 동작 |
|---|---|
| SlidingWindow | 최근 N개 메시지만 유지(기본값) |
| Summarizing | 오래된 구간을 요약으로 압축 |
| NullConversationManager | 이력을 건드리지 않음 |

`[해석]` 이 구분은 1절의 "토큰 폭발·윈도우 초과" 문제와 직접 연결된다 —
대화가 길어질 때 무엇을 잘라내고 무엇을 남길지가 `ConversationManager`의
정책이다. `SlidingWindow`를 너무 좁게 잡으면 "이전 추천을 참조해 달라"는
요청이 무시되는 문제(컨텍스트 밖으로 밀려남)가 생길 수 있다 — 이 문제의
실제 사례는 [`agent-app-design.md`](../practice/agent-app-design.md) 5절에 있다.

## 3. 세션 너머 — 장기 기억

`[해석]` 세션이 끝나도 남아야 하는 정보는 별도 계층인 **장기 기억**으로
옮긴다. 동작 흐름은 추출 → 저장 → 회수 → 주입 4단계다 — 대화에서 남길
것을 추출해 저장하고, 다음 세션이 시작될 때 회수해서 컨텍스트에 다시
주입한다.

`[해석]` 무엇을 남기는지는 크게 세 종류로 나뉜다.

- **사실(Semantic)**: 잘 변하지 않는 정보 (예: "회사는 강남역 근처")
- **선호(Preference)**: 예: "창가 자리 선호, 매운 음식 못 먹음"
- **에피소드(Episodic)**: 과거 사건의 요약 (예: "7/20 예약 — 만족")

전부 저장하는 것은 오히려 잡음이 된다. 다음 세션에 실제로 쓸 것만 추출해서
남기는 것이 핵심이다.

## 4. 시스템 프롬프트 4블록 구조

`[해석]` 에이전트 프롬프트는 "좋은 답변"이 아니라 "올바른 행동"을 설계하는
것이 목적이다. 4블록으로 나누면 오동작을 진단·수정하기 쉽다.

| 블록 | 내용 | 비고 |
|---|---|---|
| 1. 역할(Role) | 정체성 + 행동 방침 | "도구로 데이터 기반 답변" 같은 원칙도 포함 |
| 2. 행동 규칙(Rules) | 도구 사용 순서, 추측 금지, 호출 횟수 제한 | 오동작 시 가장 먼저 손볼 블록 |
| 3. 출력 형식(Format) | 단위·자릿수·서술 순서 | 응답 일관성의 전역 규칙 |
| 4. 제한(Constraints) | 하면 안 되는 일 (실행 금지, 다른 계정 접근 금지) | 권한의 경계 |

`[해석]` 시스템 프롬프트와 도구 description은 역할이 다르다 — **행동 규칙·
출력 형식·제한처럼 에이전트 전체에 적용되는 전역 규칙은 시스템 프롬프트**에,
**"언제 이 도구를 쓰나"처럼 도구 선택의 근거가 되는 정보는 도구
description**에 둔다. 파라미터의 의미·형식은 description과 입력 스키마가
함께 담당한다.

## 4-1. Human-in-the-Loop(HITL) 3패턴

`[해석]` Day 1에서 다룬 자율성 3단계(AI Assistant → AI Agent → Agentic AI)
중 2단계부터는 고위험 동작 앞에 승인 게이트가 필요하다고 짚었다. 원본
필기는 이를 위험도에 따른 기본 방침과 세 가지 구체적 패턴으로 더 좁혀
정리한다.

기본 방침: **읽기(조회) 작업은 자동 실행, 쓰기(변경) 작업은 승인 필요,
고위험 작업(삭제·결제 등)은 이중 확인**을 거친다.

- **승인 게이트**: 실행 전에 사람의 승인을 받는 패턴. 위 방침의 "쓰기는
  승인" 단계에 대응한다.
- **에스컬레이션**: 에이전트가 처리 범위를 벗어난 상황(모호함, 권한 부족,
  예외 상황)을 만나면 자동 실행을 멈추고 사람에게 넘기는 패턴.
- **감사 로그**: 자동 실행된 작업이라도 무엇을 언제 왜 했는지 기록을
  남겨 사후에 추적할 수 있게 하는 패턴.

`[해석]` 세 패턴을 관통하는 설계 원칙은 **최소 권한**(필요한 만큼만 자동
실행 허용), **점진적 자율**(신뢰가 쌓인 작업부터 승인 단계를 줄여나감),
**실패 안전**(판단이 애매하면 실행하지 않고 사람에게 넘기는 쪽으로
기본값을 둠)이다.

## 5. Strands Agents SDK 개요

`[해석]` 에이전트 개발 방식은 판단의 주체가 누구인가를 기준으로 세 세대로
나눌 수 있다.

| 세대 | 판단 주체 | 방식 | 대표 |
|---|---|---|---|
| 1세대 · 직접 구현 | 개발자 | LLM API를 직접 연결, 루프·프롬프트·응답 파싱을 전부 직접 코딩 | OpenAI·Anthropic API 직접 호출 |
| 2세대 · 에이전트 프레임워크 | 그래프 구조 | 그래프 노드·상태 머신·역할 정의로 흐름을 설계 | LangChain·LangGraph·CrewAI |
| 3세대 · Model-Driven | 모델 | LLM이 도구 선택과 실행 순서를 직접 판단, 개발자는 도구만 등록 | Strands Agents SDK |

`[해석]` 세대가 올라갈수록 개발자가 흐름 제어 코드를 직접 짜는 비중이
줄고, 모델의 판단에 위임하는 비중이 커진다. Strands는 3세대(Model-Driven)
접근에 속한다.

`[문서]` Strands 공식 문서는 에이전트 프레임워크의 흐름을 "모델이 도구
선택과 순서를 직접 판단하는" model-driven 접근으로 설명한다. 최소 구성은
다음 세 요소다.

```
Agent = Model + Tools + System Prompt
```

- **Model**: 유일한 필수 요소. 도구 선택과 완료 여부를 판단하는 추론 엔진.
- **Tools**: 선택 요소. 없으면 일반 채팅봇과 같다.
- **System Prompt**: 선택 요소. 없으면 범용 응답을 한다.

`[해석]` `@tool` 데코레이터를 함수에 붙이면 Python 함수의 타입 힌트와
docstring이 자동으로 도구 스키마(name·description·inputSchema)로 변환된다.
이는 스키마 3요소를 손으로 작성하지 않기 위한 것이다.

`[문서]` 빌트인 도구는 두 공급원이 있다 — SDK 코어에 동봉된 것과
`strands-agents-tools` 패키지의 카테고리별 확장. 외부 MCP 서버의 도구는
`MCPClient`로 동적으로 로드해 등록할 수 있다.
([mcp_agent_tool](https://strandsagents.com/docs/api/python/strands.tools.mcp.mcp_agent_tool/index.md))

`[해석]` **모델 교체가 코드 2줄로 끝나는 것**이 이 SDK의 핵심 설계다 —
`tools`와 `system_prompt`는 그대로 두고 모델 프로바이더 객체만 바꾸면 된다.
정확한 프로바이더 목록·개수는 릴리스마다 바뀌므로 이 노트에 숫자를 못박지
않는다.

### Pydantic과 Structured Output

`[해석]` Pydantic은 Python에서 타입 힌트로 데이터 검증과 JSON Schema 생성을
동시에 하는 표준 라이브러리다. 클래스 선언 하나가 곧 스키마 역할을 한다.
에이전트 개발에서는 **Structured Output**(에이전트 응답을 자유 텍스트가
아니라 정해진 스키마로 강제하는 기능)의 입력·출력 스키마로 쓰인다. 이는
Strands에 한정된 개념이 아니라 OpenAI SDK, LangChain 등 LLM 생태계 전반에서
같은 방식으로 쓰인다.

## 6. MCP 아키텍처와 2026-07-28 개정

`[문서]` MCP는 Host 안의 Client가 Server와 1:1로 연결되는 3계층 구조다.
연결 경로는 stdio(로컬, 자식 프로세스)와 Streamable HTTP(원격, URL 기반)
두 가지다.

`[문서]` 2026-07-28에 실제로 MCP 스펙의 대규모 개정이 있었다. 핵심 방향은
**프로토콜 코어를 stateless로 만드는 것**이다.
([공식 changelog](https://modelcontextprotocol.io/specification/2026-07-28/changelog))

- 프로토콜 수준의 세션과 `Mcp-Session-Id` 헤더, `initialize` 핸드셰이크가
  제거됐다 — 요청마다 자기서술적 메타데이터(`_meta`)를 담아 보낸다.
- 서버가 클라이언트에 역방향 요청을 보내던 방식(roots·sampling 등)은
  MRTR(Multi Round-Trip Requests) — `input_required` 반환 후
  `inputResponses`로 재시도하는 방식으로 바뀌었다.
- 장기 작업은 공식 확장 `io.modelcontextprotocol/tasks`로 표준화됐다.
- 인증은 동적 클라이언트 등록(DCR)이 CIMD로 전환 중이다.
- **Roots·Sampling·Logging과 구 HTTP+SSE 전송은 deprecated 상태**이며,
  최소 12개월의 유예 기간을 둔다. 기존 서버는 즉시 깨지지 않는다.

`[해석]` 필기의 "stateless 코어가 정식 릴리스됐다"는 진술은 정확하다 — 다만
이는 아직 매우 최근(교육 시점 하루 전)에 나온 스펙이므로, 실제 SDK·서버
생태계가 이 방향으로 얼마나 빠르게 전환할지는 계속 확인이 필요한 영역이다.

## 6-1. A2A와 AG-UI — MCP와 함께 보는 세 방향 표준

`[해석]` 원본 필기는 에이전트 생태계의 통합 문제를 "USB-C for AI"라는
표현으로 요약한다 — 도구·에이전트·화면이라는 세 방향의 연결마다 커스텀
통합이 필요했던 N×M 조합 폭발을, 방향마다 표준 하나로 통일하려는
움직임이다. **MCP(도구 연결)·A2A(에이전트 간 연결)·AG-UI(화면 연결)**는
경쟁 관계가 아니라 서로 다른 방향을 담당하는 상호 보완 관계다.

**A2A(Agent2Agent)**는 독립적으로 배포된 에이전트 사이의 태스크 위임을
표준화한 프로토콜이다. `[문서]` 에이전트는 `Agent Card`로 자신의 능력을
알리고, 태스크는 상태를 가지고 진행된다 — 예를 들어 `submitted`(제출) →
`working`(처리 중)을 거쳐 `completed`(완료)·`failed`(실패)·`canceled`
(취소)·`rejected`(거부) 같은 종료 상태나 `input-required`(입력 필요)·
`auth-required`(인증 필요) 같은 중단 상태로 진행된다.
([A2A: Life of a Task](https://a2a-protocol.org/latest/topics/life-of-a-task/))
Google이 발표한 뒤 Linux Foundation에 기증됐다.

`[해석]` 원본 필기는 "Task 상태 6종"이라 적었으나, 공식 문서는 상태를
"진행(working) → 중단 상태(input-required, auth-required) 또는 종료
상태(completed, canceled, rejected, failed)"로 설명해 최소 6~7개 이상의
개별 상태명이 나온다. 정확히 "6종"으로 고정해 부르는 표는 공식 문서에서
찾지 못했으므로, 숫자를 못박지 않고 상태명 목록으로 정리해 둔다.

**AG-UI(Agent-User Interaction)**는 에이전트와 프론트엔드 사이의 실시간
이벤트 스트리밍을 표준화한 프로토콜이다. `[문서]` Server-Sent Events(SSE)
기반의 타입이 있는(typed) 이벤트로 메시지·도구 호출·상태 변경을 프론트엔드에
스트리밍한다. CopilotKit이 개발했고, Strands·LangGraph 같은 특정
프레임워크에 종속되지 않는다.
([CopilotKit AG-UI 문서](https://docs.showcase.copilotkit.ai/strands/ag-ui))

`[해석]` 선택 기준은 이렇게 정리된다 — **도구를 연결한다면 MCP**가 기본
출발점이고, **독립 배포된 에이전트 간 위임이 필요하면 A2A**, **에이전트를
사용자 화면에 직접 노출하려면 AG-UI**를 쓴다.

## 7. 멀티에이전트 패턴 — 강의 분류 vs Strands 공식 분류

`[해석]` 여기서 강의 필기와 Strands 공식 문서 사이에 **분류 체계 차이**가
있어 명확히 구분해 둔다.

`[문서]` Strands 공식 문서가 제시하는 멀티에이전트 패턴은 **세 가지**다.
([Multi-Agent Systems](https://strandsagents.com/docs/user-guide/concepts/multi-agent/multi-agent-patterns/index.md))

| 패턴 | 실행 경로 결정 방식 |
|---|---|
| Graph | 노드 간 정의된 그래프 구조로 결정 |
| Swarm | 에이전트가 스스로 다음 에이전트에게 핸드오프 |
| Workflow | 태스크 의존성 그래프로 순서 결정 |

`[해석]` 강의 필기의 6패턴 분류(Supervisor·Hierarchical·Pipeline·Router·
Swarm·Debate)는 Strands SDK의 1차 분류가 아니라, **개념적으로 흔히 쓰이는
멀티에이전트 아키텍처 패턴**을 정리한 것으로 보인다 — 예를 들어 Supervisor·
Hierarchical은 Strands의 "Agents-as-Tools" 구현 방식으로, Pipeline은
Workflow 패턴의 한 사례로 대응시킬 수 있다. 다만 이 대응 관계는 강의
필기에만 나온 설명이라 공식 문서로 1:1 검증되지는 않는다. 실제 구현 시에는
Graph·Swarm·Workflow 중 무엇을 쓸지 먼저 판단하고, 강의의 6패턴은 "그중
어떤 성격의 문제인가"를 설명하는 어휘로 참고하는 편이 안전하다.

`[해석]` 어느 분류를 쓰든 실무 판단 기준은 같다 — **실행 경로가 미리
정해지는가, 아니면 에이전트가 스스로 결정하는가**. 이건 1절의 체인 vs
에이전트 구분이 멀티에이전트 수준으로 확장된 것이다.

## 핵심 요약

1. 에이전틱 루프는 추론 → 호출 → 관찰의 반복. 모델은 매번 `messages[]`
   전체를 다시 받는다.
2. `messages[]`(모델에 보임) / `agent.state`(세션 내 안 보이는 저장소) /
   호출 컨텍스트(1턴, 외부 주입)는 수명과 방향이 각각 다르다.
3. 장기 기억은 추출 → 저장 → 회수 → 주입. 사실·선호·에피소드 중 남길 것만.
4. 시스템 프롬프트 4블록(역할/규칙/형식/제한) — 행동 규칙은 시스템 프롬프트,
   도구 선택 근거는 description에.
5. HITL은 읽기=자동/쓰기=승인/고위험=이중 확인이 기본 방침이고, 승인
   게이트·에스컬레이션·감사 로그 3패턴으로 구현한다.
6. Strands 최소 구성은 Model(필수) + Tools + System Prompt(둘 다 선택) —
   에이전트 개발 3세대(직접 구현 → 프레임워크 → Model-Driven) 중 3세대에
   해당한다.
7. MCP(도구)·A2A(에이전트 간)·AG-UI(화면)는 방향이 다른 상호 보완 표준이다.
8. MCP 2026-07-28 개정은 stateless 코어 전환이 핵심 — 구 HTTP+SSE는
   12개월 유예 후 제거.
9. 멀티에이전트는 Strands 공식 3패턴(Graph/Swarm/Workflow)이 기준이고,
   강의의 6패턴은 개념 분류로 참고한다.

## 확인하지 못한 것

- 강의의 6패턴(Supervisor·Hierarchical·Pipeline·Router·Swarm·Debate)과
  Strands 공식 3패턴(Graph·Swarm·Workflow)의 대응 관계는 개념적 추정이며,
  공식 문서에서 1:1로 명시한 것을 찾지 못했다.
- MCP 2026-07-28 개정이 Strands SDK에 실제로 언제 반영되는지는 확인하지
  않았다.
- A2A의 Task 상태를 "6종"으로 명시한 근거는 공식 문서에서 찾지 못했다 —
  상태명 목록(submitted/working/input-required/auth-required/completed/
  failed/canceled/rejected)은 확인했으나 이를 "6종"으로 묶는 공식 집계는
  확인하지 못했다.
- HITL 3패턴, ConversationManager 3종, 에이전트 3세대 진화는 강의 필기의
  분류를 그대로 옮긴 것이며, Strands SDK나 별도 학술 자료로 이 분류
  자체를 표준으로 확인하지는 않았다.

## 공식 자료

- [Strands session-management](https://strandsagents.com/docs/user-guide/concepts/agents/session-management/index.md)
- [Strands Multi-Agent Systems](https://strandsagents.com/docs/user-guide/concepts/multi-agent/multi-agent-patterns/index.md)
- [MCP 2026-07-28 changelog](https://modelcontextprotocol.io/specification/2026-07-28/changelog)
- [MCP 2026-07-28 release 공지](https://blog.modelcontextprotocol.io/posts/2026-07-28/)
- [A2A Protocol — Life of a Task](https://a2a-protocol.org/latest/topics/life-of-a-task/)
- [AG-UI 프로토콜 (CopilotKit)](https://docs.showcase.copilotkit.ai/strands/ag-ui)
- API 시그니처는 `strands-agents` MCP 서버(`search_docs`/`fetch_doc`) 또는
  [llms.txt](https://strandsagents.com/llms.txt)로 조회 — 릴리스가 잦아
  정적 문서에 적으면 빠르게 낡는다.
