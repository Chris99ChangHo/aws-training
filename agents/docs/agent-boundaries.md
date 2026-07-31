# 에이전트 경계 — 무엇이 어느 에이전트의 일인가

계열에 에이전트가 둘이 되자마자 겹쳤다. 이 문서는 **어떻게 겹쳤는지**와
**다음에 겹치지 않게 하는 절차**를 남긴다.

## 실제로 일어난 일

devops 에이전트의 첫 IaC 계층은 `run_iac.sh`가 `trivy config`를 호출했다.
같은 픽스처(`agents/devops/tests/fixtures/iac`)에 두 에이전트를 돌려 rule ID를
대조한 결과:

| | 결과 수 | 고유 rule | 상대 대비 전용 |
|---|---|---|---|
| security `run_sca.sh` | 14 | 13 | **0** |
| devops `run_iac.sh` | 14 | 13 | **0** |

차이가 0이었다. 원인은 security의 SCA 래퍼가 이미
`trivy fs --scanners vuln,secret,misconfig`를 돌고 있었다는 것이다.
`misconfig`가 `trivy config`와 같은 검사다.

**왜 놓쳤는가**: "IaC 스캔은 devops의 일"이라는 도메인 직관으로 경계를 그었다.
파일 종류(`.tf`, `.yaml`)로 소유권을 나눈 것이다. 그런데 보안 스캐너도 같은
파일을 읽는다. 파일은 경계가 아니다.

## 경계는 파일이 아니라 질문이다

| 에이전트 | 묻는 질문 | rule 네임스페이스 |
|---|---|---|
| `security/` | 이게 **취약한가** — 공격자가 무엇을 할 수 있는가 | `AWS-*` `KSV-*` `DS-*` (Trivy), Semgrep rule, `CVE-*` |
| `devops/` | 이게 **배포·운영 가능한가** — 배포·장애·롤백 때 무슨 일이 생기는가 | `OPS-*` |

같은 `deployment.yaml`을 둘 다 읽는다. 갈리는 것은 무엇을 보고하는가다.

```
deployment.yaml
├── securityContext 없음, 권한 상승 허용, 신뢰 못 하는 레지스트리
│     → security  (KSV-0001, KSV-0012, KSV-0125 ...)
├── 리소스 limits 없음, 이미지 태그 없음
│     → security  (KSV-0011/15/16/18, KSV-0013)   ← Trivy가 이미 본다
└── readinessProbe 없음, replicas 1, 업데이트 전략 없음
      → devops    (OPS-0010, OPS-0011, OPS-0012)  ← 아무도 안 본다
```

가운데 줄이 함정이다. "리소스 한계 없음"은 운영 문제처럼 들리지만 Trivy가
이미 보고한다. 직관으로는 이걸 알 수 없다.

## 새 검사를 추가할 때의 절차

새 에이전트를 만들거나 기존 에이전트에 검사를 추가할 때 **순서대로** 한다.

### 1. 기존 에이전트를 같은 대상에 먼저 돌린다

추측하지 않는다. 픽스처를 만들고 기존 스캐너를 실제로 돌려 출력을 본다.

```sh
SEC_REPORT_DIR=/tmp/probe sh agents/security/scanners/run_sca.sh <픽스처>
```

### 2. rule ID와 메시지를 뽑아 목록으로 만든다

"비슷한 걸 보는 것 같다"가 아니라 어느 rule이 무엇을 말하는지 본다. 이
단계에서 Dockerfile `HEALTHCHECK`가 이미 `DS-0026`으로 보고된다는 것,
Terraform `required_version`은 아무도 보지 않는다는 것이 드러났다.

### 3. 이미 보고되는 항목은 새 에이전트에서 **뺀다**

같은 것을 두 번 보고하지 않는다. 필요하면 다른 에이전트를 가리킨다.
`SYSTEM_PROMPT.md`에 그렇게 쓴다 — devops 프롬프트에는 이렇게 있다.

> You do not scan for vulnerabilities, misconfiguration or secrets. The security
> agent owns those... If a reviewer needs that, say so and point at the security
> agent rather than producing a second copy of its findings.

### 4. rule 네임스페이스를 분리하고 테스트로 단정한다

접두어를 겹치지 않게 정하고, **테스트가 그것을 지키는지 검사**한다.
`agents/devops/tests/test_operability.py`의
`TestNoOverlapWithSecurityAgent`가 이 역할이다 — `OPS-` 접두어만 나오고
`AWS-` `KSV-` `DS-` `CVE-`는 0건임을 단정한다. 이 테스트가 있어야 나중에
누가 편의상 Trivy를 다시 끌어와도 CI에서 걸린다.

### 5. 겹침이 불가피하면 소유자를 문서에 적는다

같은 검사가 두 도메인에 정말로 필요한 경우가 있을 수 있다. 그때는 한쪽을
소유자로 정하고 다른 쪽은 참조만 한다. 양쪽이 다 보고하는 상태로 두지 않는다.

## 공유되는 것 — 겹침이 아니라 공유다

| 대상 | 위치 | 왜 공유인가 |
|---|---|---|
| SARIF 2.1.0 계약 | `agents/docs/security-standards.md` §3 | 게이트가 읽는 형식. 도구를 추가해도 게이트를 안 고치려면 하나여야 한다 |
| 결정론적 게이트 | `agents/core/gate/` | 판정 로직은 도메인과 무관하다. 임계값만 각 에이전트 manifest에서 온다 |
| 종료 코드 계약 0/1/2/3/4 | `.kiro/skills/agent-conventions/SKILL.md` | 호출자가 계약을 두 개 배우게 하지 않는다 |

구분: **같은 발견을 두 번 내는 것**은 중복이고, **같은 형식·같은 판정기를
쓰는 것**은 공유다. 앞의 것만 없앤다.

## 아직 갈리지 않은 것

| 대상 | 상태 |
|---|---|
| `scanners/_lib.sh` | devops가 사본을 갖고 있다. 공유하려면 `SEC_REPORT_DIR`을 중립 이름으로 개명해야 하고 5개 파일 8곳에 있다 |
| `guard_scope.sh` §1–3 (페이로드 파싱·자격증명·구조 금지) | devops `guard_infra.sh`에 사본이 있다. 원본이 100개 행동 테스트를 지고 있어 별도 작업으로 뒀다 |
| `adapters/build.py` | security 전용. 에이전트 단위 출력과 프로젝트 단위 출력을 갈라야 공유 가능하다 |

이 세 개는 **코드 중복**이고 위에서 다룬 **발견 중복**과 다른 문제다. 코드
중복은 유지보수 비용이고, 발견 중복은 사용자를 혼란시킨다. 후자를 먼저 없앴다.
