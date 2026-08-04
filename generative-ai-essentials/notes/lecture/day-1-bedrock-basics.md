# Day 1 — AWS 컴퓨팅 기초와 Bedrock 인증

> 교육일: 2026-07-27
> AWS 공식 문서 확인일: 2026-07-31
> 범위: 인스턴스형·서버리스 과금 모델, IAM 기초, Bedrock 인증 방식, RAG의 시맨틱 검색

표기 규칙: `[문서]` AWS 공식 문서 인용(링크 있음) · `[해석]` 문서를 놓고 내린
판단. 수업 필기 원본은 별도 문서(Google Docs)로 관리한다.

## 학습 목표

- 인스턴스 기반 과금과 서버리스 과금의 차이를 설명한다.
- IAM의 user·group·policy·role 구조와 콘솔/CLI/SDK 접근 경로를 구분한다.
- Bedrock 런타임 인증 방식(SigV4 vs API 키)의 차이와 각각의 용도를 안다.
- Bedrock Inference profiles의 두 종류(시스템 정의·애플리케이션)와 용도를
  구분한다.
- 시맨틱 검색이 키워드 검색과 다른 지점을 설명한다.

## 1. 인스턴스형 vs 서버리스: 두 가지 과금 모델

`[해석]` AWS 서비스를 쓸 때 비용이 발생하는 시점은 크게 두 갈래다.

- **인스턴스형(예: EC2)**: 프로비저닝한 리소스가 **켜져 있는 동안** 과금된다.
  실제로 요청을 처리하는지와 무관하게, `running` 상태면 비용이 든다.
- **서버리스(예: Lambda, DynamoDB on-demand)**: **사용한 만큼만** 과금된다.
  요청이 없으면 비용도 없다.

`[해석]` 이 구분은 아키텍처 선택의 출발점이다. 트래픽이 일정하고 예측 가능하면
인스턴스형이 유리할 수 있고, 트래픽이 간헐적이거나 예측 불가능하면 서버리스가
유리할 수 있다. 실제 비용은 워크로드 패턴에 따라 달라지므로 일반화된 "항상
서버리스가 싸다"는 결론은 내리지 않는다.

### 평가는 모델·RAG·에이전트를 따로 한다

`[해석]` 생성형 AI 애플리케이션은 모델만 단독으로 쓰는 경우가 드물고, 검색
(RAG)이나 도구 호출(에이전트)까지 포함한 하네스와 함께 배포되는 경우가
많다. 그래서 평가도 계층별로 나뉜다 — 모델 자체의 응답 품질, RAG의 검색·
생성 품질, 에이전트의 도구 선택·작업 완료율은 각각 다른 지표와 방법으로
평가한다. "모델을 평가한다"는 말이 전체 애플리케이션을 평가했다는 뜻이
아니다 — 하네스(검색·도구·오케스트레이션)가 성능에 크게 기여하므로 하네스
자체도 평가 대상이 된다.

## 2. IAM: 인증의 기본 단위

`[문서]` IAM의 핵심 구성요소는 다음과 같다.

- **User**: 사람 또는 애플리케이션을 나타내는 자격 증명.
- **Group**: user를 묶어 정책을 한 번에 적용하는 단위.
- **Policy**: 어떤 작업을 허용/거부할지 정의하는 JSON 문서.
- **Role**: 자격 증명이 아니라 **임시로 맡는 권한 집합**. AWS 서비스, 다른
  계정, 연동된 ID 제공자가 assume할 수 있다.

`[해석]` 클라우드 컴퓨팅은 근본적으로 **가상화**다 — 적은 물리 자원을 많은
논리 자원처럼 보이게 하거나(멀티테넌시), 반대로 여러 물리 자원을 하나의
논리 단위로 묶는다. EC2는 전자의 대표적인 예(가상 머신)다. 가상화된 자원을
소프트웨어처럼 다루려면 API 호출이 필요하고, 그 호출을 인증·인가하는 계층이
IAM이다.

접근 경로는 세 가지로 나뉜다 — **AWS Management Console**(사람이 브라우저로),
**AWS CLI**(터미널), **SDK**(코드에서, 예: Python의 `boto3`). 셋 다 최종적으로는
같은 IAM 자격 증명 체계를 거친다.

## 3. Bedrock 런타임 인증: SigV4와 API 키

