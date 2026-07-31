# 다른 AI 도구로 옮기기 (포팅 가이드)

이 에이전트는 Kiro CLI, Claude Code, Codex CLI 세 개를 지원한다. 네 번째를
추가하거나, 회사가 지정한 다른 도구에 맞추려면 이 문서를 보면 된다.

먼저 알아야 할 것: **하네스를 아는 코드는 파일 하나 안에만 있다.**

```
전체 소스                 3,966줄
하네스를 모르는 부분       3,359줄  (프롬프트·manifest·스캐너·게이트·MCP·테스트)
하네스에 종속된 부분         317줄  (adapters/build.py 안: 매핑 표 55 + 렌더러 262)
```

즉 종속 비율은 8.0%이고, 그 전부가 `adapters/build.py`에 모여 있다. 수치의
정의와 산출 방법은 [`../security/README.md`](../security/README.md)의
"무엇이 벤더에 묶여 있는지"에 있다.

---

## 1. 3층 지도 — 어디를 건드리나

| 층 | 파일 | 언제 건드리나 |
|---|---|---|
| **1층** | `scanners/`, `gate/`, `mcp/server.py`, `agent/SYSTEM_PROMPT.md` | **거의 없음.** 도구가 바뀌어도, 회사가 바뀌어도 그대로 |
| **2층** | `agent/manifest.toml`, `.sec-scope`, `scanners/rules/` | **회사마다.** 임계값·허용 대상·자체 룰 |
| **3층** | `adapters/build.py` | **새 하네스를 추가할 때만** |

취업해서 정책을 맞추는 일은 **2층**이다. 새 AI 도구를 지원하는 일은 **3층**이다.

### 2층에서 실제로 바꾸는 값

`agent/manifest.toml`:

```toml
[gate]
fail_on_severity = "high"    # 이 등급 이상이면 빌드 차단
max_allowed = 0              # 몇 건까지 허용

[capabilities]
write_files = true           # 에이전트가 파일을 고칠 수 있게 할지
fetch_web = false            # 외부 URL 접근 허용 여부
```

`.sec-scope` — DAST를 허용할 호스트. 승인받은 테스트 서버를 한 줄씩 추가한다.

`scanners/rules/` — 회사 자체 Semgrep 룰을 넣으면 기본 룰셋과 함께 돌아간다.
`SEC_SAST_CONFIG`로 벤더 레지스트리 룰을 완전히 대체할 수도 있다.

---

## 2. 새 하네스를 추가하기 전에 확인할 4가지

순서대로 그 도구의 문서에서 찾으면 된다. **2번이 가장 중요하다.**

| # | 확인할 것 | 없으면 |
|---|---|---|
| 1 | MCP(Model Context Protocol) 지원 | 지원하면 절반은 끝. 스캐너를 도구로 그대로 붙인다 |
| 2 | **명령 실행 전 가로채는 훅** | **없으면 쉘 권한을 주지 말 것.** MCP 경로만 쓴다 |
| 3 | 도구 이름 (`read`? `Read`? 아예 없음?) | 매핑표에 추가 |
| 4 | 설정 파일 형식 (JSON / YAML / TOML) | 출력 함수 추가 |

### 지원하는 세 하네스의 실측 비교

| 항목 | Kiro CLI | Claude Code | Codex CLI |
|---|---|---|---|
| 에이전트 정의 | `.kiro/agents/*.json` | `.claude/agents/*.md` | `.codex/config.toml` + 별도 프롬프트 파일 |
| 프롬프트 위치 | `prompt` 필드 | 마크다운 본문 | 파일로 분리 (아래 참고) |
| 훅 이벤트 | `preToolUse` | `PreToolUse` | `PreToolUse` |
| 훅 입력 | 문서 미명시 | stdin JSON | stdin JSON |
| 명령 위치 | 미명시 | `tool_input.command` | `tool_input.command` |
| 차단 방법 | "can block" (계약 미명시) | exit 2 + stderr | exit 2 + stderr |
| 파일 읽기 | `read` 도구 (별도) | `Read` 도구 (별도) | **쉘로 처리** (별도 도구 없음) |
| MCP | `mcpServers` | `mcpServers` / `.mcp.json` | `[mcp_servers.<name>]` |
| OS 샌드박스 | 없음 | 없음 | **`sandbox_mode` 있음** |

