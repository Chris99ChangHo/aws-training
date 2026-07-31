# 보안 표준과 이 리포의 구현

`agents/security` 에이전트에서 내린 설계 결정들이 어떤 업계 표준에 근거한
것인지 정리한 문서다. 실습 README는 "무엇을 왜 했는지"를 다루고, 이 문서는
"그 판단의 근거가 되는 표준이 무엇이고 어디에 쓰여 있는지"를 다룬다.

> 파일명이 원래 `devsecops-standards.md`였다. "DevSecOps"가 DevOps 쪽 문서로
> 읽혀서(실제로 그렇게 오해됐다) `security-standards.md`로 바꿨다.

모든 표준은 공식 문서를 조회해 확인했고 원문 링크를 달았다. 확인하지 못한
것은 그렇게 표시했다.

읽는 순서는 위에서 아래다. 1~3장은 용어, 4장이 핵심(표준 ↔ 코드 매핑),
5장은 표준이 아닌 내 판단을 구분해둔 것이다.

---

## 1. 보안 테스트의 세 가지 방식

실습에서 SAST / SCA / DAST를 약어로 계속 쓴다. 셋의 차이가 스코프 규칙과
권한 설계를 갈라놓기 때문에, 이걸 먼저 이해해야 나머지가 읽힌다.

| 방식 | 무엇을 보는가 | 대상을 실행하는가 | 이 실습의 도구 | 위험도 |
|---|---|---|---|---|
| **SAST**<br>Static Application Security Testing | 소스 코드 자체 | **아니오** | Semgrep | 낮음 (읽기만) |
| **SCA**<br>Software Composition Analysis | 서드파티 의존성·컨테이너 이미지 | 아니오 | Trivy | 낮음 |
| **DAST**<br>Dynamic Application Security Testing | **구동 중인** 애플리케이션 | **예 — 실제 요청을 보낸다** | Nuclei | **높음** |

세 번째가 근본적으로 다르다. SAST와 SCA는 파일을 읽는 행위이므로 최악의
경우 잘못된 결과가 나올 뿐이다. DAST는 **네트워크로 실제 공격성 요청을
보낸다.** 대상이 내 것이 아니면 그건 스캔이 아니라 침입이다.

그래서 이 실습에서 DAST만 별도의 권한 경계(`.sec-scope`)를 갖고, 두 지점에서
독립적으로 검증하며, 도구 자체가 `deny_commands`에 있어 사람 승인을
요구한다. SAST/SCA에는 그런 장치가 없다. **위험의 종류가 다르면 통제의
종류도 달라야 한다.**

> 참고: Nmap은 이 세 범주에 들어가지 않는다. 포트·서비스 정찰 도구이지
> 애플리케이션 취약점 스캐너가 아니다. 원래 요청은 Nmap을 DAST로 배치했는데
> 실습에서 Nuclei로 교체한 이유가 이것이다.

---

## 2. STRIDE — 위협을 빠뜨리지 않기 위한 체크리스트

**출처**: Loren Kohnfelder, Praerit Garg, "The Threats To Our Products",
Microsoft, 1999. 현재는 Microsoft Threat Modeling Tool 문서에서 각 범주의
정의를 볼 수 있다.
→ https://learn.microsoft.com/en-us/azure/security/develop/threat-modeling-tool-threats

여섯 글자의 머리글자다. 각 범주는 **깨지는 보안 속성 하나**에 대응한다.
이 대응이 STRIDE를 단순 목록이 아니라 도구로 만든다.

| 글자 | 위협 | 깨지는 속성 | 예 |
|---|---|---|---|
| **S** | Spoofing (신원 위조) | 인증 (Authentication) | 남의 토큰으로 API 호출 |
| **T** | Tampering (데이터 변조) | 무결성 (Integrity) | 요청 파라미터 조작 |
| **R** | Repudiation (부인) | 부인 방지 (Non-repudiation) | 로그가 없어 누가 했는지 증명 불가 |
| **I** | Information disclosure (정보 노출) | 기밀성 (Confidentiality) | 에러 메시지에 쿼리 노출 |
| **D** | Denial of service (서비스 거부) | 가용성 (Availability) | 무제한 파일 업로드 |
| **E** | Elevation of privilege (권한 상승) | 인가 (Authorization) | 일반 사용자가 관리자 기능 호출 |

