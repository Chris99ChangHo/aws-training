# AWS Training

AWS 오프라인 교육 과정 기록과, 그 과정에서 파생된 에이전트 작업물입니다.

성격이 다른 두 축으로 나뉘어 있습니다.

| 축 | 폴더 | 성격 |
|---|---|---|
| **과정** | `generative-ai-essentials/` 등 | 학습 기록. 시간순·과정별 |
| **에이전트** | [`agents/`](./agents) | 작업물. AWS 에이전트를 해체해 벤더 독립으로 재구현한 계열 |

## 에이전트

AWS가 제공하는 에이전트를 해체해서, 특정 클라우드 벤더에도 특정 AI
도구(하네스)에도 종속되지 않게 재구현한 작업물입니다.

| 에이전트 | 원본 | 상태 | 내용 |
|---|---|---|---|
| [`agents/security/`](./agents/security) | AWS Security Agent | 동작 (테스트 178, CI 활성) | STRIDE 위협 모델링, SAST/SCA/DAST, SARIF 결정론적 게이트가 [GitHub Actions에서 실행](./.github/workflows/security-gate.yml) — 모델 호출 없음. Kiro CLI / Claude Code / Codex CLI 어댑터를 단일 프롬프트에서 생성 |

계열 공통 설계 원칙과 문서는 [`agents/README.md`](./agents/README.md)에 있습니다.

## 과정 목록

| 과정 | 폴더 | 내용 |
|---|---|---|
| Generative AI Essentials on AWS | [`generative-ai-essentials/`](./generative-ai-essentials) | Bedrock Knowledge Base, RAG, 검색 품질 튜닝 |
| Security Engineering on AWS | [`security-engineering/`](./security-engineering) | (실습은 `agents/security/`로 분리) |
| Developing Generative AI Applications on AWS | [`developing-genai-apps/`](./developing-genai-apps) | Strands Agents, MCP, Streamlit 챗봇 |
| DevOps Engineering on AWS | [`devops-engineering/`](./devops-engineering) | (진행 예정) |
| (과정 외) 기능 단위 랩 | [`labs/`](./labs) | InvokeModel, Strands 기초, MCP 트랜스포트, AgentCore Runtime |

## 구조

```
aws-training/
├── agents/                             <- 벤더 독립 에이전트 계열
│   ├── README.md                       계열 개요·공통 설계 원칙
│   ├── docs/                           계열 공통 문서 (표준, 포팅 가이드)
│   └── security/                       에이전트 하나당 폴더 하나
│
├── generative-ai-essentials/           <- 과정
│   ├── README.md
│   ├── notes/                          이론 정리 (선택)
│   └── seoul-travel-planner-kb/        실습
├── security-engineering/
├── developing-genai-apps/
├── devops-engineering/
└── labs/
```

`.kiro/`, `.claude/`, `.codex/`의 에이전트 설정은 **생성물**입니다. 직접
수정하지 않고 `agents/<이름>/adapters/build.py`로 재생성합니다.

## 도구 체인

MCP 서버 설정을 리포에 포함해서, 클론한 사람이 같은 도구로 재현할 수 있게
했습니다. 하네스마다 설정 위치가 달라 두 파일을 유지합니다.

| 파일 | 읽는 하네스 |
|---|---|
| `.mcp.json` | Claude Code |
| `.kiro/settings/mcp.json` | Kiro CLI |

| 서버 | 상태 | 용도 |
|---|---|---|
| `aws-knowledge` | 활성 | AWS 공식 문서 조회. 이론 정리의 사실 검증 |
| `strands-agents` | 활성 | Strands Agents SDK 문서. API가 자주 바뀌어 정적 문서로 대체 불가 |
| `aws-agentcore` | **비활성** | 도구를 90개 이상 노출해 컨텍스트를 크게 점유합니다. `labs/agentcore-setup`을 작업할 때만 `disabled: false`로 바꿉니다 |

시크릿이 필요한 서버는 값이 아니라 환경변수 참조로 넣습니다.

보안 에이전트가 쓰는 스캐너 설치는
[`agents/security/docs/setup-sec-tools.md`](./agents/security/docs/setup-sec-tools.md)에 있습니다.

## 참고

- 각 실습·에이전트 폴더는 독립적으로 실행 가능하도록 자체 `README.md`와
  `requirements.txt`를 포함합니다.
- AWS 계정 자격 증명, 계정 ID, 리소스 ID(KB ID, 버킷명 등)는
  포함되어 있지 않습니다.
