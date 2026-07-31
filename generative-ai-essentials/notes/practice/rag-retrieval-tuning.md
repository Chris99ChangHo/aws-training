# RAG 검색 품질 튜닝 — 네 가지 기법과 언제 무엇이 이기는가

## 이 노트의 성격

이 리포의 두 실습(`seoul-travel-planner-kb`, `restaurant-concierge-rag`)에서
**실제로 측정한 결과**를 근거로 정리한 것이다. 개념 설명은 AWS 공식 문서를
조회해 확인했고 출처를 달았다.

표기 규칙:

- `[실측]` — 이 리포의 실습에서 직접 측정한 값
- `[문서]` — AWS 공식 문서 인용. 링크 있음
- `[해석]` — 위 둘을 놓고 내린 판단. 문서에 그렇게 쓰여 있는 것이 아니다

수업 필기 원본은 `_raw/`에 둔다. 필기에 없던 사실을 정리본에 섞지 않기
위해서다.

---

## 1. Knowledge Base 검색은 기본적으로 벡터 유사도다

Bedrock Knowledge Base에 질의하면, 질문을 임베딩 모델로 벡터화해서 벡터
스토어에서 가까운 청크를 찾는다. 두 실습 모두 `amazon.titan-embed-text-v2:0`
(1024차원)과 OpenSearch Serverless 벡터 컬렉션을 썼다.

여기서 나오는 문제가 이 노트의 출발점이다.

> `[실측]` 동일 질의에서 **기본 검색은 상위 3개 중 1개만 의도에 맞았다.**
> 두 실습 모두 같았다.
>
> | 실습 | 질의 | 기본 검색 정확도 |
> |---|---|---|
> | seoul-travel-planner-kb | "서울에서 반나절 역사 코스" | 1/3 |
> | restaurant-concierge-rag | "회식하기 좋은 한식당 추천해 주세요" | 1/3 |

`[해석]` 원인은 **벡터 점수가 촘촘히 붙는 것**이다. 문서들이 같은 도메인
(관광지 소개, 식당 소개)이면 임베딩 공간에서 서로 가깝다. "역사 코스"와
"쇼핑 코스"의 거리가 "역사 코스"와 "역사 유적"의 거리와 크게 다르지 않으면,
상위 3개에 무관한 문서가 섞인다. 임베딩이 나쁜 게 아니라 **구분해야 하는
축이 임베딩이 표현하는 축과 다른** 것이다.

그래서 벡터 유사도 위에 얹는 기법이 필요하다.

---

## 2. 네 가지 기법

### 2.1 기본 (SEMANTIC) — 벡터만

