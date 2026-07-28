# 서울 여행 플래너 — Amazon Bedrock Knowledge Base 실습

서울 관광지 9곳 데이터로 Amazon Bedrock Knowledge Base를 구축하고,
메타데이터 필터·하이브리드 서치·리랭킹을 적용해 검색 품질을 개선한 뒤,
Streamlit으로 대화형 추천 챗봇을 만든 실습 기록입니다.

RAG 파이프라인 구축부터 검색 품질 튜닝, 이벤트 기반 자동화까지
직접 겪은 문제와 해결 과정을 함께 정리했습니다.

## 사용 기술

`Amazon Bedrock Knowledge Bases` · `Amazon OpenSearch Serverless` ·
`AWS Lambda` · `Amazon S3` · `Amazon Titan Embeddings V2` ·
`Anthropic Claude` · `Cohere Rerank` · `boto3` · `Streamlit`

## 아키텍처

```
S3 (guides/*.txt + *.metadata.json)
   │  ObjectCreated / ObjectRemoved 이벤트
   ▼
Lambda (travel-kb-auto-sync)
   │  start_ingestion_job (진행 중 job 중복 방지)
   ▼
Bedrock Knowledge Base ── OpenSearch Serverless (벡터 인덱스, faiss/hnsw)
   │  Titan Embeddings V2 (1024차원)
   ▼
RetrieveAndGenerate / Retrieve API
   │  메타데이터 필터 · 하이브리드 서치 · 리랭킹
   ▼
Streamlit App (Claude Sonnet 4.5, 멀티턴 세션 유지)
```

콘솔의 "Quick create" 벡터 스토어 마법사가 자동으로 처리하는 작업을
`boto3`로 직접 구현했습니다 (`setup_02_create_kb.py`):
IAM 실행 역할과 인라인 정책, OpenSearch Serverless 암호화/네트워크/데이터
액세스 정책, 벡터 컬렉션과 인덱스(`knn_vector`, dimension=1024,
engine=faiss), Knowledge Base, S3 데이터 소스, ingestion job까지
전 과정을 스크립트 한 번으로 재현 가능하게 만들었습니다.

## 설계 결정과 트러블슈팅

실습하면서 실제로 겪은 문제와 원인 분석, 해결 방식입니다. 단순히
"됐다/안 됐다"가 아니라 왜 그런 결과가 나왔는지 근거를 남기려 했습니다.

### 1. 하이브리드 서치가 효과 없어 보였던 이유

`overrideSearchType=HYBRID`로 바꿔도 `SEMANTIC`과 결과가 거의 동일해서
"하이브리드가 안 먹힌다"고 오판할 뻔했습니다. 원인을 찾기 위해 테스트
질의를 바꿔가며 확인한 결과, **질의에 이미 압도적으로 유사한 문서가
있으면(벡터 점수 격차가 크면) 키워드 매칭 보너스가 순위에 드러나지
않는다**는 걸 확인했습니다. 문서 본문에만 있는 고유 키워드로 질의를
바꾸자 차이가 명확히 드러났습니다.

```
질의: "후원 부용지 연경당"
  SEMANTIC : 창덕궁이 상위 5위 안에도 없음
  HYBRID   : 창덕궁이 1위로 올라옴 (본문의 고유 키워드가 매칭 보너스로 작용)
```

→ 결론: 하이브리드 서치의 효과는 **질의 특성에 의존**한다. 일반적인
자연어 질의보다 정확한 고유명사·숫자가 포함된 질의에서 재현율이
뚜렷하게 개선된다.

### 2. Cohere Rerank가 AWS Marketplace 정책으로 차단됐던 사례

`bedrock:Rerank`를 호출했는데 계속 `AccessDeniedException`이 발생해서,
IAM 정책 시뮬레이터로 원인을 특정했습니다.

```bash
aws iam simulate-principal-policy \
  --policy-source-arn <role-arn> \
  --action-names "aws-marketplace:Subscribe" "aws-marketplace:ViewSubscriptions"
# → 두 액션 모두 explicitDeny (조직 SCP 레벨 차단)
```

Cohere Rerank는 AWS Marketplace의 서드파티 모델이라 구독 검증 액션이
필요한데, 계정 조직 정책(SCP)에서 이를 명시적으로 막고 있었습니다.
`AdministratorAccess`를 가진 역할로도 동일하게 막혀서, IAM 정책을
더 준다고 해결되는 문제가 아니라는 걸 확인했습니다.

→ 대응: `03_rerank_search.py`에 Cohere를 먼저 시도하고, 권한 오류가
나면 **Claude를 리랭커로 활용하는 LLM 기반 폴백**으로 자동 전환하도록
구현했습니다. (질의, 후보 문서) 쌍의 관련도를 0~10점으로 채점하게 해
Cross-encoder 리랭커와 같은 원리를 LLM 프롬프트로 재현한 방식입니다.

### 3. 관리형 서비스 역할에 필요한 최소 권한 구성