세 가지가 배울 점이다.

**하나 — 같은 가드가 세 곳에서 그대로 돈다.** Claude Code와 Codex는 훅 계약이
동일하다(stdin JSON, `tool_input.command`, exit 2 차단). `guard_scope.sh`를 한
줄도 안 고치고 붙었다. Kiro는 계약이 문서에 없어서 가드가 6개 JSON 경로를
시도하고, 전부 실패하면 차단한다.

**둘 — 도구 구조가 다르면 훅 matcher도 달라야 한다.** Codex는 파일 읽기를
쉘로 하므로 `Bash` matcher 하나가 파일 읽기까지 덮는다. Kiro와 Claude Code는
`read`/`Read`가 별도 도구라서, matcher를 쉘로만 걸면 **`Read ~/.aws/credentials`가
가드를 우회한다.** 이 구멍은 Codex 어댑터를 추가하다 발견했다 — 하네스를 하나
더 붙이는 것 자체가 검증이었다.

**셋 — Codex는 다른 두 개에 없는 층이 있다.** `sandbox_mode`는 운영체제 수준
샌드박스이고, 훅의 거부 목록보다 강한 통제다. 거부 목록은 목록에 없는 걸
놓치지만 샌드박스는 능력 자체를 제한한다. Codex 어댑터는 이걸 켜고, 훅을 그
위의 다층 방어로 쓴다.

참고로 Codex 공식 문서도 훅의 한계를 같은 방식으로 설명한다.

> Treat tool hooks as a useful guardrail, not a complete enforcement boundary.

---

## 3. 실제 추가 절차

`adapters/build.py`만 고친다. 4단계다.

### 1단계 — 모델 ID 등록

`agent/manifest.toml`:

```toml
[model]
kiro = "claude-opus-5"
claude_code = "opus"
codex = "gpt-5.6"
newtool = "..."          # 추가
```

### 2단계 — 매핑표에 열 추가

`adapters/build.py`의 `CAPABILITY_TO_TOOLS`:

```python
"run_shell": {
    "kiro": ["shell"],
    "claude_code": ["Bash"],
    "codex": ["Bash"],
    "newtool": ["..."],      # 그 도구의 쉘 도구 이름
},
```

도구가 없는 능력은 빈 리스트(`[]`)를 넣는다. Codex의 `read_files`가 그렇다.

### 3단계 — 훅 matcher 등록

```python
HOOK_MATCHERS = {
    "kiro": ["shell", "read"],
    "claude_code": ["Bash|Read"],
    "codex": ["^(Bash|apply_patch)$"],
    "newtool": ["..."],
}
```

**파일 읽기 도구가 별도로 있으면 반드시 포함시켜야 한다.** 위 "둘" 참고.
matcher가 정규식을 받는지 확인하고, 모르면 Kiro처럼 이름마다 훅을 하나씩
등록한다.

### 4단계 — 출력 함수 작성

`build_kiro()`, `build_claude_agent()`, `build_codex_config()` 중 형식이 가장
비슷한 것을 복사해서 고친다. 그리고 `targets()`에 결과물을 추가한다.

```python
def targets(manifest, prompt):
    return [
        ...
        (NEWTOOL_OUT, build_newtool(manifest, prompt)),
    ]
```

`--check`가 자동으로 새 파일까지 드리프트 검사한다.

### 검증

```bash
python3 adapters/build.py                  # 생성
python3 adapters/build.py --check          # exit 0 이어야 함
python3 adapters/build.py --print newtool  # 눈으로 확인
```

그리고 훅이 실제로 차단하는지 반드시 실측한다.

```bash
printf '{"tool_name":"<그 도구의 쉘 도구명>","tool_input":{"command":"rm -rf /tmp/x"}}' \
  | sh scanners/guard_scope.sh ; echo "exit=$?"      # 2 여야 함
```

