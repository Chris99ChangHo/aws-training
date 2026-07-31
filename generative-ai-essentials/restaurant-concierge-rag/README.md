# 강남 식당 컨시어지 RAG — Amazon Bedrock Knowledge Base 실습

![AWS](https://img.shields.io/badge/AWS-Bedrock-01A88D)
![OpenSearch](https://img.shields.io/badge/OpenSearch-Serverless-005EB8?logo=opensearch&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-1.51-FF4B4B?logo=streamlit&logoColor=white)
![Anthropic](https://img.shields.io/badge/Anthropic-Claude_Sonnet_4.6-191919?logo=anthropic&logoColor=white)
![Strands Agents](https://img.shields.io/badge/Strands_Agents-1.x-4B32C3)
![Cohere Rerank](https://img.shields.io/badge/Cohere-Rerank-39594D)
![FAISS](https://img.shields.io/badge/FAISS-vector_search-0467DF)

강남 식당 8곳 데이터로 Amazon Bedrock Knowledge Base를 구축하고,
메타데이터 필터·하이브리드 서치·리랭킹으로 검색 품질을 개선한 뒤,
Corrective RAG 라우터 에이전트(Strands Agents SDK)와 멀티모달
메뉴판 검색(FAISS)까지 구현한 실습 기록입니다.

`seoul-travel-planner-kb` 실습과 같은 패턴을 재사용하면서, 4-5단계는
Agentic RAG와 멀티모달이라는 새로운 영역을 다룹니다.

## 사용 기술

`Amazon Bedrock Knowledge Bases` · `Amazon OpenSearch Serverless` ·
`Amazon Titan Embeddings V2` · `Anthropic Claude Sonnet 4.6` ·
`Cohere Rerank` · `Strands Agents SDK` · `FAISS` · `boto3` · `Streamlit`

## 아키텍처

```
S3 (restaurant-docs/*.docx + *.metadata.json)
   │
   ▼
Bedrock Knowledge Base ── OpenSearch Serverless (벡터 인덱스)
   │  Titan Embeddings V2 (1024차원)
   ▼
Retrieve / RetrieveAndGenerate API
   │  메타데이터 필터 · 하이브리드 서치 · 리랭킹
   ├──▶ Streamlit 챗봇 (필터 + 멀티턴 대화)
   └──▶ Corrective RAG 라우터 (Strands Agents SDK)
           KB 검색 → 품질 분류 → 라우팅 (KB / KB+웹 / 웹만)

별도 파이프라인 (로컬, KB 미사용):
menu_data.json → 캡셔닝 → Titan Embed V2 → FAISS 인덱스
                → 텍스트 질의로 크로스모달 검색
```

## 설계 결정과 트러블슈팅

이 실습은 Kiro CLI(모델: claude-sonnet-5)와 함께 진행했습니다. 아래
트러블슈팅은 AI 에이전트가 실행한 도구 결과(로그·에러 메시지)를 근거로
정리했으며, 어떤 해결 방향을 택할지는 사람이 검토·승인한 내용입니다.

### 1. 워크숍 가이드의 리전(`us-west-2`)과 사전 준비된 리소스(`us-east-1`) 불일치

강사가 사전에 만들어 둔 KB(`labs-kb`)와 데이터는 `us-east-1`에 있었는데,
미션 문서는 전부 `us-west-2`를 지정했다. `us-west-2`에는 KB가 전혀
없었고(`list-knowledge-bases` 결과 빈 배열), `us.anthropic.claude-sonnet-4-6`도
리전마다 가용성이 다르다는 걸 먼저 확인했다.

→ 대응: S3 데이터를 `aws s3 sync`로 `us-west-2` 새 버킷에 복사하고,
`setup_02_create_kb.py`로 그 리전에 KB를 새로 구축했다(오늘 만든
`seoul-travel-planner-kb`의 스크립트 패턴 재사용). 이렇게 하면 워크숍
가이드가 요구하는 리전과 실제 리소스가 맞아떨어진다.

### 2. IAM 정책 재실행 시 권한이 사라지는 문제

`put_role_policy`로 Rerank 권한을 별도로 추가했는데, `setup_02_create_kb.py`를
재실행하니 `ensure_role()`이 정책 전체를 원래 정의(Rerank 미포함)로
덮어써서 리랭킹이 다시 막혔다. 멱등하게 설계했다고 생각한 스크립트가
실제로는 "실행할 때마다 최신 상태로 되돌리는" 부작용이 있었던 셈이다.

→ 대응: `ensure_role()`의 정책 정의 자체에 `bedrock:Rerank`를 포함시켜,
재실행해도 항상 리랭킹 권한이 유지되도록 고쳤다. 임시로 권한을
추가하고 스크립트를 고치지 않으면, 다음 실행에서 똑같이 깨진다는
교훈.

### 3. UI에 계정 ID가 그대로 노출된 사례

Streamlit 앱의 참조 문서 카드가 전체 S3 URI
(`s3://restaurant-concierge-kb-data-<계정ID>/...`)를 그대로 표시하고
있었다. 코드 리뷰 중 실제 스크린샷에서 계정 ID가 보이는 것을 확인하고
카드에서 파일명만 표시하도록 수정했다. 계정 ID를 코드에 안 박아도,
런타임에 계정 ID가 포함된 값을 화면에 그대로 뿌리면 데모/캡처 시
그대로 유출된다는 걸 실습으로 확인한 사례다.

### 4. Corrective RAG 라우터에서 도구의 오분류를 모델이 스스로 보완

`classify_quality` 도구는 유사도 점수 임계값만으로 correct/ambiguous/
incorrect를 판정하는데, "미쉐린 가이드 신규 선정 식당" 질의에서 KB의
강남 식당 청크가 점수만으로는 `correct`로 분류됐다. 하지만 실제로는
미쉐린과 전혀 무관한 내용이었다. 시스템 프롬프트에 "절대 근거 없이
답을 지어내지 않는다"를 명시해 두었더니, 모델이 도구의 분류 결과를
그대로 믿지 않고 청크 내용을 재검토해 스스로 웹 검색으로 전환했다.
규칙 기반 도구의 한계를 LLM이 판단으로 보완하는 사례를 실제로
관찰했다.

## 구성

```
data/
  menu_data.json      # 메뉴판 이미지의 텍스트 대리 데이터 (미션 제공)
  menu_captions.json  # 생성된 캡션 (06 실행 후 생성)
  menu_index.faiss    # FAISS 벡터 인덱스 (06 실행 후 생성)

setup_01_verify_kb.py       # KB 구축 확인 + 시맨틱 검색 검증
setup_02_create_kb.py       # KB + OpenSearch Serverless 벡터스토어 생성/동기화

01_filter_search.py         # 메타데이터 필터 (equals / andAll)
02_hybrid_search.py         # 시맨틱 vs 하이브리드 서치 비교
03_rerank_search.py         # 리랭킹 (Cohere Rerank v3.5)
04_compare_all.py           # 동일 질의로 4가지 기법 종합 비교

05_agentic_rag_router.py    # Corrective RAG 라우터 (Strands Agents SDK)
06_multimodal_menu_search.py # 멀티모달 메뉴판 검색 (Vision 분석 + FAISS)

app.py                      # Streamlit 대화형 추천 챗봇 (라이트/다크 모드)
```

## 실행 방법

### 0. 사전 준비

```bash
python3.12 -m venv .venv312
.venv312/bin/pip install -r requirements.txt
aws configure   # 또는 SSO 임시 자격 증명 설정 (리전: us-west-2)
```

### 1. KB 구축 확인

```bash
.venv312/bin/python setup_02_create_kb.py
.venv312/bin/python setup_01_verify_kb.py
```

`setup_02_create_kb.py` 실행 후 `kb_info.json`이 생성됩니다(계정별
값이 담겨 있어 `.gitignore`에서 제외했습니다).

### 2. 검색 품질 개선 실험

```bash
.venv312/bin/python 01_filter_search.py
.venv312/bin/python 02_hybrid_search.py
.venv312/bin/python 03_rerank_search.py
.venv312/bin/python 04_compare_all.py
```

### 3. Agentic RAG 라우터

```bash
.venv312/bin/python 05_agentic_rag_router.py
```

### 4. 멀티모달 메뉴판 검색

```bash
.venv312/bin/python 06_multimodal_menu_search.py
```

### 5. 챗봇 실행

```bash
.venv312/bin/streamlit run app.py
```

## 검증 결과 요약

동일 질의 **"회식하기 좋은 한식당 추천해 주세요"** 기준, 상위 3개 중
한식당 비율:

| 기법 | 비율 | 비고 |
|---|---|---|
| 기본 검색 | 1/3 | 무관한 문서가 상위 진입 |
| 메타데이터 필터 | 2/3 | 정밀도 최고, `category='한식'`만 정확히 2곳 반환 |
| 하이브리드 서치 | 1/3 | "한식당"은 일반 명사라 이 질의에서는 개선 없음 |
| 리랭킹 (Cohere Rerank v3.5) | 2/3 | 필터처럼 자르지 않고 의미 기반으로 재배치 |

**Corrective RAG 라우터**: KB에 있는 질문("트라토리아 벨라 위치·가격")은
`[전략: KB 검색만 사용]`, KB에 없는 질문("미쉐린 신규 선정 식당")은
`[전략: 웹 검색만 사용]`으로 정확히 라우팅.

**멀티모달 검색**: 텍스트 질문 3종(데이트 분위기/2만원 이하 파스타/
가족 모임) 모두 정확한 캡션 검색 및 근거 기반 답변. 데이터에 없는
질문("발렛 파킹 있나요?")에는 정보가 없음을 정직하게 답변(지어내지
않음).

## 참고 사항

- **자격 증명**: 이 리포지토리에는 AWS 자격 증명, 계정 ID, 리소스 ID가
  포함되어 있지 않습니다. `kb_info.json`(계정별 KB ID·버킷명)은
  `.gitignore`로 제외되어 있으며, 실행 시 자동으로 생성됩니다.
- **비용**: OpenSearch Serverless 벡터 컬렉션은 최소 OCU가 상시
  과금됩니다. 이 실습은 `seoul-travel-planner-kb`와 별개의 컬렉션을
  씁니다(계정에 총 2개). 실습이 끝나면 둘 다 삭제하는 것을 권장합니다.
- **리랭킹**: Cohere Rerank는 AWS Marketplace 서드파티 모델이라 계정
  정책에 따라 `aws-marketplace:Subscribe` 권한이 간헐적으로 막힐 수
  있습니다. `setup_02_create_kb.py`가 실행 역할에 Rerank 권한을 함께
  부여하도록 되어 있어, 재실행해도 권한이 유지됩니다.
