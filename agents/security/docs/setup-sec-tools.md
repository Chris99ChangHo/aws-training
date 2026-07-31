# 보안 스캐너 설치

이 에이전트는 스캐너를 직접 구현하지 않고 오픈소스 도구를 호출한다.
아래 도구가 없으면 해당 래퍼는 **exit 3**으로 끝난다. exit 0(스캔 완료)과
구분되므로, 도구가 없는 상태가 "취약점 없음"으로 보고되는 일은 없다.

설치 상태는 언제든 확인할 수 있다:

```bash
sh agents/security/scanners/preflight.sh
```

## 필수

| 도구 | 역할 | 없으면 |
|---|---|---|
| `python3` (3.11+) | 게이트·MCP 서버 런타임 | 전부 동작 불가 |
| `jq` | PreToolUse 훅의 페이로드 파싱 | 훅이 fail-closed로 전부 차단 |

`python3`는 3.11 이상이 필요하다. `tomllib`이 3.11부터 표준 라이브러리에
들어왔고, manifest 파싱에 쓴다.

```bash
# macOS
brew install jq

# Debian/Ubuntu
sudo apt-get update && sudo apt-get install -y jq

# RHEL/Fedora
sudo dnf install -y jq
```

## 선택 (없으면 해당 스캔만 불가)

### Semgrep — SAST

```bash
# macOS
brew install semgrep

# 어디서나 (pipx 권장: 전역 파이썬 환경을 건드리지 않는다)
pipx install semgrep==1.155.0

# pip
python3 -m pip install --user semgrep==1.155.0
```

기본 룰셋은 `p/security-audit`, `p/secrets`, `p/owasp-top-ten`으로 고정되어
있다. `--config auto`는 쓰지 않는다 — 실행마다 네트워크로 룰을 해석해서
결과가 재현되지 않고, 프로젝트 메타데이터가 벤더 서비스로 전송된다.

**텔레메트리**: Semgrep은 레지스트리 룰을 가져올 때 기본으로 사용 통계를
전송한다(`--metrics auto`가 기본값). 래퍼는 `--metrics=off`를 항상 넣는다.

### 라이선스 주의 — Semgrep만 조건이 있다

| 구성 요소 | 라이선스 | 제약 |
|---|---|---|
| Semgrep CE 엔진 | LGPL 2.1 | 없음 |
| **Semgrep 레지스트리 룰** | **Semgrep Rules License v1.0** | **내부 사용만** |
| Trivy | Apache 2.0 | 없음 (Aqua 크레딧 표기) |
| Nuclei | 오픈소스 | 없음 |

Semgrep 공식 문서 원문:

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
| 제품·SaaS로 판매 | **아니오** |

즉 **엔진은 오픈소스지만 룰은 벤더 라이선스에 묶여 있다.** 이 실습이 내세우는
"벤더 독립"에서 가장 근본적으로 남아 있는 종속이다. 상업 배포가 목표라면
아래 오프라인 방식으로 자체 룰만 쓰거나, 완전 자유 라이선스 룰셋을 찾아야
한다.

완전 오프라인으로 돌리려면 로컬 룰 디렉토리를 지정한다. 레지스트리를 아예
쓰지 않으므로 위 제약과 텔레메트리 둘 다 사라진다.

```bash
SEC_SAST_CONFIG=./agents/security/scanners/rules \
  sh agents/security/scanners/run_sast.sh src
```

### Trivy — SCA / IaC / 시크릿

```bash
# macOS
brew install trivy

# Debian/Ubuntu (공식 apt 저장소)
sudo apt-get install -y wget gnupg
wget -qO - https://aquasecurity.github.io/trivy-repo/deb/public.key \
  | gpg --dearmor | sudo tee /usr/share/keyrings/trivy.gpg > /dev/null
echo "deb [signed-by=/usr/share/keyrings/trivy.gpg] \
https://aquasecurity.github.io/trivy-repo/deb generic main" \
  | sudo tee /etc/apt/sources.list.d/trivy.list
sudo apt-get update && sudo apt-get install -y trivy
```

