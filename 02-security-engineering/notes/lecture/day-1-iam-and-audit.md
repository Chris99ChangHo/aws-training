# Day 1 — 보안 기초, IAM, 감사 로그

> 교육일: 2026-07-22
> AWS 공식 문서 확인일: 2026-07-31
> 범위: 공동 책임 모델, IAM, 조직 거버넌스의 기초, 감사·탐지 서비스

## 학습 목표

- AWS와 고객의 책임 경계를 서비스 특성에 맞게 설명한다.
- 사람·워크로드·교차 계정 접근에 맞는 IAM 인증 방식을 선택한다.
- API 활동, 리소스 구성 변경, 보안 조사에 쓰는 서비스를 구분한다.

> 이 노트는 GPT-5.6과 함께 정리했습니다. 원 강의 내용을 바탕으로 AWS 공식
> 문서와 대조해 오개념을 짚고 사실을 재확인했으며, 정리 방향과 최종 내용은
> 사람이 검토·승인했습니다.

## 1. 공동 책임 모델과 방어 계층

AWS는 클라우드 **자체의 보안**(물리 시설, 하드웨어, 기반 인프라)을 책임지고,
고객은 클라우드 **내 보안**(데이터, IAM, 네트워크 구성, 운영체제와 애플리케이션
패치 등)을 책임진다. 고객 책임의 범위는 EC2, RDS, S3처럼 서비스마다 다르다.
이는 가격이나 서비스를 한 줄로 나열해 비교할 수 있는 문제가 아니다.

보안 설계는 한 서비스에 의존하지 않고 다음 계층을 함께 적용한다.

1. **예방**: 최소 권한 IAM, MFA, 네트워크 분리, 안전한 기본 구성
2. **탐지**: CloudTrail, AWS Config, GuardDuty, Security Hub
3. **대응·복구**: 경보, 런북, 격리, 백업·복구, 사후 개선

완벽한 차단을 전제하기보다 공격 성공 가능성과 영향을 줄이는 **완화(mitigation)**
관점으로 설계한다. 애플리케이션도 예외가 아니므로, OWASP Top 10 같은 기준으로
입력 검증·인증·권한 부여·비밀 관리·의존성 관리를 개발 과정에 포함하는
DevSecOps가 필요하다.

## 2. 계정, 루트 사용자, 다중 계정

- AWS 계정마다 **루트 사용자(root user)는 하나**다. 조직의 최상위에 별도
  자격 증명을 가진 “루트의 루트” 사용자가 생기는 구조가 아니다.
- 루트 사용자는 일상 운영에 쓰지 않는다. MFA를 적용하고, 복구·결제처럼 루트만
  가능한 작업에만 사용한다.
- AWS Organizations는 여러 AWS 계정을 중앙에서 관리한다. 계정은
  워크로드·환경·팀·보안 경계에 따라 분리할 수 있고, 각 계정은 자체 루트 사용자를
  계속 가진다.
- 관리 계정은 거버넌스에만 쓰고, 일상 워크로드는 멤버 계정에 둔다. 보안 서비스의
  중앙 운영은 가능한 경우 위임 관리자 계정에 맡긴다.

**OU(organizational unit)** 는 계정을 묶어 거버넌스 정책을 적용하는 단위다.
IAM 그룹과 동일하지 않다. **SCP(service control policy)** 는 권한을 *부여*하는
IAM 정책이 아니라 계정·OU에 허용 가능한 최대 권한을 제한하는 가드레일이다.
명시적 `Deny`는 `Allow`보다 항상 우선한다. 실제 접근 결과는 IAM 정책, 리소스
기반 정책, 권한 경계, 세션 정책 등도 함께 평가하므로 단순한 고정 순서로 외우지
않는다.

## 3. IAM: 인증과 권한 부여

### 원칙

