# DevOps 에이전트 도구 설치

`scanners/preflight.sh`가 MISSING으로 보고한 것만 설치하면 된다. 하나도
설치하지 않아도 **통제 로직과 Terraform 검사는 전부 동작한다** — 도구가 없는
상태는 exit 3(“검사하지 않았다”)으로 보고되고 0으로 위장되지 않는다.

| 대상 | 필요 시점 | 없으면 |
|---|---|---|
| PyYAML | K8s 매니페스트·GitHub Actions 검사 | 그 파일들이 미검사로 남고 래퍼가 **exit 3** |
| hadolint | Dockerfile 검사 | 해당 검사가 “실행되지 않음” 표시된 빈 SARIF |
| actionlint | 워크플로 문법 검사 | 같음 |
| jq | **PreToolUse 가드** | 가드가 페이로드를 못 읽어 **모든 명령을 차단**한다 (fail closed) |

## PyYAML — 격리 환경에 넣는다

Python 표준 라이브러리에는 TOML 파서는 있지만 YAML 파서가 없다. macOS의
Homebrew Python은 PEP 668로 전역 설치가 막혀 있으므로 에이전트 폴더 안에
가상환경을 만든다. 래퍼는 `.venv/bin/python3`가 있으면 자동으로 그것을 쓴다.

```bash
cd agents/devops
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

`.venv/`는 `.gitignore` 대상이라 커밋되지 않는다. 버전은
`requirements.txt`에 `==`로 고정돼 있다.

**중첩 YAML을 줄 단위로 훑지 않는 이유**: `resources:`나 `readinessProbe:`를
grep으로 찾으면 다른 부모 밑에 있는 같은 이름 키에 걸려 거짓 양성이 난다.
리뷰어는 그것을 실제 발견과 구분할 수 없다. 그래서 제대로 파싱하거나
"검사하지 않았다"고 보고한다.

## jq — 가드의 전제

가드는 하네스가 stdin으로 보내는 JSON에서 명령을 꺼내야 판단할 수 있다. jq가
없으면 파싱이 불가능하므로 **닫히는 쪽으로 실패한다** — 검증되지 않은 명령은
허용되지 않는다.

```bash
brew install jq          # macOS
sudo apt install jq      # Debian/Ubuntu
```

이 동작은 의도된 것이다. 파싱 못 하는 명령을 통과시키면 가드가 있다는 사실이
거짓 안심이 된다.

## hadolint — Dockerfile

```bash
brew install hadolint
```

다른 플랫폼은 [공식 리포](https://github.com/hadolint/hadolint)의 릴리스
바이너리를 쓴다. 라이선스 GPL-3.0.

## actionlint — GitHub Actions

```bash
brew install actionlint
```

또는 [공식 리포](https://github.com/rhysd/actionlint)의 릴리스 바이너리.
라이선스 MIT.

actionlint는 SARIF를 내지 못해서 `scanners/actionlint_to_sarif.py`가 JSON을
변환한다. 게이트가 형식 중립을 유지하려면 도구를 추가하는 일이 게이트 수정으로
번지지 않아야 한다.

## 설치하지 않는 것

| 도구 | 이유 |
|---|---|
| Trivy | **보안 에이전트가 소유한다.** devops가 `trivy config`를 돌렸을 때 security의 SCA와 rule ID 13개가 전부 겹쳤다. [`agent-boundaries.md`](../../docs/agent-boundaries.md) 참고 |
| terraform / kubectl / helm / docker CLI | 이 에이전트는 상태를 바꾸지 않으므로 필요 없다. 설치돼 있어도 `guard_infra.sh`가 변경 동사를 거부한다 |
| tflint / kube-linter | 검토했으나 아직 안 넣었다. 현재 `OPS-*` 8개와 겹치는 범위가 있어, 넣기 전에 `agent-boundaries.md`의 5단계 절차로 실측 대조가 필요하다 |

## 설치 후 확인

```bash
sh scanners/preflight.sh
```

MISSING이 사라졌는지 보고, 종단으로 한 번 돌린다.

```bash
sh      scanners/run_operability.sh tests/fixtures
python3 ../core/gate/merge_sarif.py
python3 ../core/gate/gate.py
```

픽스처는 의도적으로 통제를 빼놨으므로 **FAIL(exit 1)이 정상**이다. PASS가
나오면 검사가 돌지 않은 것이다.
