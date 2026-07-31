# Generic Security Agent

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)
![Dependencies](https://img.shields.io/badge/runtime_deps-none-brightgreen)
![SARIF](https://img.shields.io/badge/SARIF-2.1.0_(OASIS)-informational)
![Semgrep](https://img.shields.io/badge/Semgrep-SAST-1B2F3D)
![Trivy](https://img.shields.io/badge/Trivy-SCA_·_IaC-1904DA?logo=trivy&logoColor=white)
![Nuclei](https://img.shields.io/badge/Nuclei-DAST-3E8EDE)
![MCP](https://img.shields.io/badge/MCP-stdio_JSON--RPC-000000)
![Kiro CLI](https://img.shields.io/badge/Kiro_CLI-adapter-FF9900)
![Claude Code](https://img.shields.io/badge/Claude_Code-adapter-D97757?logo=anthropic&logoColor=white)
![Codex CLI](https://img.shields.io/badge/Codex_CLI-adapter-412991)

특정 클라우드 벤더에도, 특정 AI 에이전트 하네스에도 종속되지 않는 보안
에이전트. STRIDE 위협 모델링, SAST, SCA, DAST를 오픈소스 스캐너로 수행하고,
결과를 OASIS 표준 SARIF로 내보내 **LLM 없이 결정론적으로** CI 게이팅한다.

출발점은 "AWS Security Agent를 벤더 독립적으로 바꾸자"였다. 작업하면서
종속성이 두 층이라는 게 드러났다 — 클라우드 벤더 종속과 **에이전트 하네스
종속**. 두 번째가 더 끈질기다. Kiro CLI 대신 Claude Code를 쓰는 건 AWS 종속을
Anthropic 종속으로 바꾸는 거래일 뿐이다. 그래서 경계를 하네스 바깥에 그었다.

### 원본과 범위가 어디까지 겹치는가

"벤더 독립으로 재구현"이 "기능을 전부 옮겼다"는 뜻은 아니다. 원본은 관리형
SaaS이고 이쪽은 로컬에서 도는 스크립트 묶음이라, 옮길 수 있는 것과 옮길 수
없는 것이 갈린다. [AWS 공식 기능 목록](https://aws.amazon.com/security-agent/)
기준으로 대조한 결과다.

| AWS Security Agent 기능 | 여기 | 근거 |
|---|---|---|
| MCP 통합 / IDE·CLI에서 실행 | **동등** | MCP 서버 자체 구현(`mcp/server.py`) + 하네스 3개 어댑터. 원본은 Kiro·Claude Code 플러그인 |
| STRIDE 위협 모델링 | **부분** | 절차·산출 형식을 프롬프트로 강제(신뢰 경계 → 데이터 흐름 → 카테고리 → 완화 위치 인용). 다만 컴포넌트 추출이 자동이 아니라 LLM이 코드를 읽는 방식이다 |
| 코드 보안 리뷰 | **부분** | Semgrep(SAST) + Trivy(SCA, 시크릿, IaC) + LLM 코드 리뷰. 원본의 "조직 보안 요구사항 팩"에 해당하는 정책 정의 형식은 없다 (`scanners/rules/`에 자체 Semgrep 룰을 넣는 것이 가장 가까운 대체물) |
| 재현 가능한 공격 경로 + 적용 가능한 수정 코드 | **부분** | finding 형식에 전제·단계·관찰 결과와 before/after 코드를 필수로 강제. 다만 **문서 형식의 강제이고 실행 검증이 아니다** |
| 온디맨드 침투 테스트 (다단계 공격 체인, 시뮬레이션 환경에서 익스플로잇 검증) | **없음** | nuclei 템플릿 기반 단발 프로빙까지다. 공격 체인 오케스트레이터도, 익스플로잇을 실제로 성립시켜 보이는 샌드박스도 없다. 이게 원본과 가장 큰 격차다 |
| 설계 문서 리뷰 (스펙·아키텍처 문서 분석) | **없음** | 프롬프트가 "리포에서 실제로 볼 수 있는 것"으로 범위를 좁혀놨다. 문서 수집 경로가 없다 |
| GitHub·GitLab·Bitbucket·Confluence 연동, PR 코멘트, 자동 수정 PR | **없음** | SARIF 출력이 GitHub Code Scanning·GitLab에 그대로 들어가는 **형식 호환**까지다. 웹훅·API 클라이언트는 없다 |
| SARIF 기반 결정론적 CI 게이트 (LLM 없이 판정) | **원본에 없는 것** | 게이트가 AI를 호출하지 않는다. 벤더 독립을 목표로 하니 "구독이 끊겨도 CI가 돈다"가 요구사항이 됐고, 원본에는 그 요구가 없다 |

정리하면 **원본의 SaaS·플랫폼 연동 축은 의도적으로 버렸고, 로컬에서 결정론적으로
돌아가는 축은 원본보다 강하다.** 침투 테스트의 익스플로잇 검증은 버린 게 아니라
못 만든 쪽에 가깝다 — 샌드박스가 필요하고, §14에서 적었듯 이 프로젝트의 가드는
샌드박스가 아니다.

> **보안 용어가 처음이라면** [`../docs/security-standards.md`](../docs/security-standards.md)를
> 먼저 읽는 게 빠르다. SAST/SCA/DAST의 차이, STRIDE가 무엇인지, CWE·CVSS·SARIF가
> 각각 어떤 질문에 답하는지, 그리고 이 실습의 각 결정이 어떤 표준에 근거한
> 것인지를 원문 링크와 함께 정리해뒀다.

## 30초 요약

AI 구독이 없어도 이 4줄은 동작한다. 스캔과 판정에 AI가 개입하지 않는다.

```bash
sh      scanners/run_sast.sh .        # 코드 검사
sh      scanners/run_sca.sh .         # 의존성·시크릿 검사
python3 gate/merge_sarif.py           # 결과 합치기
python3 gate/gate.py --fail-on high   # 판정: 종료코드 0=통과, 1=차단
```

AI는 결과를 읽고 수정 코드를 써주는 편의 기능이다. 없으면 불편할 뿐이다.

## 무엇을 하려느냐에 따라 볼 문서

문서가 4개로 나뉘어 있다. 전부 읽을 필요는 없다.

| 하려는 것 | 볼 곳 |
|---|---|
| 일단 돌려보고 싶다 | 위 30초 요약 → [스캐너 설치](./docs/setup-sec-tools.md) |
| 뭘 왜 깔았는지 / 어떻게 지우는지 | [로컬 환경 관리](./docs/local-environment.md) |
| 용어를 모르겠다 (SAST? STRIDE? SARIF?) | [표준과 개념](../docs/security-standards.md) |
| 회사 정책에 맞게 임계값을 바꾸고 싶다 | [포팅 가이드 §1](../docs/porting-to-other-harnesses.md) — 3층 지도 |
| 구독이 끝난 뒤에도 쓰고 싶다 | [포팅 가이드 §4](../docs/porting-to-other-harnesses.md) — 오픈소스 3방법 |
| 다른 AI 도구를 지원하고 싶다 | [포팅 가이드 §2–3](../docs/porting-to-other-harnesses.md) |
| 왜 이렇게 만들었는지 알고 싶다 | 이 문서의 [설계 결정과 트러블슈팅](#설계-결정과-트러블슈팅) (22건) |
| 뭐가 검증됐고 뭐가 안 됐는지 | 이 문서의 [검증 결과](#검증-결과) |
| 에러가 났다 | 아래 종료 코드 표 |

### 문제가 생기면 — 숫자 하나만 보면 된다

| 종료 코드 | 뜻 | 할 일 |
|---|---|---|
| 0 | 검사 완료, 문제 없음 | 없음 |
| 1 | 검사 완료, **취약점 발견** | 보고서 읽기 (정상 동작) |
| 2 | 안전장치가 막았다 | 화면의 이유 확인. DAST면 `.sec-scope` 확인 |
| 3 | **스캐너가 안 깔렸다** | [설치 문서](./docs/setup-sec-tools.md) |
| 4 | 검사가 깨졌다 | 네트워크 확인 (Trivy는 첫 실행에 DB 다운로드) |

3번이 0번과 분리된 게 핵심이다. **도구가 없는 상태가 "취약점 없음"으로 보고되면
안 된다.**

## 무엇이 벤더에 묶여 있는지

하네스를 아는 코드는 `adapters/build.py`(607줄) **안에만** 있다. 그 안에서
두 종류로 갈린다.

| 구간 | 줄 수 | 성격 |
|---|---|---|
| 선언적 매핑 — 표 2개(`CAPABILITY_TO_TOOLS` 27, `HOOK_MATCHERS` 5)와 읽는 함수 3개(23) | 55 | 하네스를 늘려도 표에 열 하나가 붙는다 |
| 하네스별 렌더러 5개 — `build_kiro` 58, `build_claude_agent` 43, `build_claude_settings` 31, `build_codex_config` 92, `build_codex_prompt` 38 | 262 | 설정 파일 형식이 하네스마다 다르므로 통째로 특화 |
| **합계** | **317** | 전체 3,966줄의 **8.0%** |

나머지 3,359줄(프롬프트 111, manifest 88, 스캐너 918, 게이트 576,
MCP 452, 테스트 1,214)은 어떤 하네스도 모른다.

숫자는 `ast`로 노드 범위를 세어 산출했다. 정의를 적어두는 이유는, 정의 없는
비율은 검증할 수 없고 유리한 쪽으로 흐르기 때문이다. 실제로 이 문서의 이전
판은 선언적 매핑 55줄만 세어 **1.4%**라고 적었다. 렌더러 262줄도 하네스
종속인데 분자에서 빠져 있었다 — §13에서 지적받은 것과 같은 오류를, 이번에는
유리한 방향으로 반복했다.

**네 번째 하네스의 비용**도 같은 방식으로 실측된다. Codex를 추가할 때 늘어난
코드는 선언적 매핑 6줄(capability 5개에 열 하나씩 + `HOOK_MATCHERS` 1줄)과
렌더러 2개 130줄, 합 **136줄**이다. 설정을 파일 하나로 표현하는 하네스라면
렌더러가 하나라 더 적게 든다.

아래 줄 수는 실측값이다(`wc -l`).

| 자산 | 줄 수 | 하네스 종속 |
|---|---|---|
| 시스템 프롬프트 (`agent/SYSTEM_PROMPT.md`) | 111 | 없음 (마크다운) |
| 중립 manifest (`agent/manifest.toml`) | 88 | 모델 ID 3줄만 |
| 스캐너 + 가드 (`scanners/` 7개 파일) | 918 | 없음 (POSIX sh) |
| SARIF 게이트 (`gate/` 2개 파일) | 576 | 없음 (stdlib Python) |
| MCP 서버 (`mcp/server.py`) | 452 | 없음 (개방 프로토콜) |
| 테스트 (`tests/` 4개 파일) | 1,214 | 없음 |
| **어댑터 생성기 (`adapters/build.py`)** | **607** | **그중 317줄** |

전체 3,966줄 중 하네스 종속은 **8.0%**다. 분자의 정의는 바로 위 표에 있다.

지원 하네스: **Kiro CLI, Claude Code, Codex CLI**. 네 번째를 추가하는 절차는
[포팅 가이드](../docs/porting-to-other-harnesses.md)에 있다.

## 아키텍처

```
                    단일 진실 공급원
        agent/SYSTEM_PROMPT.md + agent/manifest.toml
                          │
                          ▼
              adapters/build.py  ──── --check ──▶ CI 드리프트 감지
                    │     │     │
        ┌───────────┘     │     └───────────────┐
        ▼                 ▼                     ▼
  .kiro/agents/     .claude/agents/       .codex/config.toml
  *.json            *.md + settings.json  + generic-sec-agent.md
        │                 │                     │
        └────────┬────────┴─────────────────────┘
                 │  세 하네스가 같은 통제 지점을 공유
        ┌────────┴────────────────────┐
        ▼                             ▼
  PreToolUse 훅                  MCP 서버 (Tier 2)
  scanners/guard_scope.sh        mcp/server.py
  (쉘 + 파일읽기 경로 통제)        (도구 경로 통제)
        │                             │
        └──────────┬──────────────────┘
                   │ 두 경로가 같은 스코프 규칙을 참조
                   ▼
           scanners/_scope_lib.sh  ◀── .sec-scope (권한 경계)
                   │
                   ▼
        run_sast.sh / run_sca.sh / run_dast.sh
         semgrep      trivy        nuclei
                   │
                   ▼  SARIF 2.1.0
           reports/*.sarif
                   │
                   ▼
        gate/merge_sarif.py ──▶ gate/gate.py  (Tier 3)
                                     │
                                exit 0 = pass
                                exit 1 = fail   ◀── LLM 개입 없음
                                exit 4 = error
```

### 3개 티어

| 티어 | 목적 | 산출물 |
|---|---|---|
| **Tier 1** 어댑터 분리 | 단일 프롬프트에서 하네스별 설정 생성. 허술한 정규식 대신 PreToolUse 훅으로 DAST 스코프를 파싱·검증 | `adapters/build.py`, `scanners/guard_scope.sh` |
| **Tier 2** MCP 서버화 | 도구 로직과 인자 검증을 서버 안으로. 클라이언트가 몇 개든 통제 지점은 하나 | `mcp/server.py` |
| **Tier 3** 결정론적 게이트 | SARIF severity 임계값으로 차단. 확률적 판단을 빌드 경로에서 제거 | `gate/gate.py` |

## 실행 방법

### AI 없이 쓰기 (구독이 없어도 동작한다)

**스캔과 판정에는 AI가 전혀 개입하지 않는다.** `python3`만 있으면 된다.
어떤 구독도, API 키도, 네트워크도 필요 없다.

```bash
sh      scanners/run_sast.sh .        # 코드 검사
sh      scanners/run_sca.sh .         # 의존성·시크릿·IaC 검사
python3 gate/merge_sarif.py           # 결과 합치기
python3 gate/gate.py --fail-on high   # 판정 (exit 0=통과, 1=차단)
```

CI에 넣을 부분은 이게 전부다. AI는 결과를 읽고 수정 코드를 제안하는
편의 기능이고, 없으면 불편할 뿐 못 쓰는 게 아니다.

| 기능 | AI 필요? |
|---|---|
| 스캐너 실행 | 아니오 |
| SARIF 병합 | 아니오 |
| 합격/불합격 판정 | **아니오** (의도적) |
| 결과 해석·수정 코드 제안 | 예 |
| STRIDE 위협 모델링 | 예 |

로컬 오픈소스 모델로 옮기는 방향은
[포팅 가이드 §4](../docs/porting-to-other-harnesses.md)에 정리했다.

### AI 도구로 쓰기

세 하네스 모두 어댑터가 생성되어 있다.

```bash
# Kiro CLI
/agent generic-sec-agent

# Claude Code
claude --agent generic-sec-agent

# Codex CLI
codex "Follow .codex/generic-sec-agent.md and review this project"
```

Kiro에서는 `/agent swap generic-sec-agent`도 동작한다. `swap` 키워드는
서브커맨드와 이름이 겹치는 에이전트를 지정할 때 필요한 것이고, 이 이름은
겹치지 않으므로 둘 다 같다.

**Codex는 한 단계가 더 필요하다.** 훅을 처음 쓸 때 `/hooks`로 검토·신뢰해야
한다. 이걸 빼먹으면 **가드가 설정만 되고 실행되지 않는다.**

### 가드를 켜고 끄기 (Claude Code)

가드는 이 에이전트의 정책이고 프로젝트의 정책이 아니다. 일반 개발을 하는
세션까지 웹 검색 차단·인터프리터 차단·체이닝 차단에 걸리면 도구가 아니라
방해물이 된다. 그래서 **하네스마다 가드의 유효 범위를 에이전트 단위로 맞췄다.**

| 하네스 | 가드가 사는 곳 | 켜지는 시점 |
|---|---|---|
| Kiro CLI | `.kiro/agents/generic-sec-agent.json` | `/agent generic-sec-agent`로 바꿀 때 |
| Claude Code | `.claude/agents/generic-sec-agent.md` frontmatter | 에이전트를 **스폰**할 때 (Agent 도구 또는 `@generic-sec-agent`) |
| Codex CLI | `.codex/config.toml` | `/hooks`로 신뢰한 뒤 |

`.claude/settings.json`에는 훅을 넣지 않는다. 그 파일은 **프로젝트 전역**이라
모든 세션에 걸리고, 끌 방법이 파일을 편집하는 것뿐이다. 처음에는 여기에
훅을 넣었고 그 결과 일반 작업 세션이 전부 보안 정책 아래 들어갔다.

세션 **전체**를 보안 모드로 돌려야 할 때만 스위치를 켠다. 에이전트를 지정하지
않은 일반 세션까지 가드 아래 두고 싶을 때가 그 경우다.

```bash
cp .claude/settings.local.json.example .claude/settings.local.json   # 켜기
rm .claude/settings.local.json                                       # 끄기
```

파일을 스위치로 삼은 이유는 **사람만 끌 수 있어야** 하기 때문이다. 에이전트는
가드가 켜진 상태에서 `rm`이 차단되므로 자기 강제 장치를 스스로 지울 수 없다.
`.claude/settings.local.json`은 `.gitignore` 대상이라 개인 선택이 커밋되지
않고, `.example`만 리포에 남는다.

#### 실측 (Claude Code 2.1.220)

설계가 아니라 실행으로 확인했다. **훅이 실제로 실행됐는지**는 모델의 말이 아니라
훅 자체에 임시 프로브(호출 시 로그 한 줄)를 심어 세었다. 모델은 자기 시스템
프롬프트에서 체이닝 금지 규칙을 알고 있어서, 훅에 막히지 않고도 스스로 명령을
쪼갠 뒤 "차단됐다"고 서술할 수 있다 — 모델을 계측기로 쓰면 구분되지 않는다.
`--debug`는 훅 실행을 로깅하지 않아 쓸 수 없었다.

| 실행 모드 | 훅 발동 |
|---|---|
| `claude --agent generic-sec-agent` (메인 세션) | **1회** |
| Task 도구로 서브에이전트 스폰 | **1회** |
| 일반 메인 세션 (에이전트 지정 없음) | **0회** |

**에이전트 두 모드 모두에서 발동하고 일반 세션에서는 발동하지 않는다.** 이것이
"가드는 에이전트의 정책이고 프로젝트의 정책이 아니다"가 실제로 성립한다는
증거다.

차단 동작도 확인했다. 판별 명령은 명령 체이닝을 썼다 — 가드가 구조적으로
차단하고, 차단되지 않으면 무해한 출력만 나오므로 안전한 대조군이다.

| 세션 | `echo alpha; echo beta` |
|---|---|
| 일반 메인 세션 | `alpha` `beta` — **제약 없음** |
| 보안 에이전트 (스폰) | **차단**. `BLOCKED by guard_scope.sh: command chaining or substitution character (; & \| `) present.` |

**정정**: 이 절의 이전 판은 "frontmatter 훅은 `--agent`로 메인 세션을 띄울 때
발동하지 않는다"고 적고
[anthropics/claude-code#51372](https://github.com/anthropics/claude-code/issues/51372)을
근거로 달았다. 2.1.220에서 측정한 결과 **발동한다.** 이슈 내용이 이 버전에는
맞지 않는다. 그래서 `--agent`로 보안 작업을 할 때 아래 스위치는 필요 없다.

스위치가 여전히 필요한 경우는 하나 남는다 — **에이전트를 지정하지 않은 일반
세션까지** 가드 아래 두고 싶을 때(위 표의 0회 행). 그때만 켠다.

MCP 서버도 붙는다. 서브에이전트의 도구 목록에 `mcp__sec-scanners__get_scope`가
나타나고, 호출하면 `.sec-scope`의 실제 내용(`localhost`, `127.0.0.1`, `::1`)을
반환한다. 프로젝트 서브에이전트의 `mcpServers` frontmatter는 동작한다 —
[#54921](https://github.com/anthropics/claude-code/issues/54921)이 말하는
"무시된다"는 제약은 **플러그인** 서브에이전트에만 해당한다.

단, MCP 도구 호출에는 사람의 권한 승인이 한 번 필요하다.

```
Claude requested permissions to use mcp__sec-scanners__get_scope,
but you haven't granted it yet.
```

이건 결함이 아니라 의도에 맞는 동작이다. 보안 에이전트가 자기 스캐너를 쓰는
것을 사람이 한 번 확인하는 것이고, 이 리포의 원칙("분석·생성은 자유롭게,
파괴·유출은 사람이 승인")과 같은 결이다. **CI는 영향받지 않는다** — 결정론적
경로는 MCP를 거치지 않고 래퍼와 게이트를 직접 호출한다.

### 스캐너 없이 검증

스캐너가 하나도 설치되지 않은 상태에서도 통제 로직 전체가 검증된다.
설계상 스캐너와 통제 로직이 분리되어 있어서다.

```bash
cd agents/security

sh      scanners/preflight.sh       # 도구 설치 상태
sh      tests/test_guard_scope.sh   # 훅 차단 로직 100 케이스
python3 tests/test_gate.py          # 병합 + 게이트 + SARIF 정규화 39 케이스
python3 tests/test_mcp_server.py    # MCP 프로토콜 + 인자 검증 20 케이스
python3 tests/test_adapters.py      # 생성물의 성질 19 케이스
```

### 스캔과 게이팅

```bash
sh      scanners/run_sast.sh src
sh      scanners/run_sca.sh .
sh      scanners/run_dast.sh http://localhost:8080   # .sec-scope 안에서만
python3 gate/merge_sarif.py
python3 gate/gate.py --fail-on high --max-allowed 0
```

스캐너 설치는 [`docs/setup-sec-tools.md`](./docs/setup-sec-tools.md).

### 어댑터 재생성

```bash
python3 adapters/build.py           # 생성
python3 adapters/build.py --check   # 드리프트 감지 (CI용, 불일치 시 exit 1)
```

`.kiro/agents/`와 `.claude/agents/`는 **생성물이다.** 직접 고치면 `--check`가
잡는다.

### CI 예시

Tier 3는 LLM 없이 동작하므로 파이프라인에 그대로 넣을 수 있다. 아래는
문서용 예시이며, 이 리포에 활성 워크플로로 추가하지는 않았다.

```yaml
- name: Security scan
  run: |
    sh agents/security/scanners/run_sast.sh .
    sh agents/security/scanners/run_sca.sh .
    python3 agents/security/gate/merge_sarif.py

- name: Adapter drift
  run: python3 agents/security/adapters/build.py --check

- name: Gate
  run: python3 agents/security/gate/gate.py --fail-on high
```

---

## 설계 결정과 트러블슈팅

이 실습은 Kiro CLI(모델: claude-opus-5)와 함께 진행했습니다. 아래 트러블슈팅은
AI 에이전트가 실행한 도구 결과(테스트 출력, 종료 코드, 공식 문서 조회 결과)를
근거로 정리했으며, 어떤 해결 방향을 택할지는 사람이 검토·승인한 내용입니다.

### 1. 정규식 명령 허용목록은 통제가 아니다

처음 설계는 Kiro 설정의 `allowedCommands`에 `semgrep .*` 같은 패턴을 넣는
것이었다. 이건 사실상 무제한 쉘이다. 하네스는 명령 **문자열**을 매칭하므로
이 패턴은 다음도 자동 승인한다.

```bash
semgrep --version; rm -rf ~
```

보안 에이전트 설정에 이 구멍을 두는 건 앞뒤가 안 맞는다. 대신 Claude Code
문서에서 확인된 계약을 쓰기로 했다 — PreToolUse 훅이 stdin으로 JSON을 받고
**exit 2로 차단**한다. 훅은 명령을 데이터로 받으므로 토큰화해서 실제 스캔
타겟을 뽑아내 권한 파일과 대조할 수 있다. 정규식으로는 표현할 수 없는 검사다.

측정 결과 91 케이스 중 차단 대상 70건 전부 exit 2:

```
ok   semicolon chaining          exit=2
ok   userinfo trick              exit=2   # http://localhost@evil.test
ok   uppercase host evasion      exit=2   # http://EVIL.TEST
ok   host smuggled in header flag exit=2  # -H internal.corp.test
ok   nuclei against in-scope localhost exit=0
```

### 2. MCP 도구 호출은 PreToolUse 훅을 우회한다

Tier 2를 작성하다 발견했다. MCP 도구 호출은 쉘 명령이 아니므로 훅이 보지
못한다. 스코프 검증이 훅에만 있었다면, 에이전트가 쉘 대신 MCP를 쓰는 순간
통제가 사라진다.

두 곳에서 강제하되 규칙은 한 곳에 두기로 했다.

| 경로 | 강제 지점 | 규칙 |
|---|---|---|
| 쉘 | `guard_scope.sh` (PreToolUse 훅) | `_scope_lib.sh` |
| MCP | `run_dast.sh` (래퍼 자체) | `_scope_lib.sh` |

`run_dast.sh`에서 스코프 검증을 `require_tool`보다 **앞에** 배치했다. 덕분에
nuclei가 설치되지 않은 상태에서도 거부 로직을 실측할 수 있다.

```
$ sh scanners/run_dast.sh https://example.com   ; echo $?
[dast] REFUSED: 'example.com' is not in the authorised scope.
2
$ sh scanners/run_dast.sh http://localhost:8080 ; echo $?
[dast] target http://localhost:8080 (host 'localhost' is in scope)
[dast] nuclei is not installed.
3
```

### 3. Python `$`는 후행 개행을 허용한다 — 테스트가 잡은 실제 버그

MCP 서버의 인자 검증을 `^[A-Za-z0-9._:/@%?=&+~-]{1,512}$`로 썼다. 테스트에서
`"../../etc/passwd\n"`이 통과했다. Python 정규식의 `$`는 문자열 끝뿐 아니라
**끝 직전의 개행에도** 매칭된다.

스코프 계층이 잡아내 차단은 됐지만(방어 심층화가 동작한 셈이다), 인자
검증기가 먼저 막아야 한다. `\A...\Z`로 교체했다.

```
수정 전: 스코프 계층이 차단 (exit=2, "'..' is not in the authorised scope")
수정 후: 인자 검증기가 차단 ("contains characters outside the allowed set")
```

### 4. 스캐너 종료 코드는 서로 다르다

Semgrep은 **발견하면 exit 1**, Trivy는 `--exit-code`를 주지 않으면 항상 0이다.
래퍼에 `set -e`를 썼다면 Semgrep이 뭔가 찾는 순간 스크립트가 죽고 Trivy는
실행되지 않는다. 조용히 절반만 스캔한 리포트로 게이트가 통과한다.

종료 코드 규약을 명시적으로 분리했다.

| 코드 | 의미 |
|---|---|
| 0 | 스캔 완료 (발견 여부와 무관) |
| 2 | 거부 (권한 스코프 위반) |
| 3 | 스캐너 미설치 |
| 4 | 스캔 자체 실패 |

**발견 여부는 종료 코드에 영향을 주지 않는다.** 통과/차단 판정은 `gate.py`가
SARIF를 읽어서 한다. 특히 3번을 0번과 분리한 것이 중요하다 — 도구가 없는
상태가 "취약점 없음"으로 보고되면 안 된다.

### 5. `for TOKEN in $CMD`는 글롭을 확장한다

가드에서 명령을 토큰화할 때 쉘 워드 분할을 썼는데, 이건 글롭 확장도 같이
한다. `nuclei -u localhost *.txt`를 검사하면 현재 디렉토리의 파일명이
토큰으로 들어온다. 검사 대상이 모델이 실제로 쓴 인자가 아니게 된다.
`set -f`로 확장을 끄고 토큰화한 뒤 `set +f`로 되돌린다.

### 6. 타겟 추출은 과다추출 방향으로 기울였다

DAST 명령에서 타겟을 뽑을 때, 과소추출은 스코프 밖 호스트를 통과시키고
과다추출은 정상 스캔을 막는다. 후자가 안전하므로 그쪽으로 설계했다.
호스트 형태 토큰(IPv4/IPv6/점 포함 도메인)은 위치와 무관하게 전부 후보로
잡고, 명시적 타겟 플래그(`-u`, `-target` 등)의 값은 형태와 무관하게 잡는다.

부작용: `nuclei -u http://localhost -H internal.corp.test`는 차단된다.
`internal.corp.test`가 헤더 값이지만 호스트 형태이기 때문이다. 의도한
동작이다. 반대로 `nmap -sV --top-ports 100`처럼 타겟을 식별할 수 없는
명령도 차단된다 — 검증할 수 없는 스캔을 승인하지 않는다.

### 7. Claude Code의 `Bash(...)` 권한 문법은 검증할 수 없었다

Kiro가 확인한 결과 이 환경에 `claude` CLI가 설치되어 있지 않다. 따라서
Claude Code의 명령 단위 권한 규칙 문법을 살아있는 설치본으로 대조할 수
없었다.

검증하지 못한 문법으로 통제를 흉내 내는 대신, **문서로 확인된 PreToolUse
훅을 Claude Code의 유일한 명령 통제 지점**으로 두고 도구 단위 allow/deny만
생성하기로 했다. 서로 다른 말을 하는 통제 두 개보다, 확실히 동작하는 통제
하나가 낫다.

Kiro 쪽은 `allowedCommands`/`deniedCommands`를 생성한다(문서화된 정규식
계약). 양쪽 모두 훅이 실제 통제 지점이고, 정규식은 coarse backstop이다.

**남은 미확인 사항**: Kiro CLI의 `preToolUse` 훅 페이로드 스키마는 공식
문서에 "can block"까지만 나와 있고 stdin 스키마와 exit code 계약이 명시되지
않았다. 가드는 6개 JSON 경로를 시도하고 **전부 실패하면 fail-closed로
차단**한다. 계약이 다르면 첫 사용 시 즉시 드러난다. 조용히 통과시키는
것보다 낫다고 판단했다.

### 8. macOS bash는 3.2 (2007년판)

`declare -A` 같은 bash 4 기능을 쓸 수 없다. 전부 POSIX sh로 작성했다.
부수 효과로 CI 컨테이너의 dash/ash에서도 그대로 돌아간다.

### 9. manifest를 YAML이 아니라 TOML로

Python 표준 라이브러리에 YAML 파서가 없다. `tomllib`은 3.11부터 stdlib다.
MCP 서버는 CI 러너가 스캔 전에 가장 먼저 띄워야 하는 것이라, 그 경로에
`pip install`을 추가하는 건 실패 지점을 늘리는 일이다. Python 3.14.6에서는
휠이 없을 가능성도 실재한다.

같은 이유로 MCP 서버를 SDK 없이 stdlib JSON-RPC로 구현했다. 도구 서버에
필요한 프로토콜 표면은 `initialize`, `tools/list`, `tools/call` 세 개다.

### 10. `kiro-cli agent validate`는 에러를 내면서 exit 0을 반환한다

Kiro가 실행한 대조 실험 결과다. 검증기가 실제로 동작하는지 확인하려고
일부러 깨진 설정을 넣었다.

```
$ kiro-cli agent validate --path /tmp/broken-agent.json ; echo "exit=$?"
Error: Json supplied at /tmp/broken-agent.json is invalid:
       invalid type: string "not-an-array", expected a sequence
exit=0
```

CI에서 종료 코드만 믿으면 깨진 설정이 통과한다. stderr를 봐야 한다.
이 대조 실험 덕분에 "우리 설정은 출력 없이 exit 0"이 실제로 유효하다는
근거가 됐다.

### 11. Nmap은 DAST가 아니다

원래 요청은 Nmap을 DAST 도구로 배치했다. Nmap은 네트워크/포트/서비스 정찰
도구고, 구동 중인 애플리케이션에 요청을 보내 취약점을 찾는 DAST가 아니다.
Nuclei로 교체했다 — 단일 바이너리, Docker 불필요, 템플릿 기반이라 벤더
독립적이다.

Nmap을 포함한 능동 스캔 도구 전체는 `deny_commands`에 있어 **매번 사람이
승인**해야 한다. 위험은 에이전트가 내 머신을 망가뜨리는 게 아니라 스코프
밖 호스트를 스캔하는 것이고, 그건 정규식으로 신뢰성 있게 막을 수 없다.
승인 프롬프트가 실질적 통제 장치다.

### 12. 리포트 포맷을 자체 JSON에서 SARIF로

초안은 `security_report.json`이었다. SARIF 2.1.0(OASIS 표준)으로 바꿨다.
GitHub Code Scanning, GitLab, DefectDojo가 그대로 받는다. 더 중요한 건
SARIF가 보고서를 `runs` 배열로 모델링한다는 점이다 — 스캐너를 추가하는 게
`runs`에 하나 붙이는 일이고, 게이트에 새 출력 포맷을 가르치는 일이 아니다.

### 13. 독립 감사가 결함 8개를 찾았다 — 자기 검증으로는 못 본 것들

91개 테스트가 통과한 상태에서, **이 코드를 쓰지 않은 검토자**에게 감사를
맡겼다. 컨텍스트를 공유하지 않는 검토자 2명을 병렬로 투입했다(한 명은 보안
우회만, 한 명은 규약·주장 검증만).

결과: **8개 결함이 나왔다.** 그중 2개는 Critical이었다. 이 단계를 건너뛰었다면
"91/91 통과"라는 숫자만 남고 결함은 그대로 있었을 것이다.

| 심각도 | 결함 | 재현 |
|---|---|---|
| Critical | 인터프리터 우회 — 차단 목록에 `eval`/`sh -c`/`perl -e` 없음 | `eval cat /etc/shadow` → exit 0 |
| Critical | 게이트가 빈 SARIF를 통과 처리 | `{"runs":[]}` → PASS |
| High | `level` 대소문자 구분 → severity 강등 | `"level":"Error"` → medium |
| High | `float("NaN")`은 예외를 안 낸다 | `security-severity:"NaN"` → info |
| High | 자격증명 정규식이 후행 슬래시를 요구 | `cp -r ~/.aws /tmp/exfil` → exit 0 |
| Medium | `${IFS}` 미차단 | `cat${IFS}/etc/shadow` → exit 0 |
| Medium | `.envrc` 미매칭 | `cat /app/.envrc` → exit 0 |
| — | 테스트가 상태 의존적 | 잔존 `reports/`가 있으면 1건 실패 |

각각이 왜 놓쳤는지가 배울 점이다.

**인터프리터 우회**: 내 차단 목록은 "위험한 바이너리 이름"을 막았다. 하지만
`perl -e '...'`의 위험은 `perl`이 아니라 인용부호 안의 스크립트에 있고, 가드는
그 안을 읽지 못한다. **차단 목록이 검사할 수 없는 텍스트를 실행하는 도구는
그 자체로 차단 대상**이라는 원칙을 놓쳤다.

여기에 딜레마가 있었다. 우리 래퍼는 `sh scanners/run_sast.sh`로 실행되므로
`sh`를 무조건 막으면 스캔이 불가능해진다. 통제를 약화시키는 대신 **정확히 이
형태만 예외**로 했다.

```sh
^(sh|/bin/sh)[[:space:]]+([A-Za-z0-9._-]+/)*scanners/(run_sast|run_sca|run_dast|preflight)\.sh...
```

그리고 인자에 두 번째 스크립트가 있으면 예외를 취소한다
(`sh scanners/run_sast.sh /tmp/evil.sh` → 차단).

**`${IFS}`**: `$(`만 검사했다. `cat${IFS}/etc/shadow`는 가드에게는 토큰 하나,
쉘에게는 인자 두 개다. **가드가 읽는 문자열과 실행될 문자열이 다르면 어떤
검사도 무의미하다.** 그래서 `$`와 `{}`를 전면 금지로 바꿨다 — 확장되는 텍스트
자체를 거부하는 게 유일하게 건전한 규칙이다.

**빈 SARIF 통과**: 이게 실무적으로 가장 위험하다. 스캐너가 죽으면 `runs: []`가
남고, 게이트가 이걸 "발견 0건 = 통과"로 읽었다. **파이프라인이 조용히
초록불이 된다.** 게이트가 없는 것보다 나쁘다 — 근거 없는 승인 기록이 남기
때문이다.

`validate_report()`를 추가해서 아래를 전부 오류(exit 4)로 만들었다.

| 리포트 형태 | 의미 |
|---|---|
| `runs` 없음 / 빈 배열 | 아무것도 실행되지 않았다 |
| `runs`가 배열이 아님 | SARIF가 아니다 |
| `results`가 배열이 아님 | 결과 집합을 기록하지 않았다 |
| `executionSuccessful: false` | 도구가 스스로 실패를 보고했다 |

**`float("NaN")`**: 예외를 던지지 않는다. 그리고 NaN과의 모든 비교는 False다.
`>=9.0`, `>=7.0`, `>=4.0`, `>0` 전부 False → 최하위 버킷 `info`. 게다가 숫자
경로가 `level`보다 우선순위가 높아서, 멀쩡한 `level: error`까지 버려졌다.

**`~/.aws` 후행 슬래시**: 정규식이 `\.aws/`였다. `cp -r ~/.aws /tmp/exfil`은
슬래시 없이 디렉토리를 지목하고 자격증명 전체를 복사한다. 정규식을 좁게 쓸
때는 "이 패턴이 놓치는 표기법"을 따로 세어봐야 한다.

**상태 의존 테스트**: 내 테스트는 내 환경에서만 통과했다. 감사자 환경에는
이전 실행이 남긴 `reports/`가 있어서 1건이 실패했다. 파보니 **실제 버그가
하나 더** 있었다 — 래퍼는 `SEC_REPORT_DIR`을 존중하는데 게이트는 무시해서,
환경변수를 설정하면 쓰는 곳과 읽는 곳이 달라졌다. 양쪽을 맞추고 테스트는
격리된 임시 디렉토리를 쓰게 했다.

**README 수치도 지적받았다.** 코드 줄 수, 차단 케이스 수, 매핑 테이블 크기가
전부 실측값과 어긋나 있었다(줄 수는 과소, 차단 케이스는 과대). 시스템 프롬프트에
"미검증 주장 금지"를 넣어놓고 README에서 스스로 어겼다. 전부 `wc -l`·테스트
출력 실측값으로 정정했다. 당시의 틀린 숫자는 여기 적지 않는다 — 실제 값이
바뀔 때마다 이 문장이 또 어긋나기 때문이다.

### 14. 이 가드는 샌드박스가 아니다 (잔여 위험)

정직하게 남긴다. `guard_scope.sh`는 **알려진 탈출 경로를 막는 거부 목록**이고,
완전한 격리가 아니다. 거부 목록은 원리상 불완전하다.

| 남은 위험 | 왜 |
|---|---|
| 목록에 없는 인터프리터 | 새 런타임(예: 특이한 스크립트 엔진)은 목록에 없다 |
| `sed`의 `e` 명령 | GNU sed는 `s///e`로 실행이 가능하다. `sed`는 너무 자주 쓰여서 막지 않았다 |
| 예외 처리된 래퍼 자체의 버그 | `sh scanners/run_*.sh`는 인터프리터 검사를 면제받는다 |
| TOCTOU | 검사 시점과 실행 시점 사이에 심링크 대상이 바뀔 수 있다 |

그래서 가드는 **유일한 통제가 아니라 층 하나**다. 나머지 층은 사람의 승인
프롬프트(DAST 도구는 전부 `deny_commands`에 있어 매번 승인 필요), 두 지점에서
독립적으로 강제되는 스코프 검증, 그리고 결정론적 게이트다. 어느 한 층이
뚫려도 다음 층이 남는 구조가 목표다.

### 15. 하네스를 하나 더 붙이니 보안 구멍이 드러났다

Codex CLI 어댑터를 추가하면서, 세 하네스의 도구 구조를 나란히 놓고 나서야
보인 것이 있다.

| 하네스 | 파일 읽기 방식 |
|---|---|
| Kiro CLI | `read` — **별도 도구** |
| Claude Code | `Read` — **별도 도구** |
| Codex CLI | 쉘 명령으로 처리 (별도 도구 없음) |

내 훅은 matcher가 쉘 도구뿐이었다. 그러면 이렇게 된다.

```
Codex:       cat ~/.aws/credentials     → Bash 호출이므로 훅이 잡는다
Kiro:        read ~/.aws/credentials    → 훅이 보지 못한다
Claude Code: Read ~/.aws/credentials    → 훅이 보지 못한다
```

게다가 `read`/`Read`는 생성된 어댑터에서 **자동 승인 목록에 들어 있었다.**
사람 확인도 없이 통과한다. 자격증명 차단이 두 하네스에서 사실상 없었던 셈이다.

Codex는 이 구멍이 없다. 파일 읽기가 쉘이라서 하나의 matcher가 다 덮는다.
**구멍이 있는 쪽이 아니라 없는 쪽을 보다가 구멍을 찾았다.** 하네스가 하나면
"이게 원래 이런 건가"와 "내가 놓친 건가"를 구분할 수 없다.

수정: 가드가 명령이 없는 호출에서도 파일 경로를 꺼내 검사하고, 훅 matcher가
읽기 도구를 포함하게 했다.

```
Kiro         matcher: "shell", "read"        (훅 2개 등록)
Claude Code  matcher: "Bash|Read"
Codex        matcher: "^(Bash|apply_patch)$"
```

Kiro만 훅을 두 개 등록한 이유는, Kiro의 matcher가 정규식을 받는지 문서에
없어서다. 정규식 지원을 가정하는 대신 이름마다 하나씩 걸었다.

자격증명 정규식은 `CREDENTIAL_RE` 변수 하나로 모아서 명령 검사와 경로 검사가
같은 규칙을 쓰게 했다 — `_scope_lib.sh`와 같은 이유다.

9개 케이스를 추가했고, 추가 직후 전부 실패하는 것을 확인한 뒤 패치했다.

```
ok  Claude Code Read of aws credentials   exit=2
ok  Kiro read of dotenv                   exit=2
ok  read of ordinary source file          exit=0
ok  read of path containing env word      exit=0   ← environments/staging
```

### 16. Codex 훅 계약이 Claude Code와 동일했다

기대하지 않았던 결과다. Codex 공식 문서를 확인해보니:

| 항목 | Claude Code | Codex |
|---|---|---|
| 이벤트 | `PreToolUse` | `PreToolUse` |
| 입력 | stdin JSON | stdin JSON |
| 명령 위치 | `tool_input.command` | `tool_input.command` |
| 차단 | exit 2 + stderr | exit 2 + stderr |

`guard_scope.sh`를 **한 줄도 고치지 않고** Codex에 붙었다. 추상화 경계를
제대로 그었는지는 세 번째 소비자를 붙여봐야 알 수 있는데, 이번이 그 검증이었다.

반대로 Codex에는 다른 둘에 없는 층이 있다. `sandbox_mode`는 운영체제 수준
샌드박스이고, 거부 목록보다 강한 통제다. 거부 목록은 목록에 없는 걸 놓치지만
샌드박스는 능력 자체를 제한한다. 그래서 Codex 어댑터는 `sandbox_mode`를 켜고
훅을 그 위의 층으로 쓴다.

Codex 문서도 훅의 한계를 같은 식으로 말한다. README §14에 적은 잔여 위험과
같은 인식이다.

> Treat tool hooks as a useful guardrail, not a complete enforcement boundary.

**주의사항 하나**: Codex는 검토·신뢰하지 않은 훅을 실행하지 않는다. 설정 후
`/hooks`를 한 번 돌려야 한다. 안 하면 가드가 설정만 되고 inert 상태가 된다.
어댑터 생성 파일 안에 이 경고를 주석으로 넣어뒀다.

### 17. "벤더 독립"의 남은 구멍 — Semgrep 룰셋 라이선스

`--config auto`가 벤더 서비스에 종속된다는 점은 §12에 적었는데, **더 근본적인
것을 놓쳤다.** 엔진은 오픈소스인데 **룰셋은 그렇지 않다.**

| 구성 요소 | 라이선스 |
|---|---|
| Semgrep CE 엔진 | LGPL 2.1 (오픈소스) |
| **Semgrep 레지스트리 룰** | **Semgrep Rules License v1.0** |

이 실습이 쓰는 `p/security-audit`, `p/secrets`, `p/owasp-top-ten`이 후자다.
공식 문서 원문:

> All rules... are licensed under Semgrep Rules License v. 1.0. They are
> available **only for internal business use**. **Vendors cannot use
> Semgrep-maintained rules in competing products or SaaS offerings.**
> Individuals, security consultants, and companies are welcome to use the
> rules internally.

| 용도 | 가능 |
|---|---|
| 학습·포트폴리오 | 예 |
| 회사 내부 코드 검사 | 예 |
| 보안 컨설턴트의 고객사 검사 | 예 (명시적 허용) |
| **제품/SaaS로 판매** | **아니오** |

Trivy(Apache 2.0)와 Nuclei(오픈소스)는 이런 제약이 없다. Semgrep만 다르다.

완전 오프라인·완전 자유 룰셋이 필요하면 `SEC_SAST_CONFIG`로 로컬 룰
디렉토리를 지정해 레지스트리를 아예 쓰지 않을 수 있다. 그 경로는 이미
래퍼에 있다.

**부수 확인**: `--metrics=off`가 유효한 플래그임을 이번에 공식 문서로
확인했다. Semgrep은 레지스트리 룰을 가져올 때 기본으로 텔레메트리를
전송한다(`--metrics auto`가 기본값). 래퍼에 이미 `--metrics=off`가 들어
있었고, 이제 "미검증" 항목에서 뺄 수 있다.

### 18. 첫 실제 스캔에서 잡음이 신호를 덮었다

여기까지는 합성 픽스처로만 검증했다. 스캐너를 실제로 설치해 이 리포를
스캔하자 **63건이 나왔고, 그중 51건이 조치 불가능**했다.

| 발견 위치 | 건수 | 조치 가능? |
|---|---|---|
| 내 의존성 파일 (`requirements.txt`, `uv.lock`, `package-lock.json`) | 12 | **예** |
| `node_modules/**` — AWS CDK 패키지에 번들된 예제 Dockerfile·k8s YAML | 48 | 아니오 |
| `.cache/**` — 빌드 스테이징 사본 | 3 | 아니오 (중복) |

차단 대상 20건 중 15건이 남의 코드였다. **이런 게 쌓이면 사람이 게이트를
끈다.** 그러면 진짜였던 5건까지 같이 사라진다. 게이트가 없는 것보다 나쁘다.

임계값을 올리는 건 답이 아니다. 문제는 severity가 아니라 **범위**다.
`run_sca.sh`에 벤더·생성 디렉토리 제외를 넣었다.

```
node_modules  .venv  venv  .cache  vendor  site-packages
```

**조용히 건너뛰지 않는다.** 제외 목록을 매번 출력하고, `SEC_SCA_NO_SKIP=1`로
해제할 수 있다. 스캐너가 스스로 범위를 좁히면서 말을 안 하면, 그건 스캐너가
설치 안 된 것과 같은 실패 모드다 — 아무것도 안 봤는데 리포트가 깨끗해 보인다.

결과:

```
전:  63건 → 차단 20건 (조치 가능 5건, 잡음 15건)
후:  12건 → 차단  5건 (전부 조치 가능)
```

### 19. `--skip-dirs` 상대 경로가 cwd 기준이었다

18번을 구현하고 나서 **래퍼로 돌리면 여전히 63건**이 나왔다. 손으로 같은
명령을 치면 12건이었다. `sh -x`로 추적해보니 조립된 명령이 완전히 동일했다.

남은 변수는 실행 위치뿐이었다.

| cwd | 결과 |
|---|---|
| `/tmp` | 12건 |
| 리포 루트 | 12건 |
| **`agents/security` (타겟 내부, 제외 대상보다 깊은 곳)** | **63건** |
| `agents/security` + 절대 경로 패턴 | 12건 |

**Trivy는 상대 `--skip-dirs` glob을 스캔 대상이 아니라 현재 작업 디렉토리
기준으로 해석한다.** 래퍼를 실습 폴더 안에서 실행하면 `**/node_modules`가
아무것도 매칭하지 못하고, 조용히 통과한다.

이건 이 리포 스티어링의 첫 규칙과 **같은 종류의 버그**다.

> 읽고 쓰는 파일은 실행 위치(cwd)가 아니라 스크립트 파일 위치를 기준으로
> 해석한다. — `python-conventions.md`

경로의 의미가 실행 위치에 좌우되면 안 된다. 스캔 대상을 절대 경로로 해석한 뒤
패턴을 그 경로에 앵커링했다.

```sh
ABS_TARGET=$(cd "$TARGET" && pwd)
--skip-dirs "$ABS_TARGET/**/node_modules"
--skip-dirs "$ABS_TARGET/node_modules"
```

세 위치에서 실행해 전부 12건임을 확인했다.

**이 버그가 위험한 이유**: 에러가 나지 않는다. 제외가 안 먹으면 결과가 늘어날
뿐이라 "원래 이만큼 나오나 보다"로 넘어간다. 반대 방향이었다면(제외가 과하게
먹었다면) 리포트가 조용히 깨끗해졌을 것이고, 그건 훨씬 위험하다. 그래서
제외 목록을 출력하게 만든 판단이 여기서 값어치를 냈다.

### 20. 스캐너를 설치하자 내 테스트가 깨졌다

`semgrep`을 설치한 직후 MCP 테스트 1건이 실패했다.

```
FAIL: test_missing_scanner_is_exit_3_not_success
AssertionError: 'exit=3' not found in 'exit=0 (scan completed...)'
```

테스트가 검증하려던 성질은 옳다 — "없는 스캐너가 깨끗한 스캔으로 보고되면
안 된다". 그런데 **검증 방법이 환경에 의존했다.** `semgrep`이 이 머신에
없다는 사실을 전제로 삼았고, 설치되자 전제가 사라졌다.

이건 §13에서 감사자가 지적한 것과 같은 문제다. 그때는 잔존 `reports/`
디렉토리였고, 이번엔 설치된 도구였다. **테스트가 통과한 이유가 "코드가
맞아서"가 아니라 "환경이 그래서"인 경우다.**

고치는 방향은 두 가지였다.

| 방법 | 문제 |
|---|---|
| 아직 안 깔린 도구(`nuclei`)로 바꾸기 | 그것도 깔리면 또 깨진다 |
| **PATH를 제한해 도구를 숨기기** | 설치 여부와 무관하게 성립 |

후자를 택했다. 테스트가 서버에 넘기는 환경에서 `PATH`를 시스템 디렉토리로
제한하면, 스캐너가 깔려 있어도 `command -v semgrep`이 실패한다.

```python
PATH_WITHOUT_SCANNERS = "/usr/bin:/bin:/usr/sbin:/sbin"

result = self.call("run_sast", {"path": "."}, path=PATH_WITHOUT_SCANNERS)
self.assertIn("exit=3", body)
```

그리고 대칭 케이스를 추가했다 — **도구가 있으면 exit 0을 보고하는지**. 한쪽만
검증하면 "항상 3을 반환하는 버그"를 못 잡는다. 이쪽은 `semgrep`이 없으면
`skipTest`로 건너뛴다.

같은 문제를 안고 있던 DAST 테스트도 미리 고쳤다. `nuclei` 미설치를 전제로
exit 3을 기대하고 있었는데, 나중에 설치하면 깨질 코드였다.

검증:

| 환경 | 결과 |
|---|---|
| 스캐너 설치됨 | 178 케이스 전부 통과 |
| PATH 제한 (미설치 시뮬레이션) | 전부 통과 (대칭 케이스 1건 skip) |

**교훈**: 테스트가 무언가의 부재를 검증한다면, 그 부재를 테스트가 직접
만들어야 한다. 환경에 기대면 환경이 바뀔 때 조용히 의미를 잃는다.

---

### 21. 드리프트 검사가 통과하는데 허용 규칙이 죽어 있었다

디렉토리를 `security-engineering/`에서 `agents/security/`로 옮긴 뒤 최종
점검에서 발견했다. 생성된 Kiro 설정에 이런 규칙이 있었다.

```
"^agents/security/git (status|diff|log)( [A-Za-z0-9._/-]+)*$"
```

`agents/security/git`이라는 실행 파일은 없다. 이 규칙은 존재 가능한 어떤
명령과도 매칭되지 않는다.

원인은 `build.py`의 휴리스틱이었다.

```python
anchor(f"{LAB_REL}/{p}") if "/" in p else anchor(p)
```

"슬래시가 있으면 랩 상대 경로"라고 추론하는데, manifest의 git 항목은 인자
문자 클래스 `[A-Za-z0-9._/-]` **안에** 슬래시를 갖고 있다. 경로 구분자가
아니라 문자 클래스의 원소인데 구분할 방법이 없었다.

이 버그는 이전 작업이 만든 게 아니다. `LAB_REL` 값만 달랐을 뿐 처음부터
같은 접두어가 붙고 있었다. **`--check`는 이걸 잡을 수 없다** — 드리프트
검사는 "디스크의 파일이 생성기 출력과 같은가"만 보고, 생성기 출력이 옳은지는
보지 않는다. 매칭되지 않는 규칙은 영원히 자기 자신과 바이트 단위로 같다.

영향 방향은 보안 구멍이 아니라 반대쪽이었다. 의도했던 자동 승인이 걸리지
않아 `git status`가 매번 사람 승인을 받았다(fail-closed). 그래서 조용히
남아 있었다.

두 가지를 고쳤다.

**1. 추론을 제거하고 의도를 소스에 선언한다.** manifest가 `{lab}`
자리표시자를 직접 쓰고, `build.py`는 치환만 한다. 인식하지 못하는
자리표시자가 남으면 `ValueError`로 죽는다 — 조용히 통과시키면 같은 버그를
재생산하기 때문이다.

```toml
"{lab}/gate/gate\\.py( [A-Za-z0-9._/=-]+)*",
"git (status|diff|log)( [A-Za-z0-9._/-]+)*",   # 접두어 없음이 명시적
```

**2. 안정성 대신 성질을 검사하는 테스트를 추가했다** (`test_adapters.py`,
19 케이스). 핵심은 생성된 허용 규칙에서 정규식의 리터럴 머리 부분을 뽑아
**그 경로가 디스크에 실제로 존재하는지 확인**하는 것이다. 이 테스트가 원래
버그를 잡는지 변이 테스트로 확인했다 — manifest의 git 항목에 `{lab}/`를
다시 붙이면 19개 중 4개가 실패한다.

| 검사 | 왜 |
|---|---|
| 모든 규칙이 `^...$`로 앵커링 | 앵커 없는 허용 규칙은 없는 것보다 나쁘다 |
| 랩 상대 규칙의 리터럴 경로가 실존 | 죽은 규칙을 직접 잡는다 |
| 접두어가 붙은 규칙은 `scanners/`·`gate/` 하위뿐 | 외부 프로그램에 경로가 붙는 오분류 차단 |
| `git status` 매칭, `git push`·`git commit`·`git reset` 비매칭 | 허용 범위가 읽기 전용인지 |
| 거부 규칙이 체이닝·자격증명 경로·DAST 도구를 실제로 막는지 | 목록의 존재가 아니라 동작을 검사 |
| 생성물에 홈 디렉토리·절대 경로 없음 | 커밋되는 파일에 개인 환경이 박히는 것 방지 |

**교훈**: 생성기에는 두 종류의 테스트가 필요하다. *출력이 소스와 일치하는가*
(드리프트)와 *출력이 뜻대로 동작하는가*(성질). 앞의 것만 있으면, 틀린
출력이 안정적으로 틀린 채 남는다.

### 22. 같은 수치 오류를 반대 방향으로 반복했다

§13에서 "README 수치를 부풀렸다"고 지적받고 전부 실측값으로 정정했다. 그런데
이번 점검에서 **유리한 방향의 오류**가 남아 있는 게 드러났다.

헤드라인 주장이 "전체 3,966줄 중 하네스 종속 **1.4%**"였다. 분자로 센 것은
선언적 매핑 55줄(표 2개 + 읽는 함수 3개)뿐이었다. 그런데 하네스별 렌더러
5개(`build_kiro` 58, `build_claude_agent` 43, `build_claude_settings` 31,
`build_codex_config` 92, `build_codex_prompt` 38 = 262줄)도 하네스 종속이다.
설정 파일 형식이 하네스마다 다르므로 통째로 특화 코드다.

실제 값은 317줄, **8.0%**다. 5.7배 낮게 적혀 있었다.

§13의 오류(줄 수를 낮게, 차단 케이스를 높게)는 방향이 섞여 있어서 "부주의"로
설명된다. 이건 다르다. **분자를 좁게 정의하면 프로젝트가 더 좋아 보인다.**
그 방향의 오류는 스스로 다시 세어볼 동기가 생기지 않는다.

그래서 두 가지를 규칙으로 남겼다.

1. **비율을 적을 때 분자·분모의 정의를 같은 자리에 적는다.** 정의 없는 비율은
   검증할 수 없고, 검증할 수 없으면 유리한 쪽으로 흐른다.
2. **분류 축을 섞지 않는다.** `adapters/build.py`는 도메인 축에서는 완전
   범용(DevOps 에이전트도 어댑터가 필요하다)이고 하네스 축에서는 317줄이
   종속이다. 한쪽 축의 "범용"을 다른 축에 옮겨 쓰면 위와 같은 결론이 나온다.
   `agents/README.md`의 이음새 표에 두 축이 직교한다고 명시해뒀다.

**교훈**: 자기에게 불리한 수치는 재검산 동기가 있어서 결국 고쳐진다. 유리한
수치는 그렇지 않다. 그래서 수치 검증은 감사 항목으로 고정해야 한다
(`.kiro/skills/agent-release-check/`).

### 23. DAST를 종단으로 돌리자 게이트가 발견을 "오류"로 보고했다

`nuclei`를 설치하고 로컬 대상(`127.0.0.1:8099`, `.git/config`를 의도적으로
노출)에 처음으로 종단 실행했다. 스캔은 성공했고 `git-config`를 medium으로
찾았는데, 게이트가 **exit 4**로 판정을 거부했다.

```
error: Nuclei reported executionSuccessful=false. The scan did not complete,
so its result set is not evidence of a clean tree.
Refusing to emit a verdict. An unusable report is an error, not a pass.
```

원인은 nuclei v3.11.0이 **완료된 스캔에도 `invocations[].executionSuccessful`을
`false`로 쓴다**는 것이다. SARIF의 `arguments` 배열에 우리가 넘긴 플래그가
그대로 있고 결과도 1건인데 자기 실행이 실패했다고 적혀 있다.

게이트 규칙 자체는 옳다 — 스캐너가 죽어서 빈 리포트가 나온 것을 "깨끗함"으로
읽으면 안 된다. 문제는 nuclei의 **다른 습관과 결합될 때** 생긴다.

| nuclei 상황 | SARIF | `executionSuccessful` | 게이트 |
|---|---|---|---|
| 발견 없음 | 파일을 **아예 쓰지 않는다** → 래퍼가 빈 SARIF 생성 | `true` | **PASS** |
| 발견 있음 | nuclei가 쓴다 | **`false`** | **exit 4 (오류)** |

**깨끗하면 통과하고 발견이 있으면 스캐너 오류로 나온다.** exit 4를 "도구 문제니
나중에 보자"로 읽는 사람에게는 발견이 조용히 사라진다. 게이트가 발견을 감추는
방향으로 실패하는 것이라 가장 나쁜 조합이다.

→ **래퍼에서 정규화한다.** `scanners/normalize_sarif.py`가 `false`를 `true`로
뒤집고, `run_dast.sh`는 **nuclei가 exit 0으로 끝난 뒤에만** 호출한다. 실제로
실패한 스캔은 그 위 분기에서 이미 exit 4로 빠지므로 이 경로에 오지 않는다.

게이트에 넣지 않은 이유: 결정론적 판정기가 "어느 스캐너가 만든 파일인지"에
의존하게 된다. 도구의 관례를 흡수하는 것은 래퍼의 일이고, 래퍼는 이미 종료
코드에 같은 일을 하고 있다.

파싱 불가능한 파일은 손대지 않는다. 읽을 수 없는 리포트를 덮어쓰면 **왜 쓸 수
없는지에 대한 증거가 사라진다.** 게이트가 거부하는 것이 맞는 결과다.

`[교훈]` 이 결함은 **단위 테스트 173개가 전부 통과하는 상태에서** 남아 있었다.
테스트가 쓴 SARIF 픽스처는 우리가 만든 것이라 `executionSuccessful: true`였고,
실제 도구가 무엇을 쓰는지는 아무도 확인하지 않았다. 계약을 테스트하는 것과
**도구가 그 계약을 지키는지 확인하는 것은 다른 일**이다. 스코프 거부 로직을
nuclei 없이 실측한 것(§16)은 유효했지만, 그것으로 "DAST 계층이 동작한다"고
말할 수는 없었다.

## 검증 결과

전부 이 세션에서 실측한 값이다.

### 실제 스캔 (스캐너 설치 후)

합성 픽스처가 아니라 **이 리포를 실제로 스캔한 결과**다.

```
$ sh scanners/run_sast.sh <repo>      → exit 0, 발견 0건 (룰 725개 로드, 3.7초)
$ sh scanners/run_sca.sh  <repo>      → exit 0, 발견 12건
$ python3 gate/merge_sarif.py         → 2 runs, 12 results
$ python3 gate/gate.py --fail-on high → FAIL, exit 1
```

게이트 출력:

```
threshold   : high or above
budget      : 0

severity    count
critical        0
high            5
medium          4
low             3
total          12

blocking findings (5):
  [high] CVE-2026-14257 labs/.../cdk/package-lock.json:2377   brace-expansion
  [high] CVE-2026-14257 labs/.../cdk/package-lock.json:2104   brace-expansion
  [high] CVE-2026-52869 labs/.../RestaurantAgent/uv.lock:1    mcp
  [high] CVE-2026-52870 labs/.../RestaurantAgent/uv.lock:1    mcp
  [high] CVE-2026-59950 labs/.../RestaurantAgent/uv.lock:1    mcp

verdict     : FAIL
```

같은 리포트에 `--fail-on critical`을 주면 `PASS` (exit 0). 임계값이 판정을
바꾸고, 판정은 항상 재현된다.

실제로 취약한 패키지 3개가 특정됐다.

| 패키지 | CVE | 최고 점수 | 위치 |
|---|---|---|---|
| `mcp` | CVE-2026-59950 / 52870 / 52869 | 8.0 | `labs/.../RestaurantAgent/uv.lock` |
| `brace-expansion` | CVE-2026-14257 / 13149 | 7.5 | `labs/.../cdk/package-lock.json` |
| `streamlit` | CVE-2026-33682 / 10804 | 4.7 | 실습 3곳의 `requirements.txt` |

**semgrep만 돌렸다면 "깨끗하다"는 결론이 나왔을 것이다.** 코드 패턴 위반은
0건이고 문제는 전부 의존성에 있었다. 도구를 나눠 쓰는 이유가 이것이다.

### 테스트

스캐너가 하나도 없는 상태에서도 통제 로직 전체가 검증된다는 점이 설계
목표였고, 그 성질은 스캐너를 설치한 뒤에도 유지된다.

독립 감사와 Codex 어댑터 추가 이후 수치다. 발견된 결함마다 **재현 테스트를
먼저 추가해 실패를 확인한 뒤** 패치했다.

| 대상 | 케이스 | 결과 |
|---|---|---|
| `test_guard_scope.sh` — 훅 차단 로직 (차단 76 / 허용 24) | 100 | **100 passed, 0 failed** |
| `test_gate.py` — SARIF 병합·게이트·리포트 무결성 | 34 | **Ran 34 tests, OK** |
| `test_mcp_server.py` — MCP 프로토콜·인자 검증 | 20 | **Ran 20 tests, OK** |
| `test_adapters.py` — 생성된 어댑터의 성질 | 19 | **Ran 19 tests, OK** |
| 합계 | **178** | 전부 통과 |

증가 경위 — 테스트가 늘어난 지점이 곧 결함이 발견된 지점이다.

| 시점 | 케이스 | 계기 |
|---|---|---|
| 최초 구현 | 91 | — |
| 독립 감사 후 | 144 | 결함 8개 (§13) |
| Codex 어댑터 후 | 153 | 읽기 도구 구멍 (§15) |
| 스캐너 설치 후 | 154 | 환경 의존 테스트 (§20) |
| 디렉토리 이전 후 | **178** | 죽은 허용 규칙 (§21) |

### 게이트 판정 (픽스처 SARIF 2개 병합)

```
$ python3 gate/merge_sarif.py tests/fixtures/semgrep.sarif tests/fixtures/trivy.sarif
  semgrep.sarif: 1 run(s), 3 result(s)
  trivy.sarif:   1 run(s), 4 result(s)
merged 2 run(s), 7 result(s)

$ python3 gate/gate.py --report reports/merged.sarif
threshold   : high or above
budget      : 0

severity    count
critical        2
high            2
medium          2
low             1
info            0
total           7

blocking findings (4):
  [critical] semgrep  python.lang.security.audit.dangerous-subprocess-use app/tasks.py:42
  [high    ] semgrep  generic.secrets.hardcoded-token config/settings.py:9
  [critical] Trivy    CVE-2021-44228 pom.xml:31
  [high    ] Trivy    CVE-2023-45853 usr/lib/zlib1g:1

verdict     : FAIL        (exit 1)
```

같은 리포트에 `--fail-on critical --max-allowed 5`를 주면 `PASS` (exit 0).
동일 입력 3회 실행 시 출력이 바이트 단위로 동일함을 테스트로 확인했다
(`test_verdict_is_reproducible`).

### 어댑터

| 검증 | 결과 |
|---|---|
| `kiro-cli agent validate` | 에러 출력 없음 → 유효 |
| 대조: 깨진 설정 | `Error: ... expected a sequence` → 검증기가 실제로 동작함 |
| `kiro-cli agent list` | `generic-sec-agent  Workspace` 등록 |
| Kiro 훅 matcher | `shell`, `read` 2개 등록 확인 |
| Claude Code frontmatter YAML 파싱 | OK (임시 venv의 PyYAML로 확인) |
| Claude Code frontmatter 미문서화 키 | 없음 |
| Claude Code 훅 matcher | `Bash|Read` |
| **Codex `config.toml` tomllib 파싱** | **OK** |
| Codex 키 검증 | `model` / `approval_policy` / `sandbox_mode` / `web_search` / `features.hooks` / `mcp_servers` / `hooks.PreToolUse` 전부 문서 대조 완료 |
| Codex 훅 matcher | `^(Bash\|apply_patch)$` |
| `build.py --check` (동기) | exit 0 |
| `build.py --check` (손편집 후) | exit 1, 드리프트 지적 |

### 종료 코드 실측

현재 환경(semgrep·trivy·nuclei 전부 설치됨)에서 측정한 값이다.

| 명령 | 코드 | 의미 |
|---|---|---|
| `run_dast.sh` (인자 없음) | 2 | 거부 |
| `run_dast.sh https://example.com` | 2 | 스코프 밖 (도구 확인 전에 거부) |
| `run_dast.sh http://localhost@evil.test/` | 2 | userinfo 우회 — authority는 `evil.test` |
| `run_dast.sh http://evil-localhost.test/` | 2 | 접미어 트릭 — 부분 일치 없음 |
| `run_dast.sh http://127.0.0.1:8099` | **0** | 스코프 통과, nuclei 실행 완료 |
| `run_sast.sh gate` | **0** | semgrep 실행 완료 |
| `run_sca.sh gate` | **0** | trivy 실행 완료 |
| `run_sast.sh` (PATH 제한으로 semgrep 숨김) | 3 | 도구 미설치 |
| `gate.py` (리포트 없음) | 4 | 오류 (통과 아님) |
| `gate.py` (`runs: []`) | 4 | 오류 (스캔 증거 없음) |
| `gate.py` (취약점 발견, `--fail-on high`) | 1 | 차단 |
| `gate.py` (같은 리포트, `--fail-on critical`) | 0 | 통과 |

**3번과 0번이 갈리는 게 핵심이다.** 같은 `run_sast.sh`가 도구 유무에 따라
3과 0을 반환한다. 이 구분이 없으면 도구가 없는 상태가 "취약점 없음"으로
보고된다.

### AI 없이 동작함 (실측)

```
실행 환경: python3 만. AI 호출 0회, 네트워크 0회, API 키 없음

merged 2 run(s), 7 result(s)
verdict : FAIL
종료코드 1
```

### 검증하지 못한 것

정직하게 남긴다.

| 항목 | 이유 |
|---|---|
| Codex 어댑터 실행 | `codex` CLI 미설치. 문서 대조까지만 |
| Codex 서브에이전트 형식 | 문서 확인 못 함. 프롬프트를 별도 파일로 제공하는 방식으로 우회 |
| Kiro `preToolUse` 훅 페이로드 스키마 | 공식 문서에 미명시. fail-closed로 대응 |
| Kiro `preToolUse` matcher의 정규식 지원 | 미명시. 이름마다 훅을 하나씩 등록해 회피 |
| `.codex/config.toml` 실제 적용 | `codex` CLI 미설치 |
| Trivy `image` 모드 | Docker 미설치. 레지스트리 이미지 참조는 이론상 가능하나 미실행 |

해소된 항목:

| 항목 | 어떻게 |
|---|---|
| **semgrep 실제 실행** | **설치 후 실행 확인 — 룰 725개, 3.7초, SARIF 2.1.0 출력** |
| **trivy 실제 실행** | **설치 후 실행 확인 — 실제 CVE 12건 탐지** |
| **`semgrep --metrics=off` / `--sarif`** | **플래그 수용 실측 확인** |
| **`trivy --scanners vuln,secret,misconfig`** | **실행 확인** |
| **파이프라인 종단 (스캔 → 병합 → 게이트)** | **실데이터로 확인, exit 1** |
| **Claude Code 어댑터 실행** | **실행 확인 — 에이전트 로드, frontmatter 훅 발동·차단, 메인 세션은 비제약, MCP 도구 호출까지** |
| **`nuclei -sarif-export`** | **실행 확인 — v3.11.0, 템플릿 13,391개. 다만 완료된 스캔에도 `executionSuccessful: false`를 쓴다(§23)** |
| Codex 훅 차단 계약 | Codex 공식 문서로 확인 — exit 2 + stderr (§16) |

## 비용 주의사항

**상시 과금되는 클라우드 리소스를 만들지 않는다.** AWS 리소스도, 외부 SaaS
계정도 필요 없다. 스캐너는 모두 로컬 실행 오픈소스다.

발생하는 비용은 두 가지다.

- **LLM 토큰**: 에이전트 대화 비용. Tier 3 게이트는 LLM을 쓰지 않으므로 CI
  실행 횟수는 토큰 비용과 무관하다.
- **네트워크**: Trivy 취약점 DB(첫 실행), Nuclei 템플릿(첫 실행), Semgrep
  레지스트리 룰(실행 시). 오프라인이 필요하면 `SEC_SAST_CONFIG`로 로컬 룰을
  지정한다.

DAST는 `.sec-scope`의 호스트만 대상으로 하고 기본값은 루프백뿐이므로,
의도치 않은 외부 트래픽이 발생하지 않는다.

## 파일 구성

```
agents/security/
├── agent/
│   ├── SYSTEM_PROMPT.md      단일 진실 공급원 (증거 마커, finding 형식)
│   └── manifest.toml         중립 권한·도구 선언
├── adapters/build.py         하네스별 어댑터 생성 + --check
├── scanners/
│   ├── _scope_lib.sh         스코프 규칙 (단일 구현, 두 경로가 공유)
│   ├── _lib.sh               종료 코드 규약
│   ├── guard_scope.sh        PreToolUse 훅
│   ├── preflight.sh          도구 설치 상태
│   ├── rules/                자체 Semgrep 룰 (비어 있어도 정상)
│   └── run_{sast,sca,dast}.sh
├── gate/
│   ├── merge_sarif.py        SARIF runs 병합
│   └── gate.py               결정론적 게이트 (Tier 3)
│   └── normalize_sarif.py    도구 관례 정규화 (§23)
├── mcp/server.py             MCP 서버 (Tier 2, stdlib only)
├── tests/                    178 케이스 (guard_scope 100, gate 39,
│                             mcp_server 20, adapters 19)
├── docs/setup-sec-tools.md   스캐너 설치
└── .sec-scope                DAST 권한 경계
```

생성물(리포에 커밋되지만 직접 수정하지 않음):

```
.kiro/agents/generic-sec-agent.json      Kiro CLI
.claude/agents/generic-sec-agent.md      Claude Code
.claude/settings.json                    Claude Code 권한·훅
.codex/config.toml                       Codex CLI 권한·샌드박스·훅·MCP
.codex/generic-sec-agent.md              Codex CLI 프롬프트
```

## 관련 문서

| 문서 | 내용 |
|---|---|
| [표준과 개념](../docs/security-standards.md) | SAST/SCA/DAST 구분, STRIDE, CWE·CVSS·SARIF, 설계 원칙 ↔ 코드 매핑 |
| [포팅 가이드](../docs/porting-to-other-harnesses.md) | 다른 AI 도구로 옮기는 절차, 3층 지도, 오픈소스 모델 방향 |
| [스캐너 설치](./docs/setup-sec-tools.md) | Semgrep/Trivy/Nuclei/jq 설치 명령, 라이선스 주의 |
| [로컬 환경 관리](./docs/local-environment.md) | **용도별 설치 이유, 실측 용량, 제거 절차, 외부 통신 통제** |
