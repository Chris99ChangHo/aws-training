# Generic DevOps Agent

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)
![Dependencies](https://img.shields.io/badge/runtime_deps-none-brightgreen)
![SARIF](https://img.shields.io/badge/SARIF-2.1.0_(OASIS)-informational)
![Trivy](https://img.shields.io/badge/Trivy-IaC_misconfig-1904DA?logo=trivy&logoColor=white)
![Terraform](https://img.shields.io/badge/Terraform-plan_only-844FBA?logo=terraform&logoColor=white)
![Kubernetes](https://img.shields.io/badge/Kubernetes-read_only-326CE5?logo=kubernetes&logoColor=white)
![Tests](https://img.shields.io/badge/tests-64-brightgreen)

AWS DevOps Agent를 해체해서, 특정 클라우드 벤더에도 특정 AI 도구(하네스)에도
종속되지 않게 재구현한 것이다. 계열의 두 번째 에이전트이며,
[`agents/security/`](../security)에서 검증한 3층 설계를 그대로 쓴다.

**이 에이전트를 한 문장으로**: IaC·컨테이너·파이프라인을 오픈소스 린터로
검사해 SARIF로 내고, LLM 없이 결정론적으로 배포 가능 여부를 판정한다.
그리고 **인프라 상태를 절대 바꾸지 않는다.**

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
  preflight.sh                  린터 존재 보고
  run_iac.sh                    Trivy config → SARIF
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

```bash
cd agents/devops

sh      scanners/preflight.sh                  # 린터 존재 확인
sh      scanners/run_iac.sh <path>             # IaC 오설정
sh      scanners/run_pipeline.sh <path>        # Dockerfile + CI 워크플로
python3 ../core/gate/merge_sarif.py            # 병합
python3 ../core/gate/gate.py --fail-on high    # 판정 (exit 0=통과, 1=차단)
```

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
sh      tests/test_guard_infra.sh   # 상태 변경 차단 56 케이스
python3 tests/test_pipeline.py      # 래퍼 계약 + SARIF 변환 8 케이스
```

## 검증 결과

`tests/fixtures/iac/main.tf`(의도적 오설정)를 대상으로 종단 실행했다.

```
sh scanners/run_iac.sh tests/fixtures/iac
  → 14건  (critical 1, high 7, medium 1, low 5)

python3 ../core/gate/merge_sarif.py
  → trivy-config.sarif: 1 run, 14 result

python3 ../core/gate/gate.py
  → threshold high / budget 0
  → blocking 8:  AWS-0086 main.tf:7 (high)   AWS-0104 main.tf:32 (critical)
                 AWS-0107 main.tf:25 (high)  ...
  → verdict FAIL, exit 1
```

| 항목 | 상태 |
|---|---|
| IaC 스캔 → SARIF → 병합 → 판정 종단 | 확인 (위 실측) |
| 공유 게이트가 devops manifest 임계값을 읽음 | 확인 (`Devops gate`, threshold high) |
| 상태 변경 차단 56 케이스 | 확인 |
| 변이 검증: terraform 허용목록에 `apply` 추가 시 4건 실패 | 확인 |
| 린터 미설치가 exit 3 (0이 아님) | 확인 |
| SARIF 변환: 정상·빈 입력·깨진 입력 | 확인 (8 케이스) |

## 검증하지 못한 것

정직하게 남긴다. "됐다"만 적힌 문서는 근거가 없다.

| 항목 | 이유 |
|---|---|
| **하네스 어댑터 3종 생성 (Tier 1)** | 미구현. `adapters/build.py`가 security 전용이고, 일반화하려 하자 실제 제약이 드러났다 — `.claude/settings.json`과 `.codex/config.toml`은 **프로젝트 단위** 파일이라 에이전트별로 생성하면 두 에이전트가 서로 덮어쓴다. 에이전트 단위 파일(Kiro json, Claude 서브에이전트 md, Codex 프롬프트 md)과 프로젝트 단위 파일을 생성기에서 분리해야 한다 |
| `hadolint` 종단 | 로컬 미설치. 미설치 경로(exit 3)만 검증됨 |
| `actionlint` 종단 | 로컬 미설치. 변환기는 합성 입력으로 검증됨 |
| MCP 서버 | 미구현 (Tier 2). manifest에 이름만 선언돼 있다 |
| 실제 프로젝트 대상 스캔 | 이 리포에 IaC·파이프라인 파일이 0건이라 픽스처로만 검증 |
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

클라우드 리소스 0원. 전부 로컬 실행이다. Trivy가 첫 실행 시 체크 DB를
내려받는 네트워크 비용만 있다. 게이트와 스캔에는 LLM 토큰이 들지 않는다.

## 관련

- 계열 공통 설계 원칙: [`../README.md`](../README.md)
- 코드 작성 시 적용되는 규칙: `.kiro/skills/agent-conventions/SKILL.md`
- 첫 번째 에이전트: [`../security/`](../security)
