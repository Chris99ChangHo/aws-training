# Security Engineering on AWS

AWS 오프라인 교육 과정 기록.

## 실습

(진행 예정)

## 이론 정리

`notes/` 폴더에 과정 관련 이론 정리를 추가할 수 있습니다.

---

## 이 과정에서 파생된 작업물

이 과정을 계기로 시작한 **벤더 독립 보안 에이전트**는
[`agents/security/`](../agents/security)로 옮겼습니다.

AWS Security Agent를 해체해 특정 클라우드·AI 도구에 종속되지 않게 재구현한
것이라, AWS 과정 기록과 성격이 달라 별도 계열로 관리합니다.
자세한 이유는 [`agents/README.md`](../agents/README.md) 참고.

| 문서 | 내용 |
|---|---|
| [`agents/security/`](../agents/security) | 실습 본문 — 설계 결정과 트러블슈팅 17건, 검증 결과 |
| [`agents/docs/security-standards.md`](../agents/docs/security-standards.md) | 표준과 개념 (SAST/SCA/DAST, STRIDE, CWE·CVSS·SARIF) |
| [`agents/docs/porting-to-other-harnesses.md`](../agents/docs/porting-to-other-harnesses.md) | 다른 AI 도구로 옮기는 절차 |