`[문서]` "By default, Amazon Bedrock decides a search strategy for you."
— [`overrideSearchType`](https://docs.aws.amazon.com/sdk-for-ruby/v3/api/Aws/Bedrock/Types/KnowledgeBaseVectorSearchConfiguration.html)

명시하지 않으면 Bedrock이 전략을 고른다. `SEMANTIC`을 지정하는 것도, 아래
`HYBRID`를 지정하는 것도 **기본 동작을 덮어쓰는(override) 것**이다.

### 2.2 메타데이터 필터 — 후보를 잘라낸다

문서에 붙인 메타데이터(`category`, `theme` 등)로 **검색 대상 자체를 좁힌다.**
필터 밖의 문서는 점수가 아무리 높아도 나오지 않는다.

> `[실측]` 정확도가 가장 높았다. seoul 3/3, restaurant 2/3
> (`category='한식'`에 해당하는 문서가 정확히 2개였다).

`[해석]` 필터가 이기는 조건은 **질의 의도를 구조화된 값으로 옮길 수 있을 때**다.
"한식당"은 `category='한식'`로 옮겨진다. "회식하기 좋은"은 옮겨지지 않는다 —
그건 분위기·좌석·가격이 섞인 판단이고 메타데이터 한 칸에 없다.

**대가**: 필터가 틀리면 정답이 원천 배제된다. 재현율(recall)을 정밀도와
바꾸는 거래다.

### 2.3 하이브리드 서치 — 벡터 + 원문 텍스트

`[문서]` "If you're using an Amazon OpenSearch Serverless vector store that
contains a filterable text field, you can specify whether to query the
knowledge base with a `HYBRID` search using both vector embeddings and raw
text, or `SEMANTIC` search using only vector embeddings. **For other vector
store configurations, only `SEMANTIC` search is available.**"
— 같은 문서

두 가지가 중요하다.

1. `HYBRID`는 벡터 유사도와 **원문 텍스트 매칭**을 함께 쓴다.
2. **OpenSearch Serverless + 필터 가능한 텍스트 필드**일 때만 쓸 수 있다.
   다른 벡터 스토어에서는 선택지가 없다.

> `[실측]` **두 실습 모두 개선이 없었다.** seoul 1/3, restaurant 1/3 —
> 기본 검색과 동일했다.

`[해석]` 이유는 **질의에 고유 키워드가 없다는 것**이다. 텍스트 매칭이 기여하는
경우는 질의에 드문 토큰이 있을 때다 — 상호명(`트라토리아 벨라`), 지명, 모델명,
에러 코드처럼 그 문서에만 나오는 문자열. 반면 측정에 쓴 질의는
"역사 코스", "한식당", "회식"처럼 **일반 명사**다. 코퍼스 어디에나 나오므로
텍스트 매칭이 순위를 바꾸지 못한다.

이건 하이브리드가 쓸모없다는 뜻이 아니라, **효과가 질의 유형에 달려 있다는**
뜻이다. 하이브리드를 켜고 개선이 없으면 "설정이 잘못됐다"가 아니라 "이 질의는
어휘로 구분되는 종류가 아니다"일 수 있다.

### 2.4 리랭킹 — 순위를 다시 매긴다

1차 검색으로 후보를 넉넉히 가져온 뒤, 별도의 리랭커 모델이 **질의-문서 쌍을
직접 채점**해서 재배치한다. 두 실습은 Cohere Rerank v3.5를 썼다.

> `[실측]` seoul 2/3, restaurant 2/3. 필터보다 낮고 기본보다 높았다.

`[해석]` 리랭킹의 성질은 **자르지 않고 재배치한다**는 것이다. 필터는 후보를
없애고, 리랭커는 순서만 바꾼다. 그래서 정답이 1차 검색 후보 안에 있으면
끌어올려 주고, 후보에 아예 없으면 아무것도 못 한다. **1차 검색의 재현율이
리랭킹의 상한이다.**

**대가**: 호출이 한 번 더 늘고(지연·비용), Cohere는 AWS Marketplace 서드파티
모델이라 `aws-marketplace:Subscribe` 권한이 필요하다. 계정 정책으로 막히면
동작하지 않는다.

---

## 3. 무엇을 언제 쓰는가

`[해석]` 위 실측을 놓고 정리한 판단이다.

| 상황 | 선택 | 이유 |
|---|---|---|
| 질의 의도가 구조화된 값으로 옮겨진다 (카테고리, 지역, 가격대) | **메타데이터 필터** | 정밀도가 가장 높다. 단, 필터가 틀리면 정답이 사라진다 |
| 질의에 고유 명사·식별자가 있다 (상호명, 에러 코드, 모델명) | **하이브리드** | 텍스트 매칭이 기여할 여지가 있다 |
| 질의가 일반 명사·서술형이고 뉘앙스로 갈린다 ("회식하기 좋은") | **리랭킹** | 구조화할 수 없는 판단을 모델이 채점한다 |
| 후보에 정답이 아예 안 잡힌다 | 위 어느 것도 아님 → **청킹·임베딩·데이터를 본다** | 재배치로는 없는 문서를 만들 수 없다 |

**섞을 수 있다.** 필터로 범위를 좁히고 그 안에서 리랭킹하는 조합이 실무에서
흔하다. 이 리포의 실습은 기법별 효과를 분리해서 보기 위해 하나씩만 켰다.

---

## 4. 측정하지 않으면 알 수 없다

이 노트에서 가장 재사용 가능한 결론은 기법 목록이 아니라 절차다.

`[해석]` **"하이브리드가 더 좋다"는 명제는 질의를 지정하지 않으면 참도 거짓도
아니다.** 두 실습에서 하이브리드는 0% 개선이었다. 다른 질의였다면 이겼을 수
있다. 그래서 검색 품질 작업은 이렇게 한다.

1. 대표 질의를 고정한다. 바꾸면 비교가 무의미해진다
2. 정답 기준을 먼저 정한다 (여기서는 "상위 3개 중 의도에 맞는 문서 수")
3. 기법을 **하나씩** 켜고 같은 질의로 돈다
4. 개선이 없으면 설정을 의심하기 전에 **왜 없는지** 설명해 본다

3번을 건너뛰고 여러 개를 동시에 켜면, 개선이 있어도 무엇이 기여했는지 모른다.

---

## 출처

| 항목 | 출처 |
|---|---|
| `overrideSearchType`의 HYBRID/SEMANTIC 의미와 벡터 스토어 제약 | [KnowledgeBaseVectorSearchConfiguration](https://docs.aws.amazon.com/sdk-for-ruby/v3/api/Aws/Bedrock/Types/KnowledgeBaseVectorSearchConfiguration.html) |
| OpenSearch Serverless OCU·과금 구조 | [OpenSearch Service 요금](https://aws.amazon.com/opensearch-service/pricing/) |
| 실측값 | [`seoul-travel-planner-kb/README.md`](../../seoul-travel-planner-kb/README.md), [`restaurant-concierge-rag/README.md`](../../restaurant-concierge-rag/README.md) 검증 결과 요약 |

## 확인하지 못한 것

- 하이브리드가 **이기는** 질의를 실제로 측정하지 못했다. 고유 명사가 든 질의로
  대조했어야 "질의 유형에 달렸다"는 해석이 근거를 얻는다. 현재는 두 번의
  "개선 없음"과 문서상의 동작 설명에서 나온 추론이다.
- 필터와 리랭킹을 **함께** 켠 조합을 측정하지 않았다.
- 청킹 전략(크기·중첩)을 바꿔 본 비교가 없다. 4번 표의 마지막 줄
  ("청킹·임베딩·데이터를 본다")은 실측이 아니라 소거법이다.
