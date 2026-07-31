# AgentCore Runtime 배포와 엔드포인트 버전 관리

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![AWS](https://img.shields.io/badge/AWS-Bedrock_AgentCore-01A88D)
![Strands Agents](https://img.shields.io/badge/Strands_Agents-1.x-4B32C3)
![boto3](https://img.shields.io/badge/boto3-agentcore--control-232F3E)

Amazon Bedrock AgentCore Runtime에 에이전트를 배포하고, **엔드포인트를 특정
버전에 고정해서 카나리 → 승격 → 롤백**을 돌려 보는 랩입니다.

배포 자체보다 **배포 이후의 운영**에 초점이 있습니다. AgentCore는 업데이트할
때마다 새 불변 버전을 만들고, 엔드포인트가 어느 버전을 가리키는지는 별도로
관리합니다. 그 분리가 무엇을 가능하게 하는지 확인하는 것이 목적입니다.

## 사용 기술

| 기술 | 용도 |
|---|---|
| AgentCore CLI (`agentcore`) | 프로젝트 생성, 로컬 실행, CDK로 배포 |
| `bedrock-agentcore-control` (boto3) | 버전·엔드포인트 조회와 조작 |
| `bedrock-agentcore` (boto3) | 배포된 엔드포인트 호출 |
| Strands Agents | 배포 대상 에이전트 본체 (`app/`) |

## 아키텍처

```
agentcore deploy
      │
      ▼
┌─────────────────────────────────────────────┐
│ AgentCore Runtime  (RestaurantAgent)        │
│                                             │
│   버전 1 (불변)   버전 2 (불변)   버전 3     │  ← 업데이트마다 새 버전
└─────────────────────────────────────────────┘
      ▲                    ▲              ▲
      │                    │              │
  ┌───┴────────┐    ┌──────┴─────┐   ┌────┴─────┐
  │ production │    │  DEFAULT   │   │  canary  │  ← 엔드포인트가 버전을 가리킨다
  │ (버전 고정) │    │ (최신 추종) │   │ (검증용)  │
  └────────────┘    └────────────┘   └──────────┘
```

핵심은 **버전과 엔드포인트가 분리돼 있다**는 것입니다.

- `DEFAULT` 엔드포인트는 업데이트하면 자동으로 최신 버전을 가리킵니다.
- 직접 만든 엔드포인트는 **지정한 버전에 고정**됩니다. 재배포해도 움직이지
  않습니다.
- 그래서 `production`을 고정해 두고 `canary`로 새 버전을 먼저 받아 보는
  구성이 가능합니다. 승격은 엔드포인트가 가리키는 버전을 바꾸는 것이고,
  롤백은 그것을 되돌리는 것입니다. **재배포가 아닙니다.**

## 구성

```
labs/agentcore-setup/
├── agentcore/               AgentCore CLI 프로젝트 설정
│   ├── agentcore.json         에이전트·메모리·게이트웨이 등 리소스 선언
│   ├── aws-targets.json       배포 대상(계정·리전)
│   ├── .env.local             시크릿 (gitignored)
│   └── cdk/                   생성된 CDK 인프라
├── app/                     에이전트 애플리케이션 코드
└── ops/                     이 랩의 본문 — 배포 이후 운영
    ├── 01_list_versions.py    버전·엔드포인트 목록 조회
    ├── 02_create_endpoint.py  production 엔드포인트를 특정 버전에 고정 생성
    ├── 03_invoke_endpoint.py  canary 생성 후 엔드포인트별 호출 비교
    ├── 04_promote.py          검증 통과 시 production을 새 버전으로 승격
    └── 05_rollback.py         장애 시 이전 버전으로 되돌리기
```

## 실행 방법

### 0. 사전 준비

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

`agentcore` CLI(Node.js 20+)와 AWS 자격 증명이 필요합니다. 리전은
`us-west-2`입니다.

### 1. 배포

```bash
agentcore deploy
```

### 2. RUNTIME_ID 설정 — 이 랩에서 가장 많이 막히는 지점

`ops/` 스크립트는 전부 `RUNTIME_ID` 환경변수를 요구합니다. 아래 명령으로
설정하세요(한 줄).

```bash
export RUNTIME_ID=$(aws bedrock-agentcore-control list-agent-runtimes \
  --region us-west-2 --output text \
  --query "agentRuntimes[?agentRuntimeName=='RestaurantAgent_RestaurantAgent'].agentRuntimeId | [0]")
```

이름이 `RestaurantAgent`가 아니라 **`RestaurantAgent_RestaurantAgent`**입니다.
이유는 아래 트러블슈팅에 있습니다.

### 3. 운영 시나리오

```bash
python3 ops/01_list_versions.py     # 현재 버전·엔드포인트 확인
python3 ops/02_create_endpoint.py   # production을 안정 버전에 고정
python3 ops/03_invoke_endpoint.py   # canary 생성 후 응답 비교
python3 ops/04_promote.py           # production 승격
python3 ops/05_rollback.py          # 되돌리기
```

각 스크립트 상단의 버전 상수(`STABLE_VERSION`, `CANARY_VERSION`,
`NEW_VERSION`, `PREVIOUS_VERSION`)는 `01_list_versions.py` 결과에 맞춰
조정합니다.

## 설계 결정과 트러블슈팅

이 랩은 Kiro CLI와 함께 진행했습니다. 아래는 AI 에이전트가 실행한 도구
결과(에러 메시지, API 응답)를 근거로 정리했으며, 어떤 해결 방향을 택할지는
사람이 검토·승인한 내용입니다.

### 1. `AccessDeniedException`이 실제로는 이름 불일치였다

`RestaurantAgent`로 런타임을 조회하면 매칭이 실패합니다. AgentCore CLI가
런타임 이름을 **`<프로젝트명>_<런타임명>`** 형식으로 붙이기 때문에 실제
이름은 `RestaurantAgent_RestaurantAgent`입니다.

문제는 실패 방식입니다. `--query`가 매칭에 실패하면 AWS CLI는 빈 값이 아니라
**문자열 `"None"`**을 출력합니다. 그것이 `RUNTIME_ID`에 들어가고, 존재하지
않는 ID로 API를 호출하면 "없음"이 아니라 **`AccessDeniedException`**이
돌아옵니다. 권한 문제로 오인해서 IAM 정책을 뒤지게 됩니다.

→ 스크립트가 `RUNTIME_ID`를 검사할 때 `None`과 빈 문자열을 **둘 다** 거부하고,
올바른 조회 명령을 출력하도록 했습니다. 값이 없는 것과 문자열 `"None"`이 들어온
것을 구분하지 않으면 이 함정을 그대로 물려줍니다.

```python
RUNTIME_ID = os.environ.get("RUNTIME_ID")
if RUNTIME_ID is None or RUNTIME_ID in ("", "None"):
    raise SystemExit("RUNTIME_ID 환경변수가 필요합니다. ...")
```

`[해석]` 이 부류의 오류는 **존재하지 않는 리소스에 대한 권한을 확인할 수 없기
때문에** 생깁니다. AWS가 "그 리소스는 없다"고 답하면 리소스 존재 여부가
유출되므로, 권한 오류로 응답하는 것이 일반적인 설계입니다. 즉 이건 버그가
아니라 **AccessDenied를 "권한 문제"로만 읽으면 안 된다**는 뜻입니다.

### 2. 엔드포인트를 버전에 고정하지 않으면 롤백 대상이 사라진다

`DEFAULT` 엔드포인트만 쓰면 재배포할 때마다 그것이 최신 버전을 가리킵니다.
문제가 생겼을 때 되돌릴 지점이 남지 않습니다.

→ `production` 엔드포인트를 만들어 안정 버전에 고정하고, 새 버전은 `canary`로
먼저 받습니다. 승격·롤백이 **엔드포인트가 가리키는 버전을 바꾸는 것**이 되므로
재배포가 필요 없고, 되돌리는 시간이 배포 시간과 무관해집니다.

### 3. README가 CLI 보일러플레이트였다

이 파일의 이전 버전은 `agentcore create`가 생성한 CLI 일반 설명서였습니다.
프로젝트 구조와 명령어 목록은 있었지만 **이 랩이 무엇을 했는지는 없었습니다.**
생성된 문서를 그대로 두면 리포의 다른 실습과 형식이 어긋나고, 읽는 사람이
"이 폴더에서 무엇을 배웠는가"를 알 수 없습니다.

→ 랩 README 표준(기술 배지·아키텍처·설계 결정·실행 방법·검증·비용)으로 다시
썼습니다. CLI 자체 사용법은 [공식 리포](https://github.com/aws/agentcore-cli)로
링크합니다 — 상류에서 바뀌는 내용을 복사해 두면 낡습니다.

## 검증 결과

| 항목 | 상태 |
|---|---|
| `agentcore deploy`로 Runtime 배포 | 확인 |
| 버전·엔드포인트 목록 조회 (`01`) | 확인 |
| production 엔드포인트를 특정 버전에 고정 생성 (`02`) | 확인 |
| canary 엔드포인트 생성과 엔드포인트별 호출 비교 (`03`) | 확인 |
| production 승격 (`04`) | 확인 |
| 이전 버전으로 롤백 (`05`) | 확인 |
| `RUNTIME_ID` 미설정·`"None"` 입력 시 안내 메시지로 중단 | 확인 |

**확인하지 못한 것**: 실제 장애 상황(오류율 상승)을 트리거해서 롤백까지 자동으로
가는 파이프라인은 만들지 않았습니다. 승격·롤백은 사람이 스크립트를 실행하는
수동 절차입니다.

## 비용

**상시 과금됩니다.** 배포된 AgentCore Runtime은 세션이 없어도 리소스가 유지되고,
엔드포인트를 여러 개(`production`, `canary`, `DEFAULT`) 만들면 그만큼 늘어납니다.
`labs/` 안에서 상시 과금이 있는 랩은 이것뿐입니다.

랩이 끝나면 정리하세요.

```bash
agentcore status     # 배포된 리소스 확인
```

엔드포인트를 먼저 지우고 런타임을 지웁니다(`DEFAULT`는 런타임과 함께 사라집니다).
현재 단가는 [Bedrock AgentCore 요금](https://aws.amazon.com/bedrock/agentcore/)에서
확인하세요.

## 참고

- [AgentCore CLI](https://github.com/aws/agentcore-cli) — 프로젝트 생성·배포 명령
- [AgentCore CDK Constructs](https://github.com/aws/agentcore-l3-cdk-constructs)
- [Amazon Bedrock AgentCore](https://aws.amazon.com/bedrock/agentcore/)
- 이 랩을 작업할 때는 `aws-agentcore` MCP 서버를 켜세요. 기본은 비활성입니다
  (도구를 90개 이상 노출해 컨텍스트를 크게 점유합니다). 루트
  [`README.md`](../../README.md)의 "도구 체인" 절 참고.