- 기본값은 묵시적 거부다. 필요한 작업만 허용하는 **최소 권한**을 적용한다.
- 장기 액세스 키보다 IAM 역할(role)의 **임시 자격 증명**을 우선한다.
- 사람의 AWS 접근은 AWS IAM Identity Center와 외부 IdP 연동을 우선 검토한다.
  로그인 횟수 자체가 위험을 결정하지 않는다. MFA, 세션 수명, 조건부 접근,
  감사 로그와 계정 복구 절차를 함께 설계한다.
- MFA 중에서도 패스키 같은 피싱 저항 인증 방식은 원본(origin)에 묶여 동작한다.
  OTP는 사용자가 피싱 사이트에 코드를 입력하면 중계될 수 있다.

### 정책과 역할

| 구성 요소 | 역할 | 핵심 주의점 |
|---|---|---|
| 자격 증명 기반 정책 | 사용자·그룹·역할에 허용 권한 부여 | 최소 권한으로 작성 |
| 리소스 기반 정책 | S3 버킷, KMS 키 등 리소스에 접근 주체 명시 | 명시적 거부와 전체 정책 평가를 고려 |
| 권한 경계 | IAM 자격 증명 기반 정책이 넘지 못할 최대 권한 정의 | 권한을 부여하지 않음 |
| 세션 정책 | 역할 세션 등에 적용하는 추가 제한 | 임시 세션의 범위를 축소 |
| 역할 신뢰 정책 | 누가 역할을 Assume할 수 있는지 정의 | 권한 정책과 별도로 필수 |

**역할**은 AWS 서비스, 다른 AWS 계정, 또는 연동된 IdP 사용자가 맡을 수 있다.
교차 계정 접근은 대상 계정의 역할 신뢰 정책과 호출 주체의 `sts:AssumeRole` 권한을
함께 요구한다. 역할 세션 시간이 항상 1시간인 것은 아니다. 역할 연쇄(role
chaining)는 최대 1시간이라는 제약이 있지만, 직접 역할을 맡는 세션은 역할 설정과
호출 방식에 따른 범위에서 더 길게 설정할 수 있다.

SAML 2.0은 기업 IdP와 서비스 제공자 간에 쓰이는 표준 federation 프로토콜 중
하나다. federation은 외부 자격 증명을 AWS 자격 증명으로 연계하는 방식이며,
AWS에서는 그 결과로 STS 임시 자격 증명을 받는 경우가 일반적이다. CLI·SDK도 IAM
Identity Center 또는 역할 자격 증명을 사용할 수 있으므로, IAM 사용자 액세스 키가
필수는 아니다.

### 태그 기반 접근 제어

태그는 리소스와 주체에 붙이는 메타데이터이고, 조건은 정책 평가 논리다.
정책 조건에서 태그 키를 사용하면 ABAC(attribute-based access control)를 구현할 수
있다. 예를 들어 `Project` 태그가 같은 역할과 리소스만 접근하도록 제한할 수 있다.
태그 그 자체가 권한 조건은 아니다.

## 4. 감사, 구성 관리, 위협 탐지

| 서비스 | 주된 질문 | 정리 |
|---|---|---|
| AWS CloudTrail | 누가 언제 어떤 AWS API를 호출했는가? | 이벤트 기록과 감사 |
| AWS Config | 리소스 구성이 어떻게 바뀌었고 규칙을 준수하는가? | 구성 이력·규정 준수 평가 |
| Amazon CloudWatch | 지표·로그·경보가 임계값을 넘었는가? | 운영 모니터링과 알림 |
| Amazon Inspector | 지원 리소스·컨테이너·Lambda·코드의 취약점은 무엇인가? | 취약점 관리 |
| Amazon GuardDuty | 계정·워크로드에서 의심스러운 활동이 있는가? | 위협 탐지 |
| AWS Security Hub | 여러 보안 서비스의 결과와 보안 표준 상태는 어떤가? | 보안 태세 집계·우선순위화 |
| Amazon Detective | 수집된 보안 데이터를 바탕으로 사건을 어떻게 조사할까? | 조사·분석 |