**exit 2가 아니면 페이로드 형태가 다르다.** `guard_scope.sh`의 JSON 경로
목록에 그 도구의 경로를 추가한다.

---

## 4. 오픈소스 모델로 돌리는 경우

아직 구현하지 않았다. 방향만 적어둔다.

이 에이전트에서 **AI가 필요한 부분은 생각보다 작다.** 스캔과 판정은 AI가 전혀
개입하지 않는다.

| 기능 | AI 필요? |
|---|---|
| 스캐너 실행 | 아니오 |
| SARIF 병합 | 아니오 |
| 합격/불합격 판정 | **아니오** (의도적) |
| 결과 해석·수정 코드 제안 | 예 |
| STRIDE 위협 모델링 | 예 |

그래서 오픈소스 모델로 옮기는 선택지는 세 가지다.

### 방법 A — AI를 아예 안 쓴다

`python3`만 있으면 스캔부터 판정까지 전부 돈다. 추가 작업 0.

```bash
sh      scanners/run_sast.sh .
sh      scanners/run_sca.sh .
python3 gate/merge_sarif.py
python3 gate/gate.py --fail-on high
```

CI에 넣을 부분은 이게 전부다. 결과 해석만 사람이 한다.

### 방법 B — 로컬 모델을 붙인 MCP 클라이언트를 쓴다

MCP는 개방 프로토콜이라 클라이언트를 고를 수 있다. Ollama 등으로 로컬 모델을
띄우고, MCP를 지원하는 클라이언트에 `mcp/server.py`를 등록한다. 어댑터를
새로 만들 필요가 없다 — MCP 서버는 클라이언트가 누구든 같다.

확인할 것: 그 클라이언트에 **명령 가로채기 훅이 있는지**(위 2번). 없으면
쉘 권한을 주지 말고 MCP 도구만 쓴다. MCP 경로는 `mcp/server.py`의 인자 검증과
`run_dast.sh`의 스코프 검증이 이미 지키고 있다.

### 방법 C — 자체 실행기를 만든다

`mcp/server.py`가 이미 도구를 노출하고 있으므로, 모델 호출부만 붙이면 된다.
모델 프로바이더를 바꿀 수 있는 추상화 계층(LiteLLM 등)을 쓰면 OpenAI 호환
엔드포인트, Ollama, Bedrock을 같은 코드로 다룰 수 있다.

이 방법의 값어치는 **모델까지 교체 가능해진다**는 점이다. 하네스 종속을
없앤 다음 단계다.

### 어느 쪽이든 바뀌지 않는 것

세 방법 모두 `scanners/`, `gate/`, `mcp/server.py`, `.sec-scope`,
`agent/SYSTEM_PROMPT.md`를 그대로 쓴다. **바뀌는 건 "누가 프롬프트를
읽는가"뿐이다.**

---

## 5. 체크리스트

새 하네스를 추가했다면 아래를 전부 확인한다.

- [ ] `python3 adapters/build.py --check` 가 exit 0
- [ ] 그 도구의 설정 검증 명령이 통과 (있으면)
- [ ] 훅에 위험 명령을 넣어 exit 2 확인
- [ ] 훅에 정상 명령을 넣어 exit 0 확인
- [ ] **파일 읽기 도구가 별도면** 자격증명 경로로 exit 2 확인
- [ ] MCP 서버가 그 클라이언트에서 도구 목록을 반환
- [ ] 스코프 밖 DAST 타겟이 거부됨
- [ ] 생성된 파일에 절대 경로·사용자명·계정 ID가 없음
- [ ] 훅이 승인/신뢰 절차를 요구하는 도구인지 확인 (Codex는 `/hooks` 필요)

마지막 항목을 빠뜨리면 **가드가 설정만 되고 동작하지 않는다.** Codex는 승인되지
않은 훅을 건너뛴다.

## 관련 문서

- 표준과 개념: [`security-standards.md`](./security-standards.md)
- 실습 본문: [`../security/README.md`](../security/README.md)