**쓰는 방법**: 아키텍처를 데이터 흐름으로 그리고, **신뢰 경계를 넘는
지점마다** 여섯 범주를 하나씩 대본다. "이 지점에서 Spoofing이 가능한가?"
같은 식이다. 사람은 자기가 상상할 수 있는 공격만 떠올리므로, 체크리스트가
상상력의 편향을 보정한다.

### 이 실습에서 STRIDE를 다루는 방식

STRIDE 결과는 **도구가 검증해주지 않는다.** LLM의 추론 결과물이다.
스캐너가 `file:line`으로 확증한 취약점과 나란히 놓으면 독자가 구분할 수
없고, 그건 정직성 문제다.

그래서 `agent/SYSTEM_PROMPT.md`가 모든 주장에 마커를 강제한다.

| 마커 | 의미 | 근거 |
|---|---|---|
| `[TOOL-CONFIRMED]` | 스캐너가 찾았다 | 룰 ID + 파일 + 줄 번호 필수 |
| `[CODE-REVIEWED]` | 소스를 직접 읽었다 | `path:line` 인용 필수 |
| `[HYPOTHESIS]` | 추론이다 | STRIDE 위협은 기본적으로 여기 |

프롬프트에 이렇게 적어뒀다.

> A threat model with no tool backing is a list of questions to investigate,
> not a list of vulnerabilities.

---

## 3. 취약점을 표현하는 표준 3개 — 역할 분담

이름이 비슷해서 헷갈리는데, 서로 다른 질문에 답한다.

| 표준 | 답하는 질문 | 관리 주체 | 형태 |
|---|---|---|---|
| **CWE** | 이건 **어떤 종류**의 결함인가? | MITRE | 분류 번호 (`CWE-89`) |
| **CVSS** | **얼마나 심각**한가? | FIRST | 0.0~10.0 점수 |
| **SARIF** | 발견 사실을 **어떻게 주고받나**? | OASIS | JSON 스키마 |

CVE는 또 다르다. **특정 제품의 특정 취약점 하나**에 붙는 식별자다
(`CVE-2021-44228` = Log4Shell). CWE가 "SQL 인젝션이라는 결함 유형"이면
CVE는 "이 버전의 이 라이브러리에 있는 그 결함"이다.

### CVSS — 점수와 등급의 대응

**출처**: Common Vulnerability Scoring System v3.1 Specification Document,
FIRST, §5 "Qualitative Severity Rating Scale", Table 14.
→ https://www.first.org/cvss/v3.1/specification-document

원문 표를 그대로 옮기면:

| Rating | CVSS Score |
|---|---|
| None | 0.0 |
| Low | 0.1 – 3.9 |
| Medium | 4.0 – 6.9 |
| High | 7.0 – 8.9 |
| Critical | 9.0 – 10.0 |

`gate/gate.py`의 `bucket_from_score()`가 이 구간을 그대로 구현한다.
임의로 정한 숫자가 아니다.

```python
if score >= 9.0:  return "critical"
if score >= 7.0:  return "high"
if score >= 4.0:  return "medium"
if score >  0.0:  return "low"
return "info"
```

이 밴드를 쓰는 이유는 GitHub Code Scanning 등이 SARIF의
`properties.security-severity`를 같은 기준으로 해석하기 때문이다. 같은
숫자가 여기서와 저기서 다른 뜻이 되면 리포트를 옮길 수 없다.

> CVSS v4.0이 나와 있고 FIRST는 v3.1을 Archive로 분류한다. 이 실습이 v3
> 밴드를 쓰는 이유는 스캐너들이 SARIF에 넣는 `security-severity` 값이 아직
> v3 기준이기 때문이다. 스캐너가 v4로 옮기면 밴드도 같이 옮겨야 한다.

### SARIF — 스캐너를 갈아끼울 수 있게 만드는 것

**출처**: Static Analysis Results Interchange Format (SARIF) Version 2.1.0.
Edited by Michael C. Fanning and Laurence J. Golding. **27 March 2020.
OASIS Standard.**
→ https://docs.oasis-open.org/sarif/sarif/v2.1.0/os/sarif-v2.1.0-os.html

핵심 구조는 이렇다.

```
{
  "version": "2.1.0",
  "runs": [                      <- 도구 실행 하나당 원소 하나
    {
      "tool":    { "driver": { "name": "semgrep", "rules": [...] } },
      "results": [ ... ],        <- 발견 항목
      "invocations": [ { "executionSuccessful": true } ]
    }
  ]
}
```