CloudTrail **Event history** 는 별도 설정 없이 현재 리전의 관리 이벤트를 최근
90일 동안 제공한다. 영구 보관, 데이터 이벤트, Insights 이벤트, 여러 계정·리전의
중앙 수집이 필요하면 trail을 만들고 S3에 전달한다. trail에는 다중 리전, 로그 파일
무결성 검증, 적절한 S3 버킷 정책·보존 기간을 검토한다.

AWS Config는 리소스 구성을 기록하고 규칙으로 평가한다. 예를 들어 태그·공개 접근
같은 규칙 위반을 찾아낼 수 있지만, Config만으로 리소스 생성을 자동 차단하는
서비스는 아니다. 생성 자체를 막는 예방 통제는 SCP, IAM, 서비스 정책 등과 별도로
설계한다.

## 5. 서버리스와 애플리케이션 보안

AWS Lambda는 요청 또는 이벤트에 반응해 코드를 실행하는 서버리스 컴퓨팅 서비스다.
적합한 워크로드에서는 서버 관리 부담을 줄이지만, EC2를 항상 대체하는 서비스는
아니다. 단일 호출은 최대 15분이며, 장시간 처리·특수 런타임·상시 연결 요구사항은
ECS/Fargate, AWS Batch, EC2 등을 검토한다. Lambda 함수에는 전용 실행 역할을
부여해 필요한 AWS API만 허용한다.

전형적인 웹 3계층은 다음처럼 역할을 분리한다.

```text
Internet → CloudFront/WAF → Load Balancer → Web/App → Database
```

실제 구성은 워크로드에 따라 달라지며, 각 계층의 IAM·네트워크·암호화·로그·패치
책임을 분명히 해야 한다.

## 복습 체크

- [ ] 루트 사용자의 일상 사용을 막고 MFA·복구 절차를 마련했는가?
- [ ] 사람·워크로드·교차 계정 접근에 역할과 임시 자격 증명을 우선하는가?
- [ ] CloudTrail trail, Config, GuardDuty, Security Hub의 목적을 구분하는가?
- [ ] 명시적 거부와 SCP가 권한을 제한한다는 점을 설명할 수 있는가?

## 확인하지 못한 것

이 과정은 **리포에 실습이 없다.** 실습에서 파생된 작업물은 벤더 독립 보안
에이전트로 분리해 [`agents/security/`](../../../agents/security)에 있고, 그쪽은
별도로 검증된다. 따라서 아래 노트는 **강의 내용을 AWS 공식 문서와 대조한
것까지**이고, 직접 실행해 확인한 것이 아니다.

구체적으로 실행하지 않은 것:

- SCP로 계정 권한이 실제로 제한되는지 (조직 계정이 필요하다)
- CloudTrail trail 생성과 로그 파일 무결성 검증
- GuardDuty·Security Hub·Detective의 실제 탐지 결과
- 권한 경계·세션 정책이 겹칠 때의 실제 평가 결과. 정책 평가 논리는 문서로만
  확인했고, IAM 정책 시뮬레이터로 재현하지 않았다

## 공식 자료

- [AWS 공동 책임 모델](https://aws.amazon.com/compliance/shared-responsibility-model/)
- [AWS Organizations의 SCP와 IAM 정책](https://repost.aws/knowledge-center/iam-policy-service-control-policy)
- [IAM 역할](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles.html)
- [IAM 정책 평가 논리](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_evaluation-logic.html)
- [CloudTrail 보안 모범 사례](https://docs.aws.amazon.com/awscloudtrail/latest/userguide/best-practices-security.html)
- [CloudTrail Event history](https://docs.aws.amazon.com/awscloudtrail/latest/userguide/tutorial-event-history.html)
- [AWS Config와 CloudTrail의 역할 구분](https://aws.amazon.com/blogs/mt/how-to-use-aws-config-and-cloudtrail-to-find-who-made-changes-to-a-resource/)
- [AWS Security Reference Architecture — 감사·보안 서비스](https://docs.aws.amazon.com/prescriptive-guidance/latest/security-reference-architecture/phases.html)
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
