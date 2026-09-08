# Labs

워크숍 커리큘럼과 1:1로 대응하지 않는, 개별 기능·API 단위의 짧은 실습과
워크숍 미션 시리즈를 모아둔 폴더입니다. 과정 폴더의 실습이 하나의 완결된
애플리케이션을 만드는 단위라면, 여기 있는 랩은 "이 API가 어떻게 동작하는지"
하나를 확인하는 단위입니다.

## 실습 목록

| 실습 | 폴더 | 내용 |
|---|---|---|
| Bedrock InvokeModel | [`invoke-model/`](./invoke-model) | 제공자별 네이티브 요청 포맷, 스트리밍 이벤트, Nova Canvas 이미지·Nova Reel 비디오 생성 |
| AgentCore Runtime 배포 | [`agentcore-setup/`](./agentcore-setup) | AgentCore Runtime 배포, 엔드포인트 버전 관리·승격·롤백 |
| 미션 시리즈 8개 | [`mission/`](./mission) | RAG → Strands 에이전트 → 멀티에이전트 → AgentCore 배포·통합 → CI/CD → 웹 서비스 → 코딩 에이전트 |

`mission/` 하위 8개 미션은 앞 미션의 산출물 위에 쌓이는 시리즈입니다 —
목록과 폴더 규칙은 [`mission/README.md`](./mission)에 있습니다. 나머지 폴더는
자체 `README.md`와 `requirements.txt`를 갖고 독립적으로 실행됩니다.

Strands Agents 기초·MCP 클라이언트 랩은 `developing-genai-apps` 과정에
묶여 있어 [`developing-genai-apps/strands-basics/`](../developing-genai-apps/strands-basics)와
[`developing-genai-apps/strands-mcp-client/`](../developing-genai-apps/strands-mcp-client)에
있습니다.

## 공통 사항

- 대부분 `us-west-2` 리전의 Bedrock 인퍼런스 프로필을 사용합니다.
  예외는 `invoke-model`의 미디어 생성 스크립트(Nova Canvas·Reel이
  `us-east-1`에만 있음)입니다.
- 상시 과금되는 리소스가 있는 랩은 `agentcore-setup`(배포된 Runtime)과
  `mission/`의 4·5·6·7·8번입니다 — AgentCore Runtime, CloudFront 배포,
  S3 버킷, NAT 게이트웨이, VPC 인터페이스 엔드포인트가 배포된 상태로
  남아있습니다. 나머지는 호출당 과금만 발생합니다.