**첫 실행은 네트워크가 필요하다.** Trivy는 취약점 DB를 내려받아 캐시한다.
이후 실행은 캐시로 동작한다.

컨테이너 이미지를 스캔할 때, 로컬에 빌드된 이미지를 대상으로 하려면 Docker가
필요하다. 레지스트리에 있는 이미지 참조(`nginx:1.27` 등)는 Docker 없이도
스캔된다.

### Nuclei — DAST

```bash
# macOS
brew install nuclei

# Go 툴체인이 있으면
go install -v github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest

# 바이너리 릴리스
# https://github.com/projectdiscovery/nuclei/releases
```

첫 실행 시 템플릿을 내려받는다.

**Nuclei는 능동 스캔 도구다.** 권한 없는 호스트를 스캔하는 것은 대부분의
관할권에서 위법이다. 이 실습의 래퍼와 훅은 `.sec-scope`에 명시된 호스트만
허용하고, 기본값은 `localhost`, `127.0.0.1`, `::1`뿐이다. 에이전트는 이
파일을 수정하지 않도록 프롬프트로 지시되어 있고, 쓰기 거부 경로에도
포함되어 있다. 스코프를 넓히는 것은 사람이 소유권을 확인한 뒤에만 한다.

## 버전 고정에 대해

스캐너 **바이너리 버전은 고정하고, 취약점 피드는 고정하지 않는다.**

- 바이너리를 고정하는 이유: 도구가 업그레이드되면서 룰 판정이나 severity
  매핑이 바뀌면, 코드를 안 건드렸는데 게이트 결과가 달라진다. CI 게이트는
  같은 입력에 같은 판정을 내려야 한다.
- 피드를 고정하지 않는 이유: 어제 없던 CVE가 오늘 나온다. 낡은 DB로 통과한
  빌드는 통과가 아니다.

## 설치하지 않고 확인할 수 있는 것

스캐너가 하나도 없어도 아래는 전부 동작한다. 설계상 스캐너와 통제 로직이
분리되어 있기 때문이다.

```bash
cd agents/security

sh   tests/test_guard_scope.sh      # PreToolUse 훅 차단 로직 91 케이스
python3 tests/test_gate.py          # SARIF 병합 + 게이트 + 무결성 34 케이스
python3 tests/test_mcp_server.py    # MCP 프로토콜 + 인자 검증 19 케이스
```

## nuclei 설치 후 확인 (DAST)

```bash
brew install nuclei
nuclei -update-templates      # 래퍼는 -duc로 업데이트 체크를 끄므로 미리 받아야 한다
```

실측: v3.11.0, 템플릿 13,391개.

`.sec-scope`가 기본으로 `localhost`·`127.0.0.1`·`::1`을 허용하므로, 스캔 대상은
로컬에 직접 띄우면 됩니다. 검증 대상을 만드는 최소 방법:

```bash
mkdir -p /tmp/dast-target/.git
printf '[core]\n\trepositoryformatversion = 0\n' > /tmp/dast-target/.git/config
cd /tmp/dast-target && python3 -m http.server 8099 --bind 127.0.0.1
```

다른 터미널에서:

```bash
cd agents/security
sh      scanners/run_dast.sh http://127.0.0.1:8099   # git-config를 medium으로 탐지
python3 gate/merge_sarif.py
python3 gate/gate.py --fail-on medium                # exit 1 (차단)
```

**nuclei의 두 가지 관례를 알아두세요.** 둘 다 래퍼가 흡수합니다.

| 상황 | nuclei 동작 | 래퍼 대응 |
|---|---|---|
| 발견 없음 | SARIF 파일을 **아예 쓰지 않는다** | `write_empty_sarif`로 형식이 유효한 빈 리포트를 남긴다 |
| 발견 있음 | `executionSuccessful: false`를 쓴다 (완료된 스캔인데도) | `scanners/normalize_sarif.py`가 `true`로 정규화한다 |

정규화가 없으면 **깨끗한 스캔은 통과하고 발견이 있는 스캔은 게이트가 exit 4로
거부**합니다. 경위는 README §23에 있습니다.
