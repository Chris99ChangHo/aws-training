# 로컬 환경 관리 — 무엇을 왜 깔고, 어떻게 지우는가

이 에이전트는 스캐너를 직접 구현하지 않고 외부 도구를 호출한다. 그래서 로컬에
프로그램이 깔린다. 무엇이 왜 필요하고 어떻게 되돌리는지 정리했다.

설치 명령 자체는 [`setup-sec-tools.md`](./setup-sec-tools.md)에 있다. 이 문서는
**판단 근거와 되돌리는 방법**을 다룬다.

---

## 1. 용도별로 왜 필요한가

도구마다 **보는 대상이 다르다.** 하나로 안 되는 이유가 이것이다.

| 도구 | 무엇을 보는가 | 없으면 못 하는 일 | 대상을 실행하나 |
|---|---|---|---|
| `python3` | — | **전부.** 게이트·MCP 서버 런타임 | — |
| `jq` | — | PreToolUse 훅이 명령을 파싱 못 함 → 전부 차단(fail-closed) | — |
| `semgrep` | **내가 쓴 소스 코드** | SAST. 하드코딩된 비밀번호, 인젝션 패턴 | 아니오 (읽기만) |
| `trivy` | **의존성·시크릿·IaC 설정** | SCA. 쓰고 있는 라이브러리의 알려진 CVE | 아니오 (읽기만) |
| `nuclei` | **구동 중인 웹 서비스** | DAST. 실제 요청을 보내 취약점 확인 | **예 (네트워크 요청)** |

### 왜 셋을 다 필요로 하는가

같은 취약점을 세 도구가 각각 못 본다.

```
내 코드에 SQL 인젝션이 있다
  → semgrep 이 잡는다.  trivy 는 못 본다(내 코드를 분석하지 않음)

쓰는 라이브러리에 CVE가 있다
  → trivy 가 잡는다.    semgrep 은 못 본다(라이브러리 내부를 안 봄)

인증 우회가 실제로 되는지
  → nuclei 만 확인 가능. 정적 분석으로는 알 수 없음
```

이 리포를 실제로 스캔했을 때 나온 결과가 그 예다.

| 도구 | 발견 |
|---|---|
| semgrep | **0건** — 이 리포의 파이썬/쉘 코드에 패턴 위반 없음 |
| trivy | **12건** — `mcp`, `brace-expansion`, `streamlit` 패키지의 CVE |

semgrep만 돌렸으면 "깨끗하다"는 결론이 나왔을 것이다. 실제로는 의존성에
12건이 있었다.

### nuclei를 따로 취급하는 이유

앞의 둘은 **파일을 읽는 행위**다. 최악의 경우 잘못된 결과가 나온다.
nuclei는 **네트워크로 공격성 요청을 보낸다.** 대상이 내 것이 아니면 스캔이
아니라 침입이고, 대부분의 관할권에서 위법이다.

만든 쪽(ProjectDiscovery)도 자기 도구를 이렇게 소개한다.

> ProjectDiscovery is widely known for its open-source **red-team toolkit**
> (Nuclei, Subfinder, and more)

"red-team"은 공격하는 쪽을 뜻한다. 그래서:

| 상황 | 판단 |
|---|---|
| 개인 컴퓨터 | 문제 없음 |
| **회사 지급 노트북** | **사전 확인 필요** — 백신·EDR이 탐지·격리할 수 있고, 승인 없는 침투테스트 도구 설치는 정책 위반일 수 있다 |
| 보안회사 업무용 | 정상 도구. 정식 승인받고 사용 |

이 실습은 **nuclei 없이도 DAST 통제 로직 전체가 검증된다.** `run_dast.sh`가
스코프 검증을 도구 존재 확인보다 앞에 두기 때문이다.

```
$ sh scanners/run_dast.sh https://example.com   ; echo $?
[dast] REFUSED: 'example.com' is not in the authorised scope.
2                                    ← nuclei 없이도 거부 동작 확인됨
```

---

## 2. 실제로 설치된 것 (실측)

`brew install semgrep trivy` 한 번으로 들어온 것이다.

| 항목 | 값 |
|---|---|
| 주 패키지 | `semgrep 1.172.0`, `trivy 0.72.0` |
| semgrep 의존성 | 11개 — certifi, pycparser, cffi, cryptography, dwarfutils, gmp, libev, pcre2, pydantic, rpds-py, tree-sitter |
| trivy 의존성 | **0개** (단일 Go 바이너리) |
| 이미 있어서 안 깔린 것 | python@3.14, sqlite, zstd |
| **총 추가 패키지** | **13개** |

용량:

| 대상 | 용량 |
|---|---|
| semgrep | 224 MB |
| trivy | 195 MB |
| 의존성 11개 합계 | 92 MB |
| **합계** | **약 511 MB** |
| Homebrew 전체 | 1.5 GB → 2.0 GB |

추가로 캐시가 생긴다.

| 캐시 | 위치 | 내용 |
|---|---|---|
| Trivy 취약점 DB | `~/Library/Caches/trivy` | 첫 실행 시 다운로드 |
| Semgrep 룰 캐시 | `~/.semgrep` | 레지스트리 룰셋 |
| Nuclei 템플릿 | `~/.config/nuclei` (설치했다면) | 템플릿 저장소 |

