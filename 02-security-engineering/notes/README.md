# Security Engineering on AWS — 이론 정리

## 폴더가 갈리는 이유

`notes/`는 **근거의 출처**로 갈립니다. 섞으면 "수업에서 들은 것"과 "AI가 아는
것"을 독자가 구분할 수 없습니다. 규약은 `.kiro/steering/ai-attribution.md`에
있습니다.

| 폴더 | 근거 | 성격 |
|---|---|---|
| 수업 필기 원본 | 별도 문서(Google Docs) | 가공하지 않습니다. 이 리포에는 정리본만 둡니다 |
| [`lecture/`](./lecture) | 강의 + AWS 공식 문서 대조 | 필기에 없던 사실을 추가하지 않습니다. 보강한 부분은 출처를 답니다 |
| `practice/` | 실습에서 측정한 값 | **이 과정에는 없습니다** — 아래 참고 |


## 강의 정리

| 노트 | 범위 |
|---|---|
| [`lecture/day-1-iam-and-audit.md`](./lecture/day-1-iam-and-audit.md) | 공동 책임 모델, IAM, 조직 거버넌스 기초, 감사·탐지 서비스 |
| [`lecture/day-2-encryption-and-data.md`](./lecture/day-2-encryption-and-data.md) | 다중 계정 거버넌스, KMS와 봉투 암호화, 비밀 관리, S3·DB 보호 |
| [`lecture/day-3-network-and-response.md`](./lecture/day-3-network-and-response.md) | VPC 경계, 사설 연결, WAF, 관측성, 인시던트 대응 |

## 실습에서 도출한 정리

이 과정은 `practice/`가 없습니다. 실습에서 파생된 작업물이 벤더 독립 보안
에이전트로 분리돼 [`agents/security/`](../../agents/security)에 있고, 그쪽이
자체 README와 검증 결과를 갖습니다.


## 강의 노트의 공통 골격

```
# Day N — 제목
> 교육일 / AWS 공식 문서 확인일 / 범위
> AI 협업 표기
## 학습 목표
## 1..N 본문
## 복습 체크  또는  핵심 요약
## 확인하지 못한 것
## 공식 자료
```

요약 절의 이름만 노트마다 다릅니다. **`복습 체크`는 자기 점검 질문**(체크박스),
**`핵심 요약`은 요점 정리**(번호 목록)이고 내용의 성격이 실제로 다릅니다. 이름을
억지로 맞추면 내용을 잘못 표현하게 되므로 골격과 순서만 고정했습니다.

`확인하지 못한 것`은 **필수**입니다. 무엇을 검증하지 않았는지 적지 않으면
읽는 사람이 전부 확인된 것으로 오해합니다.
