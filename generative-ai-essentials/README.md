# Generative AI Essentials on AWS

Amazon Bedrock 기반 RAG 애플리케이션을 만드는 과정입니다. 두 실습 모두
Knowledge Base를 직접 구축하고 **검색 품질을 측정해서 개선**하는 데 초점이
있습니다.

## 실습

| 실습 | 내용 |
|---|---|
| [`seoul-travel-planner-kb/`](./seoul-travel-planner-kb) | Amazon Bedrock Knowledge Base 구축, 메타데이터 필터·하이브리드 서치·리랭킹, S3 이벤트 기반 자동 동기화, Streamlit 챗봇 |
| [`restaurant-concierge-rag/`](./restaurant-concierge-rag) | Knowledge Base 고급 검색, Corrective RAG 라우터(Strands Agents SDK), FAISS 기반 멀티모달 메뉴판 검색 |

두 실습은 **별개의 OpenSearch Serverless 컬렉션**을 씁니다. 상시 과금되므로
끝나면 각 폴더의 `cleanup.py`로 정리하세요.

## 이론 정리

근거의 출처로 폴더가 갈립니다. 상세는 [`notes/README.md`](./notes)에 있습니다.

| 폴더 | 근거 | 내용 |
|---|---|---|
| [`notes/lecture/`](./notes/lecture) | 강의 + AWS 공식 문서 대조 | Day 1 — 인스턴스형·서버리스 과금, IAM, Bedrock 인증(SigV4·API 키), 시맨틱 검색 |
| [`notes/practice/`](./notes/practice) | 실습에서 측정한 값 | 검색 기법 4가지 비교 — 하이브리드 서치가 두 실습 모두 개선 0이었던 실측 |
| [`notes/_raw/`](./notes/_raw) | 수업 필기 원본 | 가공하지 않습니다 |

정리본은 `[실측]`·`[문서]`·`[해석]`으로 근거를 구분합니다. 필기에 없던 사실을
강의 정리에 섞지 않는 이유는 그 폴더의 README에 있습니다.

## 이 과정에서 얻은 것

`[실측]` 두 실습이 서로 다른 도메인(관광지, 식당)에서 **같은 패턴**을
보였습니다.

| 기법 | seoul | restaurant |
|---|---|---|
| 기본 검색 | 1/3 | 1/3 |
| 메타데이터 필터 | 3/3 | 2/3 |
| 하이브리드 서치 | 1/3 | 1/3 |
| 리랭킹 | 2/3 | 2/3 |

하이브리드 서치가 두 번 다 개선이 없었다는 것이 이 과정에서 가장 배운
지점입니다. 설정 문제가 아니라 **질의에 고유 키워드가 없으면 텍스트 매칭이
기여할 여지가 없다**는 것이고, 이걸 알려면 측정해야 합니다. 자세한 근거는
위 노트에 있습니다.
