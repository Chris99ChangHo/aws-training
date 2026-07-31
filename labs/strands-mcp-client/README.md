# MCP 연동 — stdio / streamable-http 트랜스포트

![Python](https://img.shields.io/badge/Python-3.14-3776AB?logo=python&logoColor=white)
![Strands Agents](https://img.shields.io/badge/Strands_Agents-1.50-4B32C3)
![MCP](https://img.shields.io/badge/MCP-1.29-000000)
![AWS](https://img.shields.io/badge/AWS-Bedrock-01A88D)

MCP(Model Context Protocol) 서버를 직접 만들고, Strands 에이전트가 두 가지
트랜스포트(stdio, streamable-http)로 그 서버의 도구를 사용하도록 연결한
실습입니다.

MCP는 에이전트와 도구 제공자를 분리하는 프로토콜입니다. 도구를 에이전트
코드 안에 `@tool`로 박아두면 그 에이전트만 쓸 수 있지만, MCP 서버로
빼면 여러 에이전트·클라이언트가 같은 도구를 공유할 수 있습니다.

## 아키텍처

```
restaurant_server.py (FastMCP 서버)
   │  도구: search_restaurants, get_restaurant_details
   │  데이터: 하드코딩된 식당 5곳
   │
   ├── stdio 트랜스포트 ──────── 01_stdio_client.py
   │     (클라이언트가 서버를 자식 프로세스로 실행)
   │
   └── streamable-http ───────── 02_http_client.py
         (서버를 미리 띄우고 HTTP로 접속)

03_mixed_tools.py — MCP 도구 + 로컬 @tool 도구를 한 에이전트에 함께 연결
```

트랜스포트가 나뉘는 기준은 서버의 생명주기입니다. stdio는 클라이언트가
서버를 직접 띄우고 끝나면 같이 종료되어 로컬 개발에 적합하고,
streamable-http는 서버가 독립적으로 떠 있어 여러 클라이언트가 붙거나
원격 배포할 때 씁니다.

## 실행 방법

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# stdio — 서버를 따로 띄우지 않습니다
python 01_stdio_client.py

# streamable-http — 터미널 2개 필요
python restaurant_server.py streamable-http   # 터미널 1
python 02_http_client.py                      # 터미널 2

python 03_mixed_tools.py
```

## 사전 조건

- `us-west-2`에서 Claude Sonnet 4.6 접근 권한 (에이전트가 Bedrock을 호출)
- MCP 서버 자체는 AWS에 의존하지 않아 단독 테스트가 가능합니다

## 검증 결과

MCP 서버는 Bedrock 없이 도구 함수를 직접 호출해 검증할 수 있습니다.

```
강남역 이탈리안: 🍽️ 트라토리아 벨라 (이탈리안) — 강남역, 50,000원/인, 평점 4.5
예산 3만 이하:  🍽️ 매콤한 마라 (중식) — 강남역, 25,000원/인, 평점 4.1
없는 조건:      조건에 맞는 식당이 없습니다. 조건을 완화해보세요.
없는 식당 상세: '없는식당' 식당을 찾을 수 없습니다.
```

필터 조합·빈 결과·미존재 항목까지 의도대로 동작합니다.

## 이론 정리

- [`notes/mcpclient-pattern.md`](./notes/mcpclient-pattern.md) — MCPClient 연결 패턴
- [`notes/challenge-tasks.md`](./notes/challenge-tasks.md) — 추가 과제 메모

## 설계 결정

이 실습은 Kiro CLI(모델: claude-opus-5)와 함께 진행했습니다. 아래 내용은
AI 에이전트가 실행한 도구 결과를 근거로 정리했으며, 판단은 사람이
검토·승인했습니다.

**stdio 클라이언트가 서버 경로를 스크립트 기준으로 잡는 이유** —
`args=["restaurant_server.py"]`처럼 상대 경로를 쓰면 리포 루트에서
실행할 때 서버를 찾지 못합니다. `Path(__file__).parent`로 절대 경로를
만들어 실행 위치와 무관하게 동작합니다.

**`command`에 `sys.executable`을 쓰는 이유** — `"python"`은 PATH에 없거나
가상환경 밖의 다른 버전을 가리킬 수 있습니다. `sys.executable`은 현재
실행 중인 인터프리터를 그대로 재사용하므로, 활성화된 venv의 패키지를
서버 프로세스가 확실히 물려받습니다.

## 보안 주의사항

`restaurant_server.py`를 `streamable-http` 모드로 띄우면 **인증 없이**
HTTP 서버가 열립니다. 이 실습은 로컬에서만 실행하고 데이터도 하드코딩된
가짜 식당 정보라 실제 위험은 없지만, 같은 패턴을 실제 데이터에 쓸 때는
인증(예: `Authorization: Bearer <token>` 헤더)을 반드시 추가해야 합니다.

## 비용 주의사항

상시 과금되는 리소스는 없습니다. MCP 서버는 로컬 프로세스라 비용이 없고,
에이전트의 Bedrock 호출량만 과금됩니다.