### 시스템에 남기지 않는 것 (실측 확인)

| 항목 | 확인 결과 |
|---|---|
| 백그라운드 데몬 | **없음** — `brew services list`에 아무것도 등록되지 않음 |
| 자동 실행 | **없음** — `~/Library/LaunchAgents`에 항목 없음 |
| 시스템 설정 변경 | 없음 |
| 로그인 항목 | 없음 |

셋 다 **실행할 때만 동작하고 끝나면 사라지는** 일반 CLI 도구다.

---

## 3. 지우는 방법

### 3-1. 도구만 지우기 (가장 흔한 경우)

```bash
brew uninstall semgrep trivy
```

nuclei도 깔았다면:

```bash
brew uninstall nuclei
```

의존성 11개는 남는다. 다른 패키지가 쓸 수도 있으므로 brew가 자동으로 지우지
않는다. 아무도 안 쓰는 의존성을 정리하려면:

```bash
brew autoremove --dry-run   # 무엇이 지워질지 먼저 확인
brew autoremove             # 실제 삭제
```

**`--dry-run`을 먼저 돌릴 것.** 다른 도구가 쓰던 라이브러리가 목록에 있으면
멈추고 확인해야 한다.

### 3-2. 캐시까지 지우기

도구를 지워도 캐시는 남는다. 용량이 크므로 같이 지우려면:

```bash
rm -rf ~/Library/Caches/trivy      # Trivy 취약점 DB
rm -rf ~/.semgrep                  # Semgrep 룰 캐시
rm -rf ~/.config/nuclei            # Nuclei 템플릿 (설치했다면)
```

지워도 다음 실행 때 다시 내려받는다. 되돌릴 수 없는 손실은 없다.

### 3-3. 이 실습이 만든 파일 지우기

```bash
rm -rf agents/security/reports/    # SARIF 리포트
```

리포트에는 절대 경로, 코드 스니펫, 스캐너가 탐지한 시크릿 값이 담긴다.
`.gitignore`로 제외되어 있지만 로컬에서도 필요 없으면 지우는 게 좋다.

### 3-4. 에이전트 설정까지 되돌리기

```bash
rm -f .kiro/agents/generic-sec-agent.json
rm -f .claude/agents/generic-sec-agent.md
rm -f .codex/config.toml .codex/generic-sec-agent.md
```

`.claude/settings.json`은 다른 설정이 섞여 있을 수 있으니 **눈으로 보고**
해당 부분만 지운다. 전부 생성물이므로
`python3 agents/security/adapters/build.py`로 언제든 되살릴 수 있다.

### 3-5. 설치 전 상태와 대조하기

설치 전에 스냅샷을 남겨두면 정확히 무엇이 추가됐는지 대조할 수 있다.
다음에 새 도구를 깔 때 권장하는 방법이다.

```bash
# 설치 전
brew list --formula > ~/brew_before.txt

# 설치 후
brew list --formula > ~/brew_after.txt
diff ~/brew_before.txt ~/brew_after.txt
```

이번 설치에서 이 방법으로 추가 패키지 13개를 확인했다.

---

## 4. 외부 통신 통제

셋 다 네트워크를 쓴다. 무엇을 위해 쓰는지와 끄는 방법이다.

| 도구 | 통신 목적 | 통제 방법 | 래퍼 적용 여부 |
|---|---|---|---|
| semgrep | 레지스트리 룰 다운로드 | `SEC_SAST_CONFIG`로 로컬 룰 지정 | 선택 |
| semgrep | **사용 통계 전송 (기본 ON)** | `--metrics=off` | **적용됨** |
| trivy | 취약점 DB 다운로드 (첫 실행) | 캐시 후 오프라인 가능 | — |
| nuclei | 템플릿 다운로드 | 캐시 후 오프라인 가능 | — |
| nuclei | **매 실행 버전 확인** | `-duc` | **적용됨** |

Semgrep 공식 문서 기준, `--metrics auto`가 기본값이고 **레지스트리에서 룰을
가져올 때 통계가 전송된다.** 래퍼는 항상 `--metrics=off`를 넣는다.

완전 오프라인으로 돌리려면:

```bash
SEC_SAST_CONFIG=agents/security/scanners/rules \
  sh agents/security/scanners/run_sast.sh src
```

---

## 5. 라이선스 요약

| 도구 | 라이선스 | 제약 |
|---|---|---|
| Trivy | Apache-2.0 | 없음 (Aqua 크레딧 표기) |
| Semgrep CE 엔진 | LGPL-2.1-only | 없음 |
| **Semgrep 레지스트리 룰** | Semgrep Rules License v1.0 | **내부 사용만.** 제품·SaaS 판매 불가 |
| Nuclei | 오픈소스 | 없음 |

상세는 [`setup-sec-tools.md`](./setup-sec-tools.md)의 라이선스 절 참고.

---

## 관련 문서

- [스캐너 설치 명령](./setup-sec-tools.md)
- [실습 본문](../README.md)
- [표준과 개념](../../docs/devsecops-standards.md)
