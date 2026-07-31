# 리포 구조 규약

AWS 오프라인 교육 과정별 실습·이론 정리와, 그 과정에서 파생된 에이전트
작업물을 모아두는 모노레포다.

**성격이 다른 두 축이 있다.**

| 축 | 위치 | 성격 |
|---|---|---|
| 과정 | `<과정명>/` | 학습 기록. 시간순·과정별. 내용이 AWS에 종속돼도 무방 |
| 에이전트 | `agents/` | 작업물. 재사용 가능한 계열. **정의상 벤더 독립** |

두 번째를 첫 번째 안에 넣지 않는다. 벤더 독립이 목표인 산출물이 특정 벤더
과정 폴더에 들어가면 계속 어긋나고, 어댑터가 워크스페이스 루트(`.kiro/`,
`.claude/`, `.codex/`)에 생성되므로 과정 폴더에 담기지도 않는다.

## 디렉토리 구조

```
aws-training/
├── README.md                      두 축(과정/에이전트) 목록
├── .gitignore                      민감 정보·산출물 제외 규칙
├── .kiro/steering/                 이 규칙 파일들
├── .kiro/ .claude/ .codex/         생성된 에이전트 어댑터 (직접 수정 금지)
│
├── agents/                         벤더 독립 에이전트 계열
│   ├── README.md                   계열 개요·공통 설계 원칙·이음새 표
│   ├── docs/                       계열 공통 문서 (표준, 포팅 가이드)
│   ├── core/                       에이전트 간 공유 코드
│   └── <도메인>/                    에이전트 하나당 폴더 하나 (security, devops...)
│
└── <과정명>/
    ├── README.md                   과정 내 실습 목록
    ├── notes/                      이론 정리 (.md)
    └── <실습명>/                    실습 하나당 폴더 하나
        ├── README.md               실습 개요·실행법·검증 결과
        ├── requirements.txt        이 실습 전용 의존성
        └── (스크립트, 데이터)
```

과정 폴더는 kebab-case 영문으로 짓는다
(`generative-ai-essentials`, `security-engineering`,
`developing-genai-apps`, `devops-engineering`).

## agents/ 규칙

- 폴더명은 **도메인 한 단어**로 짧게 짓는다(`security`, `devops`). 이 경로가
  생성되는 모든 어댑터 설정에 문자열로 박히므로 길면 손해다. 폴더명과
  에이전트 이름(`generic-sec-agent`)은 별개다.
- 경로를 코드에 절대 경로로 쓰지 않는다. 파일 위치에서 계산한다
  (`LAB_ROOT.relative_to(WORKSPACE_ROOT)`). 폴더를 옮겨도 재생성만 하면
  어댑터가 자동으로 맞고, 홈 디렉토리·사용자명이 커밋되지 않는다.
- **공유 코드 추출은 실제 소비자가 2개 이상일 때만 한다.** 첫 에이전트만 있는
  상태에서 `core/`의 경계를 정하면 틀린 경계를 코드로 굳힌다. 그때까지는
  `agents/README.md`의 이음새 표에 후보만 기록한다.

  근거: `agents/security`에서 하네스가 2개일 때는 추상화가 잘 된 줄 알았으나
  3번째를 붙이자 보안 구멍(파일 읽기 도구가 훅을 우회)이 드러났다.
- 계열 공통 설계 원칙은 `agents/README.md`에 모으고, 개별 에이전트 README는
  자기 트러블슈팅만 담는다.

## 실습 폴더 규칙

- **독립 실행 가능해야 한다.** 자체 `README.md`와 `requirements.txt`를 갖고,
  다른 실습 폴더를 참조하지 않는다.
- 스크립트는 실행 순서를 파일명 앞 숫자로 표현한다
  (`01_`, `02_`...). 인프라 구축 단계와 실험 단계를 구분해야 하면
  구축 쪽에 접두어를 붙인다(`setup_01_`, `setup_02_`).
- 각 스크립트는 완료 기준을 자체 검증하고 종료 코드로 성공/실패를 알린다.

## 실습 README에 담을 것

단순 실행법만 적지 않고 아래를 함께 남긴다. 이 리포는 학습 기록이자
포트폴리오이므로, **판단 근거가 결과보다 중요하다.**

1. 사용 기술 목록 — [shields.io](https://shields.io/badges/static-badge) 정적 배지로 표시.
   제목 바로 아래, 첫 문단 위에 둔다.
   ```markdown
   ![AWS](https://img.shields.io/badge/AWS-Bedrock-orange?logo=amazonaws&logoColor=white)
   ![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python&logoColor=white)
   ![Strands Agents](https://img.shields.io/badge/Strands_Agents-1.x-4B32C3)
   ```
   로고는 [simple-icons](https://simpleicons.org/) slug를 쓴다(`logo=` 값).
   대상 없는 도구는 로고 없이 라벨-메시지-색상만 넣는다.
2. 아키텍처 (텍스트 다이어그램으로 충분)
3. **설계 결정과 트러블슈팅** — 겪은 문제, 원인 분석 과정, 해결 방법.
   "됐다/안 됐다"가 아니라 왜 그런 결과가 나왔는지 근거를 남긴다.
4. 실행 방법
5. 검증 결과 (수치·비교표)
6. 비용 주의사항 (상시 과금되는 리소스가 있으면 명시)

## 이론 정리

- `<과정명>/notes/` 아래에 마크다운으로 둔다.
- 파일명은 주제 기반 kebab-case (`rag-fundamentals.md`).

## 과정을 추가할 때

1. 과정 폴더와 `notes/` 생성
2. 과정 `README.md` 작성 (실습 목록 표)
3. 최상위 `README.md`의 과정 목록 표에 한 줄 추가
