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
| [`agents/security/`](./agents/security) | AWS Security Agent | 동작 (테스트 173) | STRIDE 위협 모델링, SAST/SCA/DAST, SARIF 결정론적 CI 게이트. Kiro CLI / Claude Code / Codex CLI 어댑터를 단일 프롬프트에서 생성 |

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

## 참고

- 각 실습·에이전트 폴더는 독립적으로 실행 가능하도록 자체 `README.md`와
  `requirements.txt`를 포함합니다.
- AWS 계정 자격 증명, 계정 ID, 리소스 ID(KB ID, 버킷명 등)는
  포함되어 있지 않습니다.