`[문서]` Bedrock Runtime(InvokeModel, Converse API 등)을 호출하는 기본 인증
방식은 **SigV4**(AWS의 표준 요청 서명 방식)이며, IAM 자격 증명(user, role)을
기반으로 서명이 생성된다. ([Bedrock Runtime 예제](https://docs.aws.amazon.com/bedrock/latest/userguide/bedrock-runtime_example_bedrock-runtime_Converse_AmazonNovaText_section.html))

`[문서]` 이와 별도로 Bedrock은 **API 키** 인증을 지원한다.
([API 키 참조](https://docs.aws.amazon.com/bedrock/latest/userguide/api-keys-reference.html))

| 키 종류 | 유효 기간 | 특징 |
|---|---|---|
| 단기(short-term) | 세션 길이 또는 최대 12시간 | 발급한 IAM 주체의 권한을 그대로 상속. 발급한 리전에서만 사용 가능 |
| 장기(long-term) | 사용자가 지정 | 내부적으로 전용 IAM 사용자를 생성. AWS는 **탐색·실험 용도로만** 권장하며, 프로덕션에서는 단기 자격 증명으로 전환할 것을 권고 |

`[문서]` API 키는 Bedrock/Bedrock Runtime 작업에만 쓸 수 있고,
`InvokeModelWithBidirectionalStream`이나 Agents for Bedrock API에는 쓸 수 없다.

`[해석]` 필기의 "베드락 멘틀은 API 키를 쓴다"는 실제로 근거가 있다. `[문서]`
**Bedrock Mantle**(`bedrock-mantle` 엔드포인트)은 AWS가 새로 도입한 분산
추론 엔진으로, OpenAI/Anthropic API와 호환되는 형태로 Bedrock 모델을 호출할 수
있게 한다. 이 엔드포인트는 SigV4와 API 키 인증을 **둘 다** 지원한다.
([Chat Completions 문서](https://docs.aws.amazon.com/bedrock/latest/userguide/inference-chat-completions-mantle.html))

`[해석]` 다만 "런타임(SigV4 방식)이 사라질 수도 있다"는 예측은 현재 시점
공식 문서로 확인되지 않는다. 확인되는 것은 **API 키가 기존 SigV4 인증을
대체하는 것이 아니라 병행 제공**된다는 점이다. Bedrock Runtime의 기존 SigV4
경로가 폐기(deprecate)된다는 공지는 찾지 못했다. 이 부분은 강의에서 나온
추측으로 남겨두고, 프로덕션 설계 시에는 AWS가 명시적으로 권고하는 대로
단기 자격 증명(IAM 역할) 우선을 기본값으로 삼는다.

## 4. Bedrock Inference profiles

`[문서]` Inference profile은 모델과 그 모델이 요청을 라우팅할 수 있는 하나
이상의 리전을 정의한다. 크게 두 종류가 있다.

- **시스템 정의(system-defined) 프로파일**: AWS가 미리 만들어 둔 것으로,
  Cross-Region Inference에 쓴다 — 하나의 리전에서 온 요청을 여러 리전의
  컴퓨트로 분산해 처리량과 복원력을 높인다. 요청을 보낼 소스 리전과, 그
  요청이 실제로 라우팅될 수 있는 대상 리전들을 정의한다. 이 프로파일은
  또다시 **리전(geographic) 단위**와 **글로벌 단위**로 나뉜다 — 필기의
  "리전, 글로벌추론프로파일 두 가지"가 이 구분에 대응한다.
- **애플리케이션(application) 프로파일**: 사용자가 직접 만드는 프로파일로,
  비용·사용량을 추적하기 위한 용도다. 단일 리전용으로 만들 수도 있고,
  시스템 정의 Cross-Region 프로파일을 감싸서 여러 리전에 걸친 사용량을
  하나로 추적할 수도 있다. API로만 생성할 수 있다.

`[해석]` 필기의 "시스템적인게 있고 내가 작성할 수도 있다"는 이 두 종류의
구분과 정확히 대응한다 — 시스템 정의는 AWS가 만든 것(Cross-Region 라우팅),
애플리케이션은 사용자가 만든 것(비용 추적)이다.

## 5. RAG의 시맨틱 검색

`[해석]` RAG(Retrieval-Augmented Generation)에서 벡터 데이터베이스 검색은
**시맨틱 검색**이다. 이는 검색어의 정확한 문자열이 일치하는지를 보는
키워드 검색(예: 전통적인 웹 검색의 기본 방식)과 다르다 — 질의와 문서를
임베딩 모델로 벡터화한 뒤, 벡터 공간에서 **의미적으로 가까운** 문서를 찾는다.

AWS에서 이 벡터 저장·검색을 관리형으로 제공하는 서비스가 **Amazon Bedrock
Knowledge Bases**다. 시맨틱 검색의 구체적인 동작과 한계(같은 도메인 문서가
많을 때 벡터 점수가 촘촘해지는 문제 등)는 이 리포의
[`rag-retrieval-tuning.md`](../practice/rag-retrieval-tuning.md)에서 실측 데이터로 더
깊이 다룬다.

## 복습 체크

- [ ] 인스턴스형과 서버리스 과금의 차이를 설명할 수 있는가?
- [ ] IAM user/group/policy/role의 역할을 구분하는가?
- [ ] Bedrock SigV4 인증과 API 키 인증의 용도 차이를 설명할 수 있는가?
- [ ] 장기 API 키를 프로덕션에 쓰면 안 되는 이유를 아는가?
- [ ] 시스템 정의 Inference profile과 애플리케이션 Inference profile의
      용도 차이를 설명할 수 있는가?
- [ ] 시맨틱 검색과 키워드 검색의 차이를 설명할 수 있는가?

## 확인하지 못한 것

- "Bedrock Runtime의 SigV4 인증이 향후 폐기될 수 있다"는 강의 중 발언은 공식
  문서·릴리스 노트에서 근거를 찾지 못했다. 현재 확인되는 사실은 API 키가
  SigV4와 **병행** 제공된다는 것뿐이다.

## 공식 자료

- [Amazon Bedrock API 키 동작 방식](https://docs.aws.amazon.com/bedrock/latest/userguide/api-keys-how.html)
- [Amazon Bedrock API 키 참조](https://docs.aws.amazon.com/bedrock/latest/userguide/api-keys-reference.html)
- [Bedrock Mantle Chat Completions API](https://docs.aws.amazon.com/bedrock/latest/userguide/inference-chat-completions-mantle.html)
- [Bedrock API 키 GA 발표 (2025-07)](https://aws.amazon.com/about-aws/whats-new/2025/07/amazon-bedrock-api-keys-for-streamlined-development/)
- [Bedrock Inference profiles](https://docs.aws.amazon.com/help-panel/bedrock/latest/console/hp-inference-profiles.html)
- [Increase throughput and resilience with cross-region inference](https://docs.aws.amazon.com/bedrock/latest/userguide/geographic-cross-region-inference.html)
- [IAM이란?](https://docs.aws.amazon.com/IAM/latest/UserGuide/introduction.html)
- [Amazon Bedrock Knowledge Bases란?](https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base.html)