**`runs`가 배열인 게 결정적이다.** 스캐너를 추가하는 일이 배열에 원소 하나
붙이는 일이 되고, 게이트에 새 출력 포맷을 가르치는 일이 아니다. 각 도구는
자기 룰 정의를 자기 `run` 안에 들고 있어서 변환이 필요 없다.

이게 "벤더 독립"이 구호가 아니라 구조가 되는 지점이다. `gate/merge_sarif.py`
전체가 하는 일은 여러 파일의 `runs`를 이어 붙이는 것뿐이다.

`invocations[].executionSuccessful`도 중요하다. **도구가 스스로 실패를
보고하는 자리**다. 이 필드를 무시하면 죽은 스캐너의 빈 결과를 "발견 없음"으로
읽는다. 실습에서 독립 감사가 정확히 이 결함을 찾아냈다.

---

## 4. 보안 설계 원칙 ↔ 이 실습의 코드

여기가 이 문서의 핵심이다. 원칙 이름만 아는 것과, 그 원칙이 코드에서 어떤
모양인지 아는 것은 다르다.

### 4.1 Fail-safe defaults (실패 시 안전한 기본값)

**출처**: Jerome H. Saltzer, Michael D. Schroeder, "The Protection of
Information in Computer Systems", 1975. 여덟 가지 설계 원칙 중 하나로 제시된
고전이다. 원문은 "base access decisions on permission rather than exclusion"
— 즉 **판단할 수 없으면 거부**한다.

OWASP도 같은 원칙을 "Fail Securely"로 정리한다.

**이 실습의 구현 4곳:**

| 위치 | 판단 불가 상황 | 동작 |
|---|---|---|
| `scanners/guard_scope.sh` | 훅 페이로드에서 명령을 못 찾음 | `exit 2` 차단 |
| `scanners/guard_scope.sh` | DAST 명령인데 타겟을 식별 못 함 | 차단 |
| `scanners/guard_scope.sh` | 타겟 목록이 **파일**로 주어짐 | 차단 (승인 시점에 내용 검증 불가) |
| `gate/gate.py` | 리포트가 없거나 손상됨 | `exit 4` (통과 아님) |

특히 세 번째가 원칙의 좋은 예다. `nuclei -l targets.txt`는 파일 내용을
검사한다 해도 검사 직후에 파일이 바뀔 수 있다(→ 4.4 TOCTOU). 검증했다고
말할 수 없으면 승인하지 않는다.

가드 코드의 주석에 이유를 남겼다.

> Failing closed on purpose: allowing an unread command would make this
> guard decorative.

### 4.2 Defense in depth (다층 방어)

한 층이 뚫려도 다음 층이 남게 만드는 것. 이 실습에서 실제로 작동한 사례가
있다.

MCP 서버의 인자 검증 정규식을 `^...$`로 썼는데, Python의 `$`는 문자열 끝
직전의 개행에도 매칭된다. 그래서 `"../../etc/passwd\n"`이 검증을 통과했다.

**그런데 차단은 됐다.** 스코프 계층이 잡아냈기 때문이다.

```
1층: MCP 인자 검증  → 통과 (버그)
2층: 스코프 검증    → 차단 ('..'는 허용 호스트가 아님)
```

버그는 고쳤지만(`\A...\Z`), 이 사건이 다층 방어의 값어치를 보여준다.
**층이 하나였다면 그대로 뚫렸다.**

이 실습의 층 구성:

```
1. 사람의 승인 프롬프트      DAST 도구는 전부 deny_commands → 매번 승인
2. PreToolUse 훅            쉘 경로의 명령 검증
3. 래퍼 자체의 스코프 검증   MCP 경로 (훅이 보지 못하는 경로)
4. MCP 서버의 인자 검증      argv 리스트 실행 + 문자 화이트리스트
5. 결정론적 게이트           통과/차단 판정
```

### 4.3 통제 지점은 둘, 규칙은 하나

**MCP 도구 호출은 PreToolUse 훅을 우회한다.** MCP 호출은 쉘 명령이 아니므로
훅이 보지 못한다. 스코프 검증이 훅에만 있었다면 에이전트가 쉘 대신 MCP를
쓰는 순간 통제가 사라진다.

그런데 두 곳에 규칙을 복사하면 시간이 지나며 갈라져서, 두 경로가 "무엇이
스코프 안인가"에 다른 답을 하게 된다. 그게 더 나쁘다.

해법: 규칙을 `scanners/_scope_lib.sh` 한 파일에 두고 두 곳에서 호출한다.

