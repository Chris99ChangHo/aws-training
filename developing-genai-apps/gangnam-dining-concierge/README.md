# 강남 다이닝 컨시어지

![AWS](https://img.shields.io/badge/AWS-Bedrock-orange?logoColor=white)
![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python&logoColor=white)
![Strands Agents](https://img.shields.io/badge/Strands_Agents-1.48-4B32C3)
![Streamlit](https://img.shields.io/badge/Streamlit-1.51-FF4B4B?logo=streamlit&logoColor=white)
![FastMCP](https://img.shields.io/badge/FastMCP-3.4-6E56CF)

Strands Agents SDK로 강남 다이닝 컨시어지를 4단계 미션으로 발전시키는
실습. 도구 에이전트 → 대화 관리·세션 영속화 → Streamlit 챗봇 UI →
리뷰 MCP 서버까지를 이 폴더 하나에 통합했다.

| 미션 | 주제 | 산출물 |
|---|---|---|
| 1 | 도구 에이전트와 MCP | `tools.py`(`@tool` 식당 검색·메뉴), `mcp_server.py`(예약 조회 MCP 서버) |
| 2 | 대화 관리와 세션 | `agent.py`의 `FileSessionManager` 기반 히스토리 저장·복원 |
| 3 | Streamlit 다이닝 컨시어지 | `app.py`(도구+대화+MCP 통합 챗봇 UI) |
| 4 | 리뷰 MCP 서버 구축 | `review_server.py`(`restaurant_reviews` 도구), `review_agent.py`(에이전트 연결), `inspect_reviews.py`(도구 스키마 점검) |

미션 1~3은 `app.py` 하나로 통합되어 함께 동작하고, 미션 4의 리뷰 MCP
서버는 **독립 파이프라인으로 분리**되어 있다(통합 앱에는 아직 연결하지
않았다 — 아래 "리뷰 MCP 서버를 통합 앱에 넣지 않은 이유" 참고).

## 아키텍처

```
사용자 ──chat_input──▶ app.py (Streamlit)
                          │
                          ├─ agent.build_agent(session_id)
                          │     ├─ tools.py
                          │     │     ├─ search_restaurants (@tool)
                          │     │     └─ get_menu (@tool)
                          │     ├─ mcp_server.py (FastMCP, stdio)
                          │     │     └─ check_availability
                          │     └─ FileSessionManager (sessions/*.json)
                          │
                          ├─ agent.stream_async() 이벤트 순회
                          │     ├─ current_tool_use → 사이드바 도구 호출 로그
                          │     └─ data(텍스트 delta) → 채팅 스트리밍 표시
                          │
                          ├─ agent.list_sessions() → 사이드바 "이전 대화" 목록
                          │     └─ 클릭 시 그 session_id로 전환
                          │
                          └─ 응답 텍스트에서 식당명 매칭 → 카드 렌더링

별도 파이프라인 (미션 4, 통합 앱 미연결):

review_agent.py ──MCPClient(stdio)──▶ review_server.py (FastMCP)
                                          └─ restaurant_reviews
inspect_reviews.py ──ClientSession──▶ list_tools()로 도구 스키마 점검
```

- **모델**: Amazon Bedrock Claude Sonnet 4.6 (`us.anthropic.claude-sonnet-4-6`,
  us-west-2 크로스 리전 인퍼런스 프로필)
- **도구**: `search_restaurants`(지역·음식 종류로 검색), `get_menu`(메뉴·가격 조회)
- **MCP**: 로컬 stdio 서버 2개 — `mcp_server.py`가 `check_availability`(예약
  가능 여부·남은 좌석), `review_server.py`가 `restaurant_reviews`(평점·리뷰)를 노출
- **세션**: `FileSessionManager`로 대화 히스토리를 `sessions/`에 JSON으로 저장·복원
- **데이터**: 강남 일대 식당 6곳(강남 파스타 하우스, 역삼 스시바, 신사 분식당,
  강남 트라토리아, 압구정 바베큐, 르 비스트로)을 `tools.py`에 정적으로 내장.
  리뷰 데이터는 별개 식당 5곳(트라토리아 벨라, 스시 오마카세 하루, 한우명가,
  르 비스트로, 매콤한 마라)이 `review_server.py`에 내장

## 설계 결정과 트러블슈팅

### 리뷰 MCP 서버를 통합 앱에 넣지 않은 이유

미션 4의 `review_server.py`는 미션 1~3의 통합 앱(`app.py`)에 연결하지
않고 독립 파이프라인으로 뒀다. 기술적으로는 `agent.py`에서 MCP 클라이언트를
하나 더 붙이면 되지만, **두 데이터셋의 식당 목록이 전혀 겹치지 않는다.**

| 출처 | 식당 |
|---|---|
| `tools.py` (미션 1~3) | 강남 파스타 하우스, 역삼 스시바, 신사 분식당, 강남 트라토리아, 압구정 바베큐, 르 비스트로 |
| `review_server.py` (미션 4) | 트라토리아 벨라, 스시 오마카세 하루, 한우명가, 르 비스트로, 매콤한 마라 |

겹치는 건 "르 비스트로" 하나뿐이다. 이 상태로 통합하면 사용자가
`search_restaurants`로 찾은 식당 대부분에 대해 `restaurant_reviews`가
"리뷰 정보를 찾지 못했습니다"를 반환한다 — 도구는 정상 동작하는데
사용자 경험만 망가지는 조합이다.

→ 판단: 미션 4는 "FastMCP로 도구를 노출하고 에이전트에 연결하는 방법"을
익히는 것이 목적이므로, 그 목적은 `review_agent.py`로 독립 검증하는 것으로
충족된다. 통합하려면 두 데이터셋의 식당 이름을 먼저 일치시켜야 하고,
그건 실습 목적과 무관한 데이터 정리 작업이다.

### MCP 서버 경로·인터프리터를 환경에 의존하지 않게 고침

`review_agent.py`와 `inspect_reviews.py`가 처음에는 MCP 서버를
`StdioServerParameters(command="python", args=["review_server.py"])`로
띄우고 있었다. 두 가지 문제가 있다.

1. `command="python"`은 PATH에 `python`이 없는 환경(macOS 기본은 `python3`만
   있는 경우가 흔하다)이나, 가상환경 밖의 다른 버전을 가리키는 환경에서
   깨진다.
2. `args=["review_server.py"]`는 cwd 기준 상대 경로라, 리포 루트에서
   실행하면 서버 스크립트를 찾지 못한다.

→ 수정: `command=sys.executable`(현재 가상환경 인터프리터를 그대로 재사용),
`args=[str(Path(__file__).parent / "review_server.py")]`(스크립트 위치 기준).
`agent.py`는 처음부터 이 방식이었는데 미션 4 스크립트들만 누락되어 있었다.
리포 루트에서 실행해 정상 동작을 확인했다.

### "새 대화 시작"이 이전 대화를 미아로 만드는 문제

"새 대화 시작"은 `session_id`를 새 UUID로 바꿀 뿐 이전 세션 파일을
지우지 않는다. `FileSessionManager`가 `sessions/session_<id>/`에 대화를
그대로 남겨두는데도, 이전 `session_id`(UUID)를 기억할 방법이 없어
사실상 다시 접근할 수 없었다 — 디스크에는 저장되는데 사용자는 못
보는 상태였다.

해결: `agent.py`에 `list_sessions()`를 추가해 `sessions/` 아래의
`session.json`(session_id, updated_at)과 첫 사용자 메시지를 읽어
요약 목록을 만들고, 사이드바에 "💬 이전 대화" 섹션으로 노출했다.
목록에서 하나를 클릭하면 그 `session_id`로 `chat_session_id`를 바꾸고
`agent`/`display_messages`/`tool_call_log`를 초기화해 다시 빌드한다
("새 대화 시작"과 같은 전환 패턴을 재사용).

`AppTest`로 이전 대화 버튼 클릭 → `session_id` 전환 → 예외 없음을
확인했다.

### 도구 호출 로그가 세션 복원과 비대칭이었던 문제

`FileSessionManager`가 대화 텍스트는 복원하는데, 사이드바의 도구 호출
로그(`tool_call_log`)는 항상 빈 리스트로 시작했다. 세션이 실제로는
이어지는데 로그만 끊긴 것처럼 보이는 비대칭이었다.

해결: `agent.messages`의 `assistant` 메시지에서 `toolUse` 블록을 순서대로
뽑아 로그를 재구성하는 `_rebuild_tool_call_log()`를 추가하고,
`_init_session_state()`에서 대화 텍스트 복원과 같은 시점에 함께 복원하게
했다.

같은 맥락에서, 도구 호출 로그가 턴이 쌓일수록 무한정 늘어나는 문제도
같이 고쳤다 — `MAX_TOOL_CALL_LOG_ENTRIES`(10개)로 캡을 걸어, 턴이 끝난
뒤 오래된 항목을 잘라낸다. 스트리밍 도중에 자르면 `toolUseId` → 인덱스
매핑이 어긋나므로, 한 턴의 스트리밍이 완전히 끝난 뒤에만 자른다.

### callback_handler 대신 stream_async를 쓴 이유

Strands의 동기 `agent()` 호출은 내부적으로 별도 스레드/이벤트 루프에서
실행되고, `callback_handler`도 그 스레드 안에서 호출된다. 그 안에서
`st.empty().markdown()` 같은 Streamlit 위젯 API를 부르면
`NoSessionContext` 예외가 난다 — Streamlit은 위젯 갱신이 스크립트의
메인 실행 컨텍스트에서 일어나야 하기 때문이다.

해결: `agent.stream_async()`를 Streamlit 스크립트 실행 흐름 안에서
`asyncio.run()`으로 직접 순회했다. 도구 호출 로깅과 텍스트 스트리밍
모두 이 순회 루프 안에서 처리한다.

### 도구 입력이 문자열로 스트리밍되는 문제

`current_tool_use` 이벤트의 `input`은 모델이 토큰 단위로 생성하는 JSON
문자열이 델타로 계속 이어붙는 형태로 전달된다(`''` → `'{"area": "강'`
→ `'{"area": "강남역", "cuisine": "이탈리안"}'`). 완성된 형태는 그 도구
호출의 마지막 이벤트에서만 확인할 수 있다.

해결: `toolUseId`를 키로 로그 항목을 upsert(있으면 최신 입력으로
덮어쓰기, 없으면 추가)하고, 입력 문자열이 유효한 JSON으로 파싱될 때만
dict로 변환해 저장했다.

### "이전 추천을 다른 식당으로 바꿔 달라" 요청이 무시되는 문제

초기 시스템 프롬프트는 "회상 요청이 오면 대화 히스토리를 참고해
안내하라"고만 지시했다. 그 결과 "거기 말고 르 비스트로로 바꿔
주세요" 같은 요청에서, 모델이 직전 `search_restaurants(area="강남역",
cuisine="이탈리안")` 결과에 "르 비스트로"가 없다는 이유만으로 "찾을 수
없다"고 답하고 도구를 재호출하지 않았다. 실제로는 르 비스트로가
프렌치 식당으로 존재하는데도 검증 없이 존재하지 않는다고 단정한
것이다.

해결: 시스템 프롬프트에 "새로 지정된 식당 이름으로 get_menu 또는
check_availability를 즉시 시도하고, 이전 검색 결과에 없다는 이유만으로
존재하지 않는다고 단정하지 말라"는 지시를 추가했다. 이후 같은 질문에
`check_availability`를 즉시 재호출해 정상 응답했다.

### 세션 재현성 주의사항

`mcp_server.py`의 예약 좌석 데이터(`_BOOKED_SEATS`)에 특정 날짜
(`"2026-07-29"`)가 하드코딩되어 있다. "내일" 같은 상대 날짜 질의는
`datetime.now()` 기준으로 계산되므로, 이 실습을 다른 날 재현하면
예약된 좌석 데이터가 매칭되지 않아 항상 "전석 여유"로 나온다. 기능은
깨지지 않지만, 데모 시나리오(좌석 2석만 남았다는 긴장감)를 재현하려면
날짜를 오늘 기준으로 바꿔야 한다.

## 실행 방법

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 미션 1~2: 에이전트 모듈만 단독 검증
.venv/bin/python3 agent.py

# 미션 3: Streamlit 앱 실행
.venv/bin/streamlit run app.py

# 미션 4: 리뷰 MCP 서버
.venv/bin/python3 inspect_reviews.py   # 도구 스키마 확인
.venv/bin/python3 review_agent.py      # 에이전트로 리뷰 질의
```

MCP 서버(`mcp_server.py`, `review_server.py`)는 클라이언트가 서브프로세스로
띄우므로 따로 실행할 필요가 없다.

us-west-2 리전의 Bedrock Claude Sonnet 4.6 인퍼런스 프로필에 접근 가능한
AWS 자격 증명이 필요하다.

## 검증 결과

Streamlit `AppTest`로 실제 채팅 입력을 시뮬레이션해 확인:

| 시나리오 | 결과 |
|---|---|
| "강남역 근처 이탈리안 식당 추천해 주세요" | `search_restaurants` 호출, 사이드바 로그 표시, 카드 2개 렌더링 |
| "내일 저녁 7시에 2명 예약 가능해요?" | "내일"→`2026-07-29` 정확히 변환, `check_availability` 2회 호출 |
| "거기 말고 르 비스트로로 바꿔 주세요" | 이전 조건(2명, 19:00)을 기억해 르 비스트로로 즉시 재조회 |

`streamlit run app.py --server.headless true`로 기동 후 `curl`로 HTTP
200 확인. 예외 없이 3턴 모두 완료.

미션 4(리뷰 MCP 서버)는 리포 루트에서 실행해 확인:

| 검증 항목 | 결과 |
|---|---|
| `inspect_reviews.py` 도구 스키마 조회 | `restaurant_reviews` / 파라미터 `restaurant_name: string (필수)` 출력, 종료 코드 0 |
| `review_agent.py` 자연어 질의 | "트라토리아 벨라 리뷰 어때요?" → 도구 자동 호출, 평점 4.5와 리뷰 3건 근거로 응답, 종료 코드 0 |
| cwd 의존성 | 리포 루트(`aws-training/`)에서 실행해도 정상 동작 — 스크립트 위치 기준 경로로 고친 뒤 확인 |

## 비용 주의사항

- Bedrock Claude Sonnet 4.6 호출마다 온디맨드 과금 발생.
- 상시 실행되는 리소스는 없음(로컬 Streamlit 서버, 로컬 stdio MCP
  서버). 앱을 종료하면 과금되는 리소스가 남지 않는다.
