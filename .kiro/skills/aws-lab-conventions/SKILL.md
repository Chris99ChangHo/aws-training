---
name: aws-lab-conventions
description: AWS 실습·랩 폴더를 만들거나 그 안의 스크립트(Bedrock, IAM, S3, OpenSearch 등 리소스를 생성·조회하는 boto3 코드)를 작성할 때 사용한다. 폴더 구조와 실행 순서 규칙, 환경별 식별자 처리, 멱등성, put_role_policy 덮어쓰기 함정. "실습 폴더 만들어줘", "KB 생성 스크립트 짜줘", "이 스크립트 재실행해도 되나" 같은 요청에 해당한다.
---

# AWS 실습 규약

`<과정명>/<실습명>/`과 `labs/<랩명>/`에 적용된다. 아래는 이 리포에서 실제로
깨져서 규칙으로 남긴 것들이다. `agents/`(벤더 독립 축)에는 적용하지 않는다 —
그쪽은 `agent-conventions` 스킬을 쓴다.

## 실습 폴더 규칙

- **독립 실행 가능해야 한다.** 자체 `README.md`와 `requirements.txt`를 갖고,
  다른 실습 폴더를 참조하지 않는다.
- 스크립트는 실행 순서를 파일명 앞 숫자로 표현한다(`01_`, `02_`...).
  인프라 구축 단계와 실험 단계를 구분해야 하면 구축 쪽에 접두어를 붙인다
  (`setup_01_`, `setup_02_`).
- 각 스크립트는 완료 기준을 자체 검증하고 **종료 코드로 성공/실패를 알린다.**
- README에 담을 내용은 `readme-audit` 스킬의 6항목을 따른다.

## 환경별 식별자 하드코딩 금지

AWS 계정 ID, 리소스 ID, 버킷명처럼 환경마다 달라지는 값은 코드에 박지 않고
런타임에 조회하거나 설정 파일에서 읽는다.

```python
account_id = boto3.client("sts", region_name=REGION).get_caller_identity()["Account"]
model_arn = f"arn:aws:bedrock:{REGION}:{account_id}:inference-profile/{MODEL_ID}"
```

**이유**: 공개 리포에 계정 ID가 노출되고, 다른 계정에서 재현이 불가능해진다.
커밋 전 점검 항목은 `git-conventions.md`에 있다.

생성된 리소스 ID를 다음 스크립트에 넘겨야 하면 `kb_info.json`처럼 파일로
떨어뜨리고 `.gitignore`에 넣는다. 파일 경로는 스크립트 위치 기준으로
해석한다(`python-conventions.md`).

## 멱등성

인프라를 생성하는 스크립트는 여러 번 실행해도 안전하게 만든다. 이미 존재하면
재사용하고, 없으면 생성한다.

```python
try:
    resp = client.create_role(RoleName=name, ...)
except client.exceptions.EntityAlreadyExistsException:
    resp = client.get_role(RoleName=name)
```

**이유**: 실습 중 스크립트를 중간에 취소하거나 재실행하는 일이 잦다. 멱등하지
않으면 매번 리소스를 수동으로 정리해야 한다.

## `put_role_policy`는 항상 전체를 덮어쓴다

`create_role`은 존재 확인 분기를 넣기 쉽지만, IAM 인라인 정책을 넣는
`put_role_policy`는 create가 아니라 **upsert**라서 호출할 때마다 정책 전체를
통째로 교체한다.

스크립트 밖에서 `put_role_policy`로 권한을 임시로 추가해 둔 상태에서
스크립트를 그대로 재실행하면, 그 임시 권한이 스크립트에 정의된 원래 정책으로
되돌아가며 사라진다.

실제 재현: restaurant-concierge-rag 실습에서 별도로 추가한 `bedrock:Rerank`
권한이 `setup_02_create_kb.py` 재실행 한 번으로 사라져 리랭킹 스크립트가 다시
깨졌다.

→ 필요한 권한은 **처음부터 스크립트의 정책 정의 자체에 포함시킨다.** "일단
콘솔/CLI로 임시로 추가하고 나중에 코드에 반영하자"는 접근은 재실행 시 그대로
되돌아간다.

## 리전에 없는 모델은 "권한 없음"이 아니라 "식별자 무효"로 나온다

Bedrock은 해당 리전 카탈로그에 없는 `modelId`를 "그 리전에 없다"가 아니라
`ValidationException: The provided model identifier is invalid`로 응답한다.
모델 액세스 미승인처럼 보이므로 권한 문제로 오인하기 쉽다.

먼저 카탈로그를 조회해서 리전에 그 모델이 있는지 확인한다.

```bash
aws bedrock list-foundation-models --region <리전> \
  --query "modelSummaries[].modelId" --output text | tr '\t' '\n' | grep <모델>
```

실측 예: `amazon.nova-canvas-v1:0`·`amazon.nova-reel-v1:0`은 `us-east-1`에만
있고 `us-west-2`에는 없다(labs/invoke-model).

## 비용

상시 과금되는 리소스(Knowledge Base, OpenSearch 컬렉션, 엔드포인트 등)를
만드는 실습은 README에 명시하고, 정리 스크립트나 정리 절차를 함께 남긴다.
현재 단가는 문서에 적지 않고 AWS 요금 페이지를 참조하게 한다 — 적어두면
낡는다.