```
guard_scope.sh  ─┐
                 ├─→ _scope_lib.sh (normalise_host / load_scope / in_scope)
run_dast.sh     ─┘
```

일반화하면: **강제 지점의 개수는 진입 경로의 개수를 따라가고, 규칙의 개수는
항상 하나여야 한다.**

### 4.4 검증 시점과 실행 시점의 불일치

두 가지 형태로 겪었고, 둘 다 같은 원인이다.

**형태 1 — 쉘 확장**. `cat${IFS}/etc/shadow`는 가드에게는 토큰 하나,
쉘에게는 인자 두 개다(`$IFS`가 공백으로 확장된다). 가드가 읽는 문자열과
실행될 문자열이 다르면 어떤 검사도 무의미하다.

→ 그래서 `$`와 `{}`를 **전면 금지**했다. 특정 패턴을 잡는 게 아니라
**확장되는 텍스트 자체를 거부**하는 게 유일하게 건전한 규칙이다.

**형태 2 — TOCTOU** (Time-of-Check to Time-of-Use). 검사와 사용 사이에
대상이 바뀌는 경쟁 조건. 심링크 대상 교체, 타겟 목록 파일 수정 등.
CWE-367로 분류된다.

→ 타겟 목록 파일을 거부하는 이유가 이것이다. 실습에서 완전히 해결하지는
못했고 README §14에 잔여 위험으로 남겼다.

### 4.5 거부 목록은 원리상 불완전하다

가드는 **거부 목록**(denylist) 방식이다. 알려진 위험을 열거해 막는다.
허용 목록(allowlist)이 원칙적으로는 더 안전하지만, 보안 분석 에이전트가
탐색을 위해 어떤 명령을 쓸지 미리 다 열거할 수 없어서 이 실습은 거부
목록을 택했다.

그 대가를 정직하게 적어야 한다. 거부 목록은 **목록에 없는 것을 놓친다.**

독립 감사가 이걸 실증했다. 내 목록은 "위험한 바이너리 이름"을 막았지만,
`perl -e '...'`의 위험은 `perl`이 아니라 **인용부호 안의 스크립트**에 있고
가드는 그 안을 읽지 못한다. 놓친 원칙이 이것이다.

> 차단 목록이 검사할 수 없는 텍스트를 실행하는 도구는, 그 자체로 차단
> 대상이다.

그래서 인터프리터 계열(`eval`, `sh -c`, `python3 -c`, `xargs`, `env` 등)을
통째로 막았다. 그래도 목록 밖의 인터프리터는 남는다 → README §14.

---

## 5. NIST SSDF 매핑

**출처**: NIST SP 800-218, "Secure Software Development Framework (SSDF)
Version 1.1: Recommendations for Mitigating the Risk of Software
Vulnerabilities", 2022.
→ https://csrc.nist.gov/pubs/sp/800/218/final

미국 행정명령 14028의 후속으로 나온 문서라 정부 조달에서 실질적 기준으로
쓰인다. 네 그룹으로 나뉜다.

| 그룹 | 뜻 | 이 실습의 해당 부분 |
|---|---|---|
| **PO** Prepare the Organization | 조직 준비 | 해당 없음 (개인 실습) |
| **PS** Protect the Software | 산출물 보호 | `.gitignore`로 SARIF 리포트 제외 |
| **PW** Produce Well-Secured Software | 안전한 소프트웨어 생산 | 위협 모델링, SAST/SCA, 코드 리뷰 |
| **RV** Respond to Vulnerabilities | 취약점 대응 | 게이트, 리포트 |

> SP 800-218 Rev.1(SSDF v1.2)은 현재 초안 단계다. 개별 practice ID
> (`PW.7.1` 등)는 버전 간에 바뀔 수 있어 이 문서에서는 그룹 수준까지만
> 매핑했다. 정확한 ID가 필요하면 원문을 확인해야 한다.

---

## 6. 표준 ↔ 구현 변환표

한 눈에 보기 위한 요약이다. 줄 번호는 코드가 바뀌면 틀리므로 파일과 함수
이름으로 적었다.

