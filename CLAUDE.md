# aws-training

AWS 오프라인 교육 기록과, 그 과정에서 파생된 벤더 독립 에이전트 작업물.

이 파일은 **색인**입니다. 상세 규칙은 `.claude/rules/`(항상 로드)와
`.claude/skills/`(필요할 때 로드)에 있으므로 여기 옮겨 적지 않습니다.

## 성격이 다른 두 축

| 축 | 위치 | 성격 |
|---|---|---|
| 과정 | `generative-ai-essentials/`, `security-engineering/`, `developing-genai-apps/`, `labs/` | 학습 기록. 내용이 AWS에 종속돼도 무방 |
| 에이전트 | `agents/` | 작업물. **정의상 벤더 독립** |

두 번째를 첫 번째 안에 넣지 않습니다. 벤더 독립이 목표인 산출물이 특정 벤더
과정 폴더에 들어가면 계속 어긋나기 때문입니다.

## 규칙과 스킬은 Kiro CLI와 공유합니다

이 리포는 Kiro CLI로도 작업합니다. 규약을 두 벌로 유지하면 갈라지므로
**심볼릭 링크로 한 벌만 둡니다.**

```
.claude/rules   -> ../.kiro/steering    항상 로드되는 규약
.claude/skills  -> ../.kiro/skills      필요할 때 로드되는 절차
```

따라서 규약을 고칠 때는 `.kiro/steering/`과 `.kiro/skills/`의 원본을
고칩니다. 링크된 쪽을 고치는 것과 결과는 같지만, 원본 위치를 기준으로
생각하는 편이 혼동이 적습니다.

**개선 여지**: Claude Code의 rules는 `paths:` 프론트매터로 조건부 로딩을
지원합니다(Kiro는 지원하지 않습니다). `python-conventions.md`를
`**/*.py`로 스코프하면 문서만 고치는 세션에서 컨텍스트를 아낄 수 있습니다.
지금 넣지 않은 이유는 Kiro가 그 키를 어떻게 파싱하는지 검증하지 못했고,
잘못되면 규약이 조용히 사라지기 때문입니다.

## 자주 쓰는 명령

### 보안 에이전트 (`agents/security/`)

```bash
# 어댑터 재생성. .kiro/ .claude/ .codex/ 설정은 전부 생성물이다
python3 agents/security/adapters/build.py
python3 agents/security/adapters/build.py --check   # 드리프트 감지, exit 1이면 불일치

# 테스트 178개. 스캐너가 하나도 없어도 전부 돈다
sh      agents/security/tests/test_guard_scope.sh   # 훅 차단 로직 100
python3 agents/security/tests/test_gate.py          # 게이트 + SARIF 정규화 39
python3 agents/security/tests/test_mcp_server.py    # MCP 프로토콜 20
python3 agents/security/tests/test_adapters.py      # 생성물 성질 19

# 스캔과 판정 (LLM 개입 없음)
cd agents/security
sh      scanners/preflight.sh          # 어떤 스캐너가 있는지
sh      scanners/run_sast.sh <path>    # Semgrep
sh      scanners/run_sca.sh <path>     # Trivy (경로 아니면 컨테이너 이미지로 판별)
sh      scanners/run_dast.sh <url>     # Nuclei, .sec-scope 안에서만
python3 gate/merge_sarif.py
python3 gate/gate.py --fail-on high --max-allowed 0
```

### 실습 정리

```bash
# 상시 과금 리소스 정리 (기본은 dry-run)
python3 generative-ai-essentials/seoul-travel-planner-kb/cleanup.py
python3 generative-ai-essentials/seoul-travel-planner-kb/cleanup.py --delete
```

## 절대 하지 않는 것

`.claude/rules/git-conventions.md`에 상세가 있습니다. 요약하면:

- **생성된 어댑터를 직접 수정하지 않습니다.** `.kiro/agents/`, `.claude/agents/`,
  `.claude/settings.json`, `.codex/`는 전부 `build.py`의 출력입니다. 고칠 것이
  있으면 `agents/security/agent/manifest.toml`이나 `SYSTEM_PROMPT.md`를 고치고
  재생성합니다.
- **자격 증명·계정 ID·리소스 ID를 커밋하지 않습니다.** 공개 리포입니다.
  `kb_info.json`은 `.gitignore` 대상입니다.
- **`.sec-scope`를 편집하지 않습니다.** DAST 권한 경계이고 사람만 고칩니다.

## CI

`.github/workflows/security-gate.yml`이 push마다 돕니다. **모델 호출이 없습니다.**

| 잡 | 범위 | 차단 |
|---|---|---|
| `verify` | 어댑터 드리프트 + 테스트 178개 | 예 |
| `gate` | `agents/` SAST·SCA 후 판정 | 예 |
| `report` | 리포 전체 스캔, 보고만 | 아니오 |

`gate`가 `agents/`만 보는 이유는 실측에 있습니다 — 리포 전체는 high 5건에서
FAIL하고, 전부 `labs/agentcore-setup/`의 생성 락파일이라 여기서 고칠 수
없습니다. 자세한 근거는 `agents/security/README.md`에 있습니다.

## 이론 정리를 쓸 때

`notes/`는 근거의 출처로 갈립니다. 섞으면 "수업에서 들은 것"과 "AI가 아는 것"을
독자가 구분할 수 없습니다.

```
notes/lecture/   강의 정리. 필기 + AWS 공식 문서 대조가 근거입니다
notes/practice/  실습에서 도출한 정리. 측정이 근거입니다
notes/README.md  색인 — 어떤 노트가 무슨 근거인지
```

수업 필기 원본은 별도 문서(Google Docs)로 관리하며, 가공하지 않습니다.
이 리포에는 정리본만 둡니다.

정리본에는 `[실측]`·`[문서]`·`[해석]`으로 근거를 표시합니다. **필기에 없던
사실을 강의 정리에 추가하지 않습니다.** AI 기여 표기 규칙은
`.claude/rules/ai-attribution.md`에 있습니다.

## 더 볼 것

| 주제 | 위치 |
|---|---|
| 보안 에이전트 전체 (설계·트러블슈팅 23건·검증) | `agents/security/README.md` |
| 계열 설계 원칙, 폐기한 DevOps 시도 | `agents/README.md` |
| 보안 표준 ↔ 코드 매핑 | `agents/docs/security-standards.md` |
| 다른 하네스로 옮기기 | `agents/docs/porting-to-other-harnesses.md` |
| 스캐너 설치 | `agents/security/docs/setup-sec-tools.md` |
