# Day 2 — 거버넌스, 암호화, 데이터 보호

> 교육일: 2026-07-23
> AWS 공식 문서 확인일: 2026-07-31
> 범위: 다중 계정 거버넌스, KMS와 비밀 관리, S3·데이터베이스 보호

## 학습 목표

- AWS Organizations와 Control Tower의 역할을 구분한다.
- KMS, Secrets Manager, Parameter Store의 책임 범위를 설명한다.
- S3·RDS·DynamoDB·EBS의 보안·복구·비용 선택지를 구분한다.

> 이 노트는 GPT-5.6과 함께 정리했습니다. 원 강의 내용을 바탕으로 AWS 공식
> 문서와 대조해 오개념을 짚고 사실을 재확인했으며, 정리 방향과 최종 내용은
> 사람이 검토·승인했습니다.

## 1. 다중 계정 거버넌스

AWS Organizations는 계정·OU·SCP를 이용해 조직 전체의 거버넌스 경계를 만든다.
SCP는 멤버 계정의 IAM 권한이 넘을 수 없는 최대 권한을 정의하며, 권한 자체를
부여하지 않는다. 관리 계정에는 SCP가 적용되지 않는다. 따라서 보안 운영 계정과
로그 보관 계정, 워크로드 계정을 분리하고, 공통 가드레일은 OU에 적용한다.

AWS Control Tower는 다중 계정 환경을 위한 관리형 랜딩 존과 거버넌스 기능을
제공한다. 대기업 전용 서비스가 아니며, 규모와 규제 요구에 맞춰 채택을 판단한다.
이미 다른 Organizations에 속한 계정을 합병·이관할 때는 단순 연결로 끝나지
않는다. 계정 이동, 랜딩 존 등록, 로깅·가드레일·정책 충돌, 애플리케이션 영향을
검토하는 마이그레이션 작업이 필요하다.

권장하는 중앙 보안 운영 예시는 다음과 같다.

```text
Management account: Organizations·결제·거버넌스 관리
Log archive account: 변경 불가능한 중앙 로그 장기 보관
Security tooling account: Security Hub, GuardDuty, Config 등의 위임 관리자
Workload accounts: 개발·테스트·운영 워크로드 격리
```

## 2. 키, 비밀, 인증서

### AWS KMS와 봉투 암호화

AWS KMS는 암호화 키와 암호화 작업을 관리하는 서비스다. KMS 키에 대한 접근은
키 정책, IAM 정책, grant를 함께 고려해 제어한다. KMS 자체가 RDS 비밀번호를
저장하거나 회전하지는 않는다.

대량 데이터를 KMS 키로 직접 암호화하는 대신 **봉투 암호화(envelope encryption)**
를 사용한다.

1. 데이터 키로 실제 데이터를 암호화한다.
2. 데이터 키를 KMS 키로 암호화한다.
3. 암호문과 암호화된 데이터 키를 함께 저장한다.
4. 복호화 시 KMS 권한을 확인해 데이터 키를 복호화한 뒤 데이터를 복호화한다.

대칭 암호화가 본질적으로 안전하지 않아서가 아니라, 매번 KMS 키를 데이터 전체에
직접 적용하지 않으면서 키 사용을 통제·감사하기 위한 설계다. KMS 키를 삭제하면
해당 키로 암호화한 데이터를 복구할 수 없을 수 있다. 먼저 비활성화 영향부터
확인하고, 삭제가 필요하면 7~30일 대기 기간의 예약 삭제를 사용한다.

KMS 키는 리전별 리소스다. 그러나 적절한 대상 리전 키를 구성하면 교차 리전 복제와
복호화 설계가 가능하다. Multi-Region KMS keys는 서로 다른 리전에 존재하는 관련
키 쌍이며, 복제·재해 복구 설계의 요구사항과 권한을 별도로 검토해야 한다.

### Secrets Manager와 Parameter Store

| 서비스 | 적합한 용도 | 주의점 |
|---|---|---|
| AWS Secrets Manager | DB 자격 증명, API 키처럼 회전이 필요한 비밀 | 저장·API·회전 구성에 비용이 발생할 수 있음 |
| Systems Manager Parameter Store | 구성 값과 `SecureString` 비밀 값 | 표준·고급 티어와 KMS 사용 조건에 따라 비용·기능이 다름 |
| AWS KMS | 키 관리와 암호화 작업 | 애플리케이션 비밀 저장소가 아님 |