| 표준 / 원칙 | 출처 | 이 실습의 구현 |
|---|---|---|
| STRIDE 6범주 | Kohnfelder & Garg, MS 1999 | `agent/SYSTEM_PROMPT.md` — finding 필수 형식의 `STRIDE:` 필드 |
| 증거와 추론의 분리 | (표준 아님, §5 참조) | `[TOOL-CONFIRMED]` / `[CODE-REVIEWED]` / `[HYPOTHESIS]` 마커 |
| SARIF 2.1.0 `runs` 배열 | OASIS Standard 2020-03-27 | `gate/merge_sarif.py` — `load_runs()` |
| SARIF `executionSuccessful` | 같음 | `gate/gate.py` — `validate_report()` |
| CVSS v3.1 정성 등급 | FIRST v3.1 §5 Table 14 | `gate/gate.py` — `bucket_from_score()` |
| CWE 분류 | MITRE | 픽스처 SARIF의 `properties.tags` (`CWE-78`, `CWE-79`, `CWE-798`) |
| CWE-367 (TOCTOU) | MITRE | 타겟 목록 파일 거부 (`guard_scope.sh`) |
| Fail-safe defaults | Saltzer & Schroeder 1975 | 훅 파싱 실패 시 차단, 게이트 리포트 없으면 `exit 4` |
| Defense in depth | 통용 원칙 | 5개 층 (§4.2) |
| Least privilege | Saltzer & Schroeder 1975 | `manifest.toml` `[capabilities]` — `fetch_web = false` |
| 권한 있는 대상만 테스트 | 법적 요구 (정보통신망법 등) | `.sec-scope` + 두 지점 강제 |
| NIST SSDF RV (취약점 대응) | NIST SP 800-218 | `gate/gate.py` 결정론적 게이트 |
| MCP (개방 프로토콜) | Model Context Protocol 명세 | `mcp/server.py` |
| JSON-RPC 2.0 | jsonrpc.org 명세 | `mcp/server.py` — `handle()` |

---

## 7. 표준이 아닌 것 — 내 판단인 부분

표준으로 뒷받침되지 않는 결정을 표준인 것처럼 적으면 이 문서 전체가
신뢰를 잃는다. 아래는 판단이다.

| 결정 | 근거 유형 |
|---|---|
| 증거 마커 3종 체계 | 표준 없음. 이 리포의 `ai-attribution.md` 규약을 에이전트 출력에 적용한 것 |
| 종료 코드 규약 (0/2/3/4) | 표준 없음. "도구 미설치와 발견 없음을 구분해야 한다"는 요구에서 도출 |
| 거부 목록의 구체적 항목 | 관행 기반. 완전성 보장 없음 |
| `.sec-scope` 와일드카드 미지원 | 판단. 편의보다 안전을 택함 |
| 기본 임계값 `fail_on_severity = "high"` | 판단. 조직마다 다르게 정해야 하는 값 |
| 스캐너 바이너리는 고정, 피드는 고정 안 함 | 판단. 재현성과 최신성의 트레이드오프 |

특히 마지막이 설명이 필요하다. 스티어링 규약은 "의존성 버전을 고정하라"고
하는데, 취약점 DB는 고정하면 안 된다. **어제 없던 CVE가 오늘 나온다.** 낡은
DB로 통과한 빌드는 통과가 아니다. 반대로 스캐너 바이너리가 올라가며
severity 매핑이 바뀌면 코드를 안 건드렸는데 게이트 결과가 달라진다.
그래서 도구는 고정하고 데이터는 고정하지 않는다.

---

## 8. 원문 링크

| 표준 | URL |
|---|---|
| SARIF 2.1.0 (OASIS Standard) | https://docs.oasis-open.org/sarif/sarif/v2.1.0/os/sarif-v2.1.0-os.html |
| CVSS v3.1 명세 | https://www.first.org/cvss/v3.1/specification-document |
| CVSS v4.0 명세 | https://www.first.org/cvss/v4.0/specification-document |
| CWE (MITRE) | https://cwe.mitre.org/ |
| NIST SP 800-218 (SSDF v1.1) | https://csrc.nist.gov/pubs/sp/800/218/final |
| STRIDE 범주 정의 (Microsoft) | https://learn.microsoft.com/en-us/azure/security/develop/threat-modeling-tool-threats |
| OWASP Top 10 | https://owasp.org/www-project-top-ten/ |
| OWASP ASVS | https://owasp.org/www-project-application-security-verification-standard/ |
| Model Context Protocol | https://modelcontextprotocol.io/ |
| JSON-RPC 2.0 | https://www.jsonrpc.org/specification |

## 다음에 볼 것

- 실습 자체: [`../security/`](../security)
- 설계 결정과 트러블슈팅 14건:
  [`../security/README.md`](../security/README.md)
- 스캐너 설치:
  [`../security/docs/setup-sec-tools.md`](../security/docs/setup-sec-tools.md)
