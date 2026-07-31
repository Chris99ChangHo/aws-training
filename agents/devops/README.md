# Generic DevOps Agent

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)
![PyYAML](https://img.shields.io/badge/PyYAML-6.0.3-informational)
![SARIF](https://img.shields.io/badge/SARIF-2.1.0_(OASIS)-informational)
![Terraform](https://img.shields.io/badge/Terraform-plan_only-844FBA?logo=terraform&logoColor=white)
![Kubernetes](https://img.shields.io/badge/Kubernetes-read_only-326CE5?logo=kubernetes&logoColor=white)
![Tests](https://img.shields.io/badge/tests-83-brightgreen)

AWS DevOps Agent를 해체해서, 특정 클라우드 벤더에도 특정 AI 도구(하네스)에도
종속되지 않게 재구현한 것이다. 계열의 두 번째 에이전트이며,
[`agents/security/`](../security)에서 검증한 3층 설계를 그대로 쓴다.

**이 에이전트를 한 문장으로**: 인프라 정의가 **배포·운영 가능한지**를 검사해
SARIF로 내고, LLM 없이 결정론적으로 판정한다. 그리고 **인프라 상태를 절대
바꾸지 않는다.**

## 보안 에이전트와 무엇이 다른가

이 경계는 추측이 아니라 실측으로 정했다. 초기 버전은 `run_iac.sh`가
`trivy config`를 호출했는데, 같은 픽스처에서 보안 에이전트의 `run_sca.sh`와
**rule ID 13개가 전부 동일**했다(security 전용 0건, devops 전용 0건). 보안
에이전트가 이미 `trivy fs --scanners vuln,secret,misconfig`를 돌고 있었기
때문이다. 두 에이전트가 같은 발견을 내는 것은 커버리지가 아니라 소유권 혼란이다.

| | 묻는 질문 | rule 네임스페이스 |
|---|---|---|
| security | 이게 **취약한가** | `AWS-*` `KSV-*` `DS-*` (Trivy), Semgrep, `CVE-*` |
| **devops** | 이게 **배포·운영 가능한가** | `OPS-*` (자체 체커) |

Trivy가 이미 잡는 것은 검사하지 않는다. 실측 결과 Trivy는 리소스
limits/requests(`KSV-0011/15/16/18`), 이미지 태그(`KSV-0013`), Dockerfile
`HEALTHCHECK`(`DS-0026`), 모든 `securityContext`를 보고한다. 반면 아래 8개는
어떤 보안 스캐너도 보고하지 않는다.

| rule | 검사 | 운영상 무슨 일이 생기는가 | 등급 |
|---|---|---|---|
| `OPS-0001` | `required_version` 없음 | 다른 CLI 버전이 같은 코드를 다르게 plan | medium |
| `OPS-0002` | provider 버전 제약 없음 | 나중 실행이 다른 provider를 받아 다른 plan | medium |
| `OPS-0003` | 원격 backend 없음 | state가 로컬·락 없음 → 동시 apply가 state 손상, 호스트와 함께 소실 | **high** |
| `OPS-0010` | probe 없음 | 준비 안 된 프로세스로 트래픽 전송 | **high** |
| `OPS-0011` | 단일 replica | 단일 장애점, 무중단 업데이트 불가 | medium |
| `OPS-0012` | 업데이트 전략 미선언 | 롤아웃·롤백이 클러스터 기본값에 좌우됨 | low |
| `OPS-0020` | `timeout-minutes` 없음 | 멈춘 스텝이 러너를 플랫폼 최대치까지 점유 | low |
| `OPS-0021` | `uses`가 SHA 미고정 | 같은 워크플로가 나중에 다른 코드를 실행 | medium |

등급은 SARIF 표준 level(`error`/`warning`/`note`)로만 표현한다. 공유 게이트가
그걸 high/medium/low로 매핑하므로, 보안 발견이 아닌 것에 `security-severity`
같은 필드를 지어 넣지 않는다.

## 핵심 통제: plan은 되고 apply는 안 된다

security 에이전트와 위협 모델이 다르다. 그쪽은 시크릿을 읽거나 승인 안 된
호스트를 스캔하는 것이 위험이다. 이쪽은 **오타 하나가 운영 클러스터를
지우는 것**이 위험이다.

그래서 `scanners/guard_infra.sh`가 상태 변경 명령을 전부 거부한다.

| 도구 | 허용 |
|---|---|
| `terraform` / `tofu` / `terragrunt` | `validate` `plan` `show` `providers` `fmt` `graph` `output` `init` |
| `kubectl` / `oc` | `get` `describe` `logs` `explain` `diff` `top` `version` |
| `helm` | `template` `lint` `show` `list` `get` `version` |
| `docker` / `podman` | `build` `images` `ps` `inspect` `history` |
| `aws` / `gcloud` / `az` | `describe-*` `get-*` `list-*` `ls` `show` `head` `validate` |

허용 목록으로 짠 이유는 **변경 동사가 열린 집합**이기 때문이다. 새 서브커맨드가
생겨도 기본이 차단이다. deny 목록이면 새 동사마다 구멍이 열린다.

`terraform plan -destroy`도 막는다. 쓰는 것은 없지만 파괴 계획을 만들고 이후
`apply`가 그걸 소비하므로, 승인된 동사를 통해 파괴 의도가 세탁된다.

`terraform.tfstate`, `*.tfvars`, `kubeconfig`는 자격증명으로 취급한다.
state 파일에는 평문 시크릿이 들어간다. **정의는 읽고 상태는 읽지 않는다.**

## 아키텍처

```
agent/                        중립 소스 (손으로 쓰는 유일한 곳)
  manifest.toml                 능력·허용/거부·게이트 임계값
  SYSTEM_PROMPT.md              역할·증거 마커·보고 형식
        │
        ├─ (Tier 1) 어댑터 생성  ← 미구현. 아래 "검증하지 못한 것" 참고
        │
scanners/                     래퍼: 종료 코드를 정규화하고 SARIF를 남긴다
  guard_infra.sh                PreToolUse 훅. 상태 변경 거부 (exit 2)
  preflight.sh                  도구·파서 존재 보고
  run_operability.sh            운영 준비도 → SARIF (OPS-* rule)
  operability_check.py            체커 본체. Terraform은 표준 라이브러리로,
                                  K8s·Actions는 PyYAML 필요
  run_pipeline.sh               hadolint + actionlint → SARIF
  actionlint_to_sarif.py        actionlint는 SARIF를 못 내므로 변환
        │
        ▼
agents/core/gate/             (Tier 3) 공유 게이트 — LLM 없음
  merge_sarif.py                여러 SARIF를 하나로
  gate.py                       severity 임계값으로 판정 (exit 0/1)
```

게이트는 security 에이전트와 **같은 코드**다. 두 번째 소비자가 생긴 시점에
`agents/core/`로 추출했다(계열 원칙 3: 소비자가 2개일 때 추상화한다).

## 실행 방법

### AI 없이 쓰기

K8s·GitHub Actions 검사는 YAML 파서가 필요하다. Python 표준 라이브러리에는
YAML 파서가 없어서 격리 환경에 설치한다. Terraform 검사와 공유 게이트는
설치 없이 동작한다.

```bash
cd agents/devops

python3 -m venv .venv                          # 최초 1회
.venv/bin/pip install -r requirements.txt

sh      scanners/preflight.sh                  # 도구·파서 존재 확인
sh      scanners/run_operability.sh <path>     # 운영 준비도 (OPS-*)
sh      scanners/run_pipeline.sh <path>        # Dockerfile + CI 워크플로
python3 ../core/gate/merge_sarif.py            # 병합
python3 ../core/gate/gate.py --fail-on high    # 판정 (exit 0=통과, 1=차단)
```

래퍼는 `.venv/bin/python3`가 있으면 자동으로 그것을 쓴다. 없으면 시스템
`python3`로 돌고, YAML 파일이 있는데 파서가 없으면 **exit 3**으로
"검사하지 않았다"를 보고한다. 0을 반환하지 않는 것이 요점이다.

`cd`하지 않고 리포 루트에서 돌리려면 `AGENT_ROOT`를 넘긴다. 공유 게이트는
자기 위치로 어느 에이전트를 위해 도는지 알 수 없어서 밖에서 받는다.

```bash
AGENT_ROOT=$PWD/agents/devops python3 agents/core/gate/gate.py
```

### 종료 코드

| 코드 | 뜻 |
|---|---|
| 0 | 실행 완료, 문제 없음 |
| 1 | 게이트 실패: 차단 대상 발견이 예산 초과 |
| 2 | 거부: 상태 변경 명령을 요청했다 |
| 3 | **린터 미설치** |
| 4 | 린터 자체가 실패 |

3을 0과 섞지 않는 것이 이 설계의 요점이다. 도구가 없는 상태를 "깨끗함"으로
보고하면 게이트가 빈 리포트를 통과시킨다.

### 테스트

린터가 하나도 없어도 통제 로직 전체가 검증된다.

```bash
sh      tests/test_guard_infra.sh          # 상태 변경 차단 56 케이스
python3 tests/test_pipeline.py             # 래퍼 계약 + SARIF 변환 8 케이스
.venv/bin/python3 tests/test_operability.py  # OPS-* 체커 19 케이스
python3 tests/test_operability.py            # 같은 파일, 파서 없는 경로를 덮는다
```

`test_operability.py`는 두 인터프리터로 돌린다. PyYAML이 있는 쪽은 K8s·Actions
검사를, 없는 쪽은 "YAML 미검사 → exit 3" 계약을 검증한다. 한쪽만 돌리면 각각
2개·6개가 skip으로 남는다.

## 검증 결과

`tests/fixtures/`(의도적으로 운영 통제를 뺀 Terraform·K8s·워크플로)를 대상으로
종단 실행했다.

```
sh scanners/run_operability.sh tests/fixtures
  → 8건 [terraform 2 file, yaml 2 doc]
     warning OPS-0001 iac/versions.tf:7      required_version 없음
     error   OPS-0003 iac/versions.tf:7      원격 backend 없음
     warning OPS-0002 iac/versions.tf:14     provider: random (버전 제약 없음)
     error   OPS-0010 k8s/deployment.yaml    Deployment/web container web
     warning OPS-0011 k8s/deployment.yaml    replicas=1
     note    OPS-0012 k8s/deployment.yaml    전략 미선언
     note    OPS-0020 workflows/...ci.yml    job: build
     warning OPS-0021 workflows/...ci.yml    actions/checkout@v4

python3 ../core/gate/merge_sarif.py
  → operability.sarif: 1 run, 8 result

python3 ../core/gate/gate.py
  → Devops gate, threshold high / budget 0
  → high 2, medium 4, low 2
  → blocking 2: OPS-0003 iac/versions.tf:7, OPS-0010 k8s/deployment.yaml:1
  → verdict FAIL, exit 1
```

발동하지 **않아야** 할 것이 발동하지 않는 것도 확인했다 — 버전 제약이 있는
`aws` provider, `timeout-minutes`가 있는 `lint` 잡, SHA로 고정된 action,
`./local-action`, 그리고 replicas·전략이 개념상 없는 CronJob.

| 항목 | 상태 |
|---|---|
| 운영 준비도 검사 → SARIF → 병합 → 판정 종단 | 확인 (위 실측) |
| 보안 에이전트와 rule 네임스페이스 분리 | 확인 (`OPS-*`만, `AWS-*`/`KSV-*`/`DS-*`/`CVE-*` 0건) |
| Trivy가 이미 잡는 항목을 재검사하지 않음 | 확인 (K8s·Dockerfile 픽스처로 Trivy 출력 실측 후 제외) |
| 공유 게이트가 devops manifest 임계값을 읽음 | 확인 (`Devops gate`, threshold high) |
| 통제가 있으면 발동하지 않음 (거짓 양성) | 확인 (19 케이스 중 5개가 이 방향) |
| 상태 변경 차단 56 케이스 | 확인 |
| 변이 검증: 가드 허용목록에 `apply` 추가 → 4건 실패 | 확인 |
| 변이 검증: OPS-0003 항상 발동 → 2건 실패 / SHA 핀 인식 제거 → 1건 실패 | 확인 |
| YAML 파서 없을 때 exit 3 (0이 아님) | 확인 |
| 린터 미설치가 exit 3 | 확인 |

## 검증하지 못한 것

정직하게 남긴다. "됐다"만 적힌 문서는 근거가 없다.

| 항목 | 이유 |
|---|---|
| **하네스 어댑터 3종 생성 (Tier 1)** | 미구현. `adapters/build.py`가 security 전용이다. 프로젝트 단위 파일(`.claude/settings.json`, `.codex/config.toml`)을 에이전트별로 생성하면 서로 덮어쓰므로 생성기가 에이전트 단위 출력과 프로젝트 단위 출력을 갈라야 한다. Codex는 프로파일(`~/.codex/<name>.config.toml` + `--profile`)로 분리 가능함을 확인했다 |
| `hadolint` 종단 | 로컬 미설치. 미설치 경로(exit 3)만 검증됨 |
| `actionlint` 종단 | 로컬 미설치. 변환기는 합성 입력으로 검증됨 |
| MCP 서버 | 미구현 (Tier 2). manifest에 이름만 선언돼 있다 |
| 실제 프로젝트 대상 스캔 | 이 리포에 IaC·파이프라인 파일이 0건이라 픽스처로만 검증 |
| **HCL 파싱의 한계** | Terraform 검사는 정규식 + 중괄호 카운팅이다. `terraform` 블록·`required_providers`처럼 최상위 선언에는 안전하지만, 중첩·표현식을 이해해야 하는 검사는 시도하지 않았다. 실제 HCL 파서가 필요해지면 그때 도입한다 |
| 릴리스 준비도 판정 | 프롬프트에 항목으로만 있다. 결정론적 검사가 아니라 LLM 독해다 |

## AWS 원본과의 차이

| AWS DevOps Agent 기능 | 이쪽 | 비고 |
|---|---|---|
| IaC 검토 | 부분 | Trivy config + LLM 독해. 조직 정책 팩 없음 |
| 파이프라인 검토 | 부분 | hadolint/actionlint. GitHub Actions 외 CI는 미지원 |
| 배포 실행·롤백 | **없음** | 의도적이다. 이 에이전트는 apply하지 않는다 |
| 관측성·인시던트 대응 | 없음 | 런타임 텔레메트리 연동 없음 |
| 플랫폼 연동 (PR 코멘트, 자동 수정 PR) | 없음 | SARIF 형식 호환까지 |
| LLM 없는 결정론적 게이트 | **원본에 없는 것** | 벤더 독립이 목표라 "구독 끊겨도 CI가 돈다"가 요구사항이 됐다 |

## 비용

클라우드 리소스 0원. 전부 로컬 실행이다. 운영 준비도 검사는 네트워크를 쓰지
않고(PyYAML 설치만 1회), 게이트와 검사에는 LLM 토큰이 들지 않는다.
`hadolint`·`actionlint`를 설치하면 그 바이너리 다운로드 비용만 있다.

## 관련

- **경계**: [`../docs/agent-boundaries.md`](../docs/agent-boundaries.md) — 어떤 검사가 어느 에이전트의 일인지, 겹쳤던 실측 기록
- 도구 설치: [`docs/setup-devops-tools.md`](./docs/setup-devops-tools.md)
- 계열 공통 설계 원칙: [`../README.md`](../README.md)
- 코드 작성 시 적용되는 규칙: `.kiro/skills/agent-conventions/SKILL.md`
- 첫 번째 에이전트: [`../security/`](../security)