`.env` 파일은 로컬 개발에 유용할 수 있지만, 저장소·로그·배포 산출물에 포함되지
않도록 해야 한다. 운영 비밀은 코드나 이미지에 하드코딩하지 않고, 실행 시 역할로
인증해 비밀 저장소에서 가져온다. 비밀을 바꾸려면 애플리케이션의 재시작·연결 풀·
장애 조치 영향까지 포함해 회전 절차를 시험한다.

### TLS, ACM, CloudHSM

- **TLS**는 더 이상 안전하지 않은 SSL의 후속 프로토콜이다. HTTPS는 HTTP에 TLS를
  적용한 통신이다.
- AWS Certificate Manager(ACM)는 지원하는 통합 AWS 서비스에 연결하는 공개
  인증서를 제공한다. 공개 ACM 인증서 자체에는 별도 ACM 요금이 없을 수 있지만,
  연결한 서비스와 ACM Private CA는 별도 과금 대상이다.
- AWS CloudHSM은 고객이 제어하는 HSM 클러스터다. 일반적인 “AZ 인스턴스”가
  아니라 가용성을 위해 여러 AZ에 HSM을 배치하는 서비스이며, 지원 하드웨어의
  FIPS 140-2 Level 3 검증 범위를 공식 문서에서 확인해야 한다.

## 3. S3: 저장소가 아니라 데이터 레이크의 기반

Amazon S3는 객체 스토리지이며, 데이터 레이크의 저장 계층으로 자주 사용된다.
그러나 데이터 레이크 전체는 S3만으로 완성되지 않는다. 수집, 데이터 카탈로그,
거버넌스, 품질 관리, 분석·접근 제어까지 함께 설계해야 한다.

### 보안 기준선

- 새 S3 객체는 기본적으로 SSE-S3로 서버 측 암호화된다. 규정 준수·키 사용 감사가
  필요하면 SSE-KMS 또는 DSSE-KMS를 검토한다. SSE-C는 고객이 키를 직접 전달하고
  관리하므로 운영 부담이 크다.
- **Block Public Access**를 기본으로 두고, 공개가 꼭 필요하면 범위를 최소화한다.
- Object Ownership를 **Bucket owner enforced**로 설정해 ACL을 비활성화하는
  방식을 기본으로 검토한다. ACL은 버킷 ACL이 “최신”이라는 뜻이 아니라, 둘 다
  레거시 접근 제어 방식이다.
- 버킷 정책, IAM 정책, 액세스 포인트 정책을 최소 권한으로 조합한다. 액세스
  포인트는 애플리케이션·워크로드별 접근 정책과 네트워크 경계를 단순화하는
  엔드포인트이지, 사용자마다 반드시 하나씩 만드는 주소가 아니다.
- 버전 관리는 실수로 덮어쓰거나 삭제한 객체를 복구하는 데 도움이 된다. 복제는
  가용성·복구를 보완하지만, 삭제 마커와 원치 않는 변경도 복제될 수 있다.
  중요 데이터는 Object Lock의 보존 모드·법적 보존, 복구 절차, 접근 권한을 함께
  검토한다.

### 스토리지 클래스

스토리지 클래스의 “월 1회”, “분기 1회” 같은 문구는 접근 빈도 선택을 위한
휴리스틱일 뿐 사용 금지 규칙이 아니다. 최소 보관 기간, 검색 지연 시간, 검색·
전송 비용, 가용성 요구사항을 함께 비교한다.

- S3 Lifecycle은 선언한 날짜·조건에 맞춰 객체를 전환·만료한다. 갑자기 인기 있는
  객체를 자동으로 빠른 클래스에 올려 주는 기능은 아니다.
- S3 Intelligent-Tiering은 액세스 패턴이 불확실한 객체의 계층 이동을 자동화한다.
  전환 조건과 객체 크기 제약도 확인한다.

## 4. 데이터베이스와 블록 스토리지