KB 실행 역할에는 아래 세 가지만 부여했습니다 (실제 ARN은 계정별로
달라 아래는 형태만 예시입니다):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "InvokeEmbeddingModel",
      "Effect": "Allow",
      "Action": "bedrock:InvokeModel",
      "Resource": "arn:aws:bedrock:<region>::foundation-model/amazon.titan-embed-text-v2:0"
    },
    {
      "Sid": "ReadDataSource",
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:ListBucket"],
      "Resource": ["arn:aws:s3:::<bucket>", "arn:aws:s3:::<bucket>/*"],
      "Condition": { "StringEquals": { "aws:ResourceAccount": "<account-id>" } }
    },
    {
      "Sid": "OpenSearchServerlessAccess",
      "Effect": "Allow",
      "Action": "aoss:APIAccessAll",
      "Resource": "arn:aws:aoss:<region>:<account-id>:collection/*"
    }
  ]
}
```

임베딩 모델은 특정 모델 ARN으로 좁히고, S3는 `aws:ResourceAccount`
조건으로 타 계정 버킷 접근을 막았습니다.

### 4. S3 이벤트 → Lambda 동기화의 동시 실행 방지

여러 파일을 한꺼번에 업로드하면 S3 이벤트가 파일 수만큼 발생해
`start_ingestion_job`이 중복 호출될 수 있습니다. Bedrock은 데이터
소스당 동시에 하나의 ingestion job만 허용하므로, Lambda 핸들러에서
`list_ingestion_jobs`로 `STARTING`/`IN_PROGRESS` 상태의 job이 있는지
먼저 확인하고, 있으면 새로 시작하지 않고 건너뛰도록 처리했습니다
(`lambda/lambda_function.py`).

### 5. Python 3.14 환경에서 Streamlit 설치 실패

`streamlit`의 의존성인 `pyarrow`가 Python 3.14용 사전빌드 wheel을
아직 제공하지 않아, 소스 빌드 중 `cmake` 부재로 실패했습니다.
Python 3.12로 별도 가상환경을 구성해 해결했습니다 — 최신 버전이
항상 최선의 선택은 아니라는 걸 실습으로 확인한 사례입니다.

## 구성

```
travel-kb-ko/
  destinations/     # 관광지 안내문 (.txt)
  metadata/          # Bedrock KB 메타데이터 (.metadata.json)

setup_01_upload_data.py   # S3 버킷 생성 + 데이터 업로드
setup_02_create_kb.py     # KB + OpenSearch Serverless 벡터스토어 생성/동기화
setup_03_query_kb.py      # RetrieveAndGenerate 기본 동작 확인

01_filter_search.py       # 메타데이터 필터 (equals / stringContains / andAll / orAll)
02_hybrid_search.py       # 시맨틱 vs 하이브리드 서치 비교
03_rerank_search.py       # 리랭킹 (Cohere Rerank v3.5, 실패 시 LLM 리랭커 폴백)
04_compare_all.py         # 동일 질의로 4가지 기법 종합 비교

05_setup_auto_sync.py     # S3 이벤트 + Lambda로 KB 자동 동기화 구축
06_verify_autosync.py     # 자동 동기화 동작 검증

lambda/lambda_function.py # S3 이벤트 트리거 Lambda 핸들러

app.py                    # Streamlit 대화형 추천 챗봇 (라이트/다크 모드)
```

## 실행 방법

### 0. 사전 준비

```bash
python3.12 -m venv .venv312
.venv312/bin/pip install -r requirements.txt
aws configure   # 또는 SSO 임시 자격 증명 설정
```

> Python 3.14는 `streamlit` 의존성인 `pyarrow`의 사전빌드 wheel이 없어
> 설치가 실패할 수 있습니다. 3.12를 권장합니다.

### 1. KB 구축

```bash
.venv312/bin/python setup_01_upload_data.py
.venv312/bin/python setup_02_create_kb.py
.venv312/bin/python setup_03_query_kb.py
```

`setup_02_create_kb.py` 실행 후 `kb_info.json`이 생성됩니다
(`knowledgeBaseId`, `dataSourceId`, `bucket` 등 계정별 값이 담겨 있어
`.gitignore`에서 제외했습니다).

### 2. 검색 품질 개선 실험

```bash
.venv312/bin/python 01_filter_search.py
.venv312/bin/python 02_hybrid_search.py
.venv312/bin/python 03_rerank_search.py
.venv312/bin/python 04_compare_all.py
```

### 3. 자동 동기화 구축

```bash
.venv312/bin/python 05_setup_auto_sync.py
.venv312/bin/python 06_verify_autosync.py
```

### 4. 챗봇 실행

```bash
.venv312/bin/streamlit run app.py
```

## 검증 결과 요약

동일 질의 **"서울에서 반나절 역사 코스"** 기준, 상위 3개 중 역사 관련
관광지 비율:

| 기법 | 비율 | 비고 |
|---|---|---|
| 기본 검색 | 1/3 | 벡터 점수가 촘촘히 붙어 무관한 문서가 상위 진입 |
| 메타데이터 필터 | 3/3 | 정밀도 최고, 필터 밖 후보는 원천 배제 |
| 하이브리드 서치 | 1/3 | 이 질의에서는 개선 없음 (고유 키워드 부재) |
| 리랭킹 (Cohere Rerank v3.5) | 2/3 | 필터처럼 자르지 않고 의미 기반으로 재배치 |

자동 동기화 파이프라인 검증: S3에 신규 문서 업로드 → Lambda가 자동으로
`start_ingestion_job` 실행 → 약 45초 내 벡터 검색에 반영 확인.

## 참고 사항

- **자격 증명**: 이 리포지토리에는 AWS 자격 증명, 계정 ID, 리소스 ID가
  포함되어 있지 않습니다. `aws configure` 또는 SSO로 로컬에 설정해서
  사용하세요. `kb_info.json`(계정별 KB ID·버킷명)은 `.gitignore`로
  제외되어 있으며, 실행 시 자동으로 생성됩니다.
- **비용**: OpenSearch Serverless 벡터 컬렉션은 최소 OCU가 상시
  과금됩니다. 실습이 끝나면 콘솔 또는 CLI로 컬렉션·KB·Lambda를
  삭제하는 것을 권장합니다.
- **리랭킹**: Cohere Rerank는 AWS Marketplace 서드파티 모델이라 계정
  정책에 따라 `aws-marketplace:Subscribe` 권한이 필요합니다. 막힐 경우
  `03_rerank_search.py`가 자동으로 LLM 기반 리랭커로 대체합니다.
