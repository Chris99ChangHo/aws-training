# mission

AWS 워크숍 미션 시리즈 8개를 순서대로 진행한 기록입니다. 각 미션은 앞
미션의 산출물 위에 쌓이므로 번호 순서가 곧 의존 순서입니다.

## 미션 목록

| 미션 | 폴더 | 내용 |
|---|---|---|
| 1 | [`01-rag-basics/`](./01-rag-basics) | Bedrock Knowledge Bases로 RAG 구성 — KB 생성, 검색 옵션(필터·하이브리드·리랭킹) 비교, 메타데이터 필터 챗봇 |
| 2 | [`02-strands-agent/`](./02-strands-agent) | Strands Agents SDK — `@tool` 커스텀 도구, MCP stdio 연동, 세션 영속화, Streamlit 챗봇 |
| 3 | [`03-multiagent-collaboration/`](./03-multiagent-collaboration) | 멀티에이전트 협업 3패턴 — agents-as-tools 위임, Graph 조건 분기, 콜백 오케스트레이션 |
| 4 | [`04-agentcore-deployment/`](./04-agentcore-deployment) | AgentCore CLI로 `DiningConcierge` Runtime 배포, CLI·boto3·Streamlit 3경로 호출 검증 |
| 5 | [`05-agentcore-integration/`](./05-agentcore-integration) | Gateway(KB Lambda 타깃) + Memory(세션 간 취향 유지) + 프로덕션 Streamlit 앱 통합 |
| 6 | [`06-cicd-pipeline/`](./06-cicd-pipeline) | 평가 게이트를 통과해야 배포되는 CodePipeline 구축, 결함 버전 차단·복구 실증 |
| 7 | [`07-dining-web-service/`](./07-dining-web-service) | SAM 서버리스 API → Cloudscape 채팅 프론트 → CloudFront 정적 호스팅 → 풀스택 파이프라인 |
| 8 | [`08-coding-agent-build/`](./08-coding-agent-build) | 코딩 에이전트 구축 — 도구 3종, 자기 교정 루프, Runtime 서비스화, Lambda MicroVMs 샌드박스 |

## 폴더 규칙

- 각 미션 폴더에 `prompts.txt`(워크숍이 제시한 원본 지시문, **수정하지
  않음**)와 `README.md`(설계 결정·검증 결과·트러블슈팅)를 둔다.
- 스크린샷(`image*.png`)은 미션 폴더 루트에 모은다.
- 미션 안에서 단계별로 프로젝트가 갈리는 경우(01·02·03·08)만 번호 접두사
  하위 폴더로 나눈다. 한 프로젝트를 4단계에 걸쳐 확장하는 경우(04·06·07)는
  미션 폴더 직하에 둔다.

`prompts.txt`가 지시하는 작업 경로(`labs/mission-*`, `labs/dining-web` 등)와
실제 경로는 다르다 — 지시문은 원본 그대로 보존하고, 산출물은 미션 폴더
하위에 모은다. 각 미션 README 상단에 이 차이를 명시했다.

## 비용 주의

4·5·6·7·8번은 상시 과금 리소스를 남긴다 — AgentCore Runtime, CloudFront
배포, S3 버킷, NAT 게이트웨이·VPC 인터페이스 엔드포인트(8번), CodePipeline
아티팩트 버킷. 각 미션 README의 "비용 주의사항"·"정리" 섹션에 삭제 명령이
있다.