- RDS는 **공개 접근 가능**하게 구성할 수 있다. 운영 DB는 일반적으로 private
  subnet에 두고, 보안 그룹·암호화·백업·패치·모니터링으로 보호한다. 이는
  권장 아키텍처이지 RDS의 강제 규칙은 아니다.
- default VPC의 기본 서브넷에는 인터넷 게이트웨이 경로가 있을 수 있다. default
  VPC 사용을 금지해야 하는지는 조직의 표준·분리 요구사항에 따라 결정한다.
- DynamoDB는 관리형 서버리스 key-value/document DB다. 수평 확장에 적합하지만
  무한 성능을 보장하지 않는다. 파티션 키 설계, hot partition, 용량·계정 한계를
  고려한다.
- S3 객체는 같은 키에 새 객체를 PUT해 교체할 수 있지만, 파일 시스템처럼 제자리
  수정하는 방식은 아니다. 버전 관리가 켜져 있으면 이전 버전이 남는다.
- EBS는 SSD·HDD 계열을 모두 제공하는 블록 스토리지다. “삭제 시 두세 번 덮어쓴
  뒤 물리 파기한다”는 보장 대신 AWS의 미디어 폐기·소독 절차와 고객의 암호화·키
  폐기·스냅샷 관리 책임을 구분해야 한다.

## 복습 체크

- [ ] SCP가 IAM 권한을 부여하지 않는다는 점을 설명할 수 있는가?
- [ ] KMS와 비밀 저장·회전 서비스의 역할을 구분하는가?
- [ ] SSE-S3, SSE-KMS, SSE-C의 책임 범위를 구분하는가?
- [ ] Object Lock, 버전 관리, 복제가 각각 막아 주는 위험을 구분하는가?
- [ ] 운영 RDS를 private subnet에 두는 이유를 설명할 수 있는가?

## 확인하지 못한 것

이 과정은 **리포에 실습이 없다.** 실습에서 파생된 작업물은 벤더 독립 보안
에이전트로 분리해 [`agents/security/`](../../../agents/security)에 있고, 그쪽은
별도로 검증된다. 따라서 아래 노트는 **강의 내용을 AWS 공식 문서와 대조한
것까지**이고, 직접 실행해 확인한 것이 아니다.

구체적으로 실행하지 않은 것:

- KMS 키 생성과 봉투 암호화의 실제 데이터 키 발급·복호 흐름
- Secrets Manager 자동 교체(rotation)
- CloudHSM (전용 하드웨어가 필요하다)
- S3 스토리지 클래스 전환에 따른 실제 비용·검색 지연
- 데이터베이스·EBS 암호화를 켠 뒤의 성능 영향

## 공식 자료

- [AWS Security Reference Architecture — 조직 계정](https://docs.aws.amazon.com/prescriptive-guidance/latest/security-reference-architecture/org-management.html)
- [AWS Control Tower란?](https://docs.aws.amazon.com/controltower/latest/userguide/what-is-control-tower.html)
- [AWS KMS 암호화 기본 개념](https://docs.aws.amazon.com/kms/latest/developerguide/concepts.html)
- [AWS KMS 봉투 암호화](https://docs.aws.amazon.com/kms/latest/developerguide/concepts.html#enveloping)
- [KMS 키 삭제 예약](https://docs.aws.amazon.com/cli/latest/reference/kms/schedule-key-deletion.html)
- [AWS Secrets Manager란?](https://docs.aws.amazon.com/secretsmanager/latest/userguide/intro.html)
- [Parameter Store란?](https://docs.aws.amazon.com/systems-manager/latest/userguide/systems-manager-parameter-store.html)
- [Amazon S3 기본 암호화](https://docs.aws.amazon.com/AmazonS3/latest/userguide/default-encryption-faq.html)
- [Amazon S3 Object Ownership](https://docs.aws.amazon.com/AmazonS3/latest/userguide/about-object-ownership.html)
- [Amazon S3 스토리지 클래스](https://docs.aws.amazon.com/AmazonS3/latest/userguide/storage-class-intro.html)
- [Amazon S3 Intelligent-Tiering](https://docs.aws.amazon.com/AmazonS3/latest/userguide/using-intelligent-tiering.html)
