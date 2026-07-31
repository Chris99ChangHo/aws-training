# Security Engineering on AWS

AWS 오프라인 교육 과정 기록.

## 실습

이 과정의 실습은 리포에 없습니다. 실습에서 파생된 작업물이 벤더 독립 보안
에이전트로 커져서 별도 계열로 분리했습니다 — 아래 "이 과정에서 파생된 작업물"
참고.

## 이론 정리

| 폴더 | 근거 | 내용 |
|---|---|---|
| [`notes/lecture/`](./notes/lecture) | 강의 + AWS 공식 문서 대조 | Day 1 — 공동 책임 모델, IAM, 감사·탐지<br>Day 2 — 거버넌스, KMS·봉투 암호화, S3·DB 보호<br>Day 3 — VPC 경계, WAF, 관측성, 인시던트 대응 |
| [`notes/_raw/`](./notes/_raw) | 수업 필기 원본 | 확보되면 넣습니다 |

상세는 [`notes/README.md`](./notes)에 있습니다. 이 과정에는 `notes/practice/`가
없습니다 — 실습이 위처럼 분리됐기 때문입니다. 그래서 강의 노트의 "확인하지 못한
것" 절에 **강의와 공식 문서 대조까지이고 직접 실행한 검증이 아니라는 점**을
명시했습니다.

---

## 이 과정에서 파생된 작업물

이 과정을 계기로 시작한 **벤더 독립 보안 에이전트**는
[`agents/security/`](../agents/security)로 옮겼습니다.

AWS Security Agent를 해체해 특정 클라우드·AI 도구에 종속되지 않게 재구현한
것이라, AWS 과정 기록과 성격이 달라 별도 계열로 관리합니다.
자세한 이유는 [`agents/README.md`](../agents/README.md) 참고.

| 문서 | 내용 |
|---|---|
| [`agents/security/`](../agents/security) | 실습 본문 — 설계 결정과 트러블슈팅 23건, 검증 결과, 테스트 178개 |
| [`agents/docs/security-standards.md`](../agents/docs/security-standards.md) | 표준과 개념 (SAST/SCA/DAST, STRIDE, CWE·CVSS·SARIF) |
| [`agents/docs/porting-to-other-harnesses.md`](../agents/docs/porting-to-other-harnesses.md) | 다른 AI 도구로 옮기는 절차 |
