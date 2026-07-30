# Labs

워크숍 커리큘럼과 1:1로 대응하지 않는, 개별 기능·API 단위의 짧은 실습을
모아둔 폴더입니다. 과정 폴더의 실습이 하나의 완결된 애플리케이션을
만드는 단위라면, 여기 있는 랩은 "이 API가 어떻게 동작하는지" 하나를
확인하는 단위입니다.

## 실습 목록

| 실습 | 폴더 | 내용 |
|---|---|---|
| Bedrock InvokeModel | [`invoke-model/`](./invoke-model) | 제공자별 네이티브 요청 포맷, 스트리밍 이벤트, Nova Canvas 이미지·Nova Reel 비디오 생성 |
| Strands Agents 기초 | [`strands-basics/`](./strands-basics) | 빌트인·커스텀 도구, 멀티턴, 콜백 관찰, Streamlit UI |
| MCP 클라이언트 연결 패턴 | [`strands-mcp-client/`](./strands-mcp-client) | stdio·Streamable HTTP 트랜스포트, MCP 도구와 로컬 `@tool` 혼합 |
| AgentCore Runtime 배포 | [`agentcore-setup/`](./agentcore-setup) | AgentCore Runtime 배포, 엔드포인트 버전 관리·승격·롤백 |

각 폴더는 자체 `README.md`와 `requirements.txt`를 갖고 독립적으로
실행됩니다.

## 공통 사항

- 대부분 `us-west-2` 리전의 Bedrock 인퍼런스 프로필을 사용합니다.
  예외는 `invoke-model`의 미디어 생성 스크립트(Nova Canvas·Reel이
  `us-east-1`에만 있음)입니다.
- 상시 과금되는 리소스가 있는 랩은 `agentcore-setup`뿐입니다(배포된
  Runtime). 나머지는 호출당 과금만 발생합니다.
