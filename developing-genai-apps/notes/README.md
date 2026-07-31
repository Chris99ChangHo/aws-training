# Developing Generative AI Applications on AWS — 이론 정리

## 폴더가 갈리는 이유

`notes/`는 **근거의 출처**로 갈립니다. 섞으면 "수업에서 들은 것"과 "AI가 아는
것"을 독자가 구분할 수 없습니다. 규약은 `.kiro/steering/ai-attribution.md`에
있습니다.

| 폴더 | 근거 | 성격 |
|---|---|---|
| [`_raw/`](./_raw) | 수업 필기 원본 | 가공하지 않습니다. 형식을 다듬지도 않습니다 |
| [`lecture/`](./lecture) | 강의 + AWS 공식 문서 대조 | 필기에 없던 사실을 추가하지 않습니다. 보강한 부분은 출처를 답니다 |
| [`practice/`](./practice) | 실습에서 **측정한 값** | 강의와 무관하게 코드를 돌려 얻은 결과입니다 |


## 강의 정리

| 노트 | 범위 |
|---|---|
| [`lecture/day-1-agent-basics.md`](./lecture/day-1-agent-basics.md) | 체인 vs 에이전트, 구성요소, 자율성 3단계, ReAct/ReWoo, 도구 스키마, MCP 전송 |
| [`lecture/day-2-state-and-strands.md`](./lecture/day-2-state-and-strands.md) | 에이전틱 루프, 세션·상태·컨텍스트, 장기 기억, 시스템 프롬프트, Strands SDK |

## 실습에서 도출한 정리

| 노트 | 근거 |
|---|---|
| [`practice/agent-app-design.md`](./practice/agent-app-design.md) | `gangnam-dining-concierge` 트러블슈팅 8건에서 뽑은 설계 원칙 |


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
