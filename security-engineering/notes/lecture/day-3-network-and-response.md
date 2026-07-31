# Day 3 — 네트워크 보안, 관측성, 인시던트 대응

> 교육일: 2026-07-24
> AWS 공식 문서 확인일: 2026-07-31
> 범위: VPC 경계, 웹 보호, 로그·자동화, 위협 탐지와 대응

## 학습 목표

- VPC 라우팅·서브넷·보안 그룹·NACL의 경계를 구분한다.
- CloudFront, ELB, WAF, Shield, VPC endpoint의 쓰임을 설명한다.
- 로그 수집, 탐지, 격리, 증거 보존, 복구의 인시던트 대응 흐름을 설계한다.

> 이 노트는 GPT-5.6과 함께 정리했습니다. 원 강의 내용을 바탕으로 AWS 공식
> 문서와 대조해 오개념을 짚고 사실을 재확인했으며, 정리 방향과 최종 내용은
> 사람이 검토·승인했습니다.

## 1. VPC와 네트워크 경계

VPC는 AWS 계정 안에서 정의하는 논리적으로 격리된 가상 네트워크다. 단순한 “AWS용
공유기”가 아니다. 통신 가능 여부는 CIDR, route table, internet gateway, NAT
Gateway, public IP, security group, NACL, VPC endpoint의 조합으로 결정된다.

- **public subnet**: route table에 internet gateway로 향하는 경로가 있는 서브넷.
  인터넷에서 인스턴스에 실제 도달하려면 public IPv4/EIP와 보안 그룹 등도 추가로
  필요하다.
- **private subnet**: 인터넷 게이트웨이로 직접 들어오는 경로가 없다. NAT Gateway를
  통해 아웃바운드 인터넷 연결은 할 수 있지만 외부에서 시작한 직접 연결은 받지
  않는다.
- **isolated subnet**: 인터넷으로 향하는 인바운드·아웃바운드 경로를 두지 않은
  서브넷. DB 등 강한 격리에 적합하다.

### Security group과 NACL

| 제어 | 적용 지점 | 상태 | 기본 설계 |
|---|---|---|---|
| 보안 그룹(Security Group) | ENI·인스턴스 등 | 상태 저장(stateful) | 워크로드별 최소 허용 |
| 네트워크 ACL(NACL) | 서브넷 | 비상태 저장(stateless) | 서브넷 단위 추가 방어·차단 |

보안 그룹에서 허용된 연결의 응답 트래픽은 별도 규칙 없이 허용된다. NACL은 비상태
저장이므로 요청과 응답 방향, 임시 포트까지 양방향으로 허용해야 한다. NACL이
“가장 저렴한 차단 방법”이라서 선택하는 것이 아니라, 제어가 필요한 계층·범위에
따라 선택한다. 보안 그룹에는 추가 요금이 없다.

원칙은 allowlist다. 모든 포트를 열거나 `0.0.0.0/0`을 넓게 허용하지 않고, 필요한
프로토콜·포트·대상·소스만 허용한다. 운영 접근은 bastion host를 무조건 두기보다,
가능하면 AWS Systems Manager Session Manager를 사용해 인바운드 SSH와 bastion
노출을 줄이고 세션 기록을 남기는 방식을 검토한다.

## 2. 사설 연결과 서비스 접근

- VPC peering은 두 VPC를 직접 연결한다. A-B, B-C가 있어도 A-C로 자동 전달하는
  전이적(transitive) 라우팅은 지원하지 않는다.
- Transit Gateway는 많은 VPC·온프레미스 연결의 허브 라우팅을 단순화한다. 연결이
  자동 암호화·자동 허용되는 것은 아니며 라우팅·보안 정책을 설계해야 한다.
- Direct Connect는 AWS와 온프레미스 간의 전용 연결이다. 전용 연결 자체가 모든
  트래픽의 암호화를 보장하지 않으므로, 필요하면 MACsec 또는 VPN 등 추가 암호화를
  검토한다.
- **Gateway VPC endpoint**는 S3와 DynamoDB용이다. **Interface VPC endpoint**는
  ENI와 security group을 사용하며 AWS PrivateLink 기술을 기반으로 한다. S3와
  DynamoDB도 interface endpoint를 지원하지만 gateway endpoint와 특성·비용이
  다르다.
- PrivateLink는 서비스 제공자와 소비자를 사설 IP로 연결하는 기술이다. 모든 VPC
  endpoint와 동의어는 아니다. endpoint policy 지원 여부는 서비스와 endpoint
  유형별로 확인한다.

## 3. 인터넷 경계와 웹 애플리케이션 보호

대표적인 공개 웹 경로는 다음과 같다.

```text
Viewer → Route 53 (DNS) → CloudFront + AWS WAF + Shield Standard
       → ALB / API Gateway → private application tier → database
```

CloudFront는 엣지 로케이션에서 콘텐츠를 캐시·전달하는 CDN이다. 엣지 로케이션은
“AZ와 사용자 사이의 가용성 계층”이 아니라 사용자와 가까운 AWS point of presence다.
CloudFront는 별도 “CloudFront 스토리지”를 만드는 서비스가 아니며, S3·ALB 같은
origin에서 콘텐츠를 가져온다.

Elastic Load Balancing(ELB)은 healthy target에 트래픽을 분산한다. 로드 밸런서가
모든 트래픽의 첫 단계는 아니며, DNS 해석과 CloudFront가 앞에 올 수 있다. 현재
유형은 Application Load Balancer(ALB), Network Load Balancer(NLB), Gateway Load
Balancer(GWLB), Classic Load Balancer(CLB)다. CLB는 레거시 설계에 해당하지만,
공식 종료 공지가 없는 한 “곧 사라진다”고 단정하지 않는다.

- **AWS WAF**: HTTP(S) 요청의 Layer 7 규칙 기반 필터링. 관리형 규칙, 자체 규칙,
  rate-based rule, 정규식 조건 등을 사용한다.
- **AWS Shield Standard**: 기본 DDoS 보호. Shield Advanced는 추가 DDoS 대응
  기능과 지원을 제공하는 유료 서비스다.
- **AWS Network Firewall**: VPC 경계에서 상태 저장 검사와 도메인·프로토콜 제어에
  사용하는 관리형 네트워크 방화벽이다.
- TLS 종료와 내부 재암호화는 요구사항에 따라 선택한다. 이것만으로 zero trust가
  완성되는 것은 아니며, 인증·권한·네트워크 분리·로깅이 함께 필요하다.

Route 53 health check와 failover routing은 DNS 응답을 바꿀 수 있지만, 클라이언트와
리졸버의 TTL 캐시 때문에 즉시 모든 트래픽이 바뀐다고 보장하지 않는다.

## 4. 관측성, 로그, 자동화

| 데이터 | 목적 | 대표 저장·처리 경로 |
|---|---|---|
| Metrics | CPU, 지연 시간, 오류율 등 상태 관찰 | CloudWatch Metrics·Alarms |
| Logs | API 호출, 애플리케이션 이벤트, 접근 기록 | CloudWatch Logs, S3, Firehose |
| Traces | 분산 요청의 서비스 간 경로·지연 분석 | X-Ray 또는 OpenTelemetry 연동 |

CloudTrail은 AWS API 활동을 기록하고, VPC Flow Logs는 VPC·서브넷·ENI의 IP 트래픽
메타데이터를 기록한다. VPC Flow Logs의 대상은 CloudWatch Logs, S3, Kinesis Data
Firehose가 될 수 있다. ALB access log는 S3로 전달한다. 따라서 “모든 로그는
CloudWatch Logs”나 “S3에는 로그를 저장하지 않는다”는 말은 틀리다. 실시간 경보,
장기 보관·조사, 비용·보존 요건에 따라 목적지를 나눈다.

운영 인스턴스의 로컬 디스크에만 로그를 두면 인스턴스 교체·침해 시 증거가 사라질
수 있다. 애플리케이션 로그, CloudTrail, Flow Logs, 로드 밸런서 로그를 중앙 계정에
전달하고, 보존 기간·암호화·접근 통제를 설정한다.

CloudWatch Events는 EventBridge의 이전 이름이다. EventBridge는 호환성을 유지하며
확장된 이벤트 버스 기능을 제공한다. 일반적인 자동화 흐름은 다음과 같다.

```text
CloudWatch alarm / GuardDuty finding / Config noncompliance
→ EventBridge rule → SNS notification 또는 Lambda·Step Functions remediation
```

자동화는 보안에만 한정되지 않는다. 다만 격리·삭제처럼 영향이 큰 조치는 검토,
승인, 예외 처리, 재시도·감사 로그를 포함한 런북으로 설계한다.

Lambda의 최대 실행 시간은 15분이다. ZIP 배포 패키지와 layer를 합친 압축 해제
크기는 250 MB 제한이 적용된다. container image 배포는 더 큰 이미지를 지원한다.
장시간 작업은 Step Functions로 ECS/Fargate, Batch 등과 조합할 수 있으며 EC2만이
유일한 대안은 아니다.

## 5. 큐, 탐지, 대응

SQS 표준 큐는 at-least-once 전달이며 순서가 바뀔 수 있다. FIFO 큐는 순서와
중복 제거 기능을 제공하지만, 소비자는 여전히 멱등성, visibility timeout, 재시도,
DLQ를 설계해야 한다. 비동기 처리의 목적은 긴 작업·트래픽 급증을 완충하는 것이며,
“반드시 한 번만 처리된다”는 보장은 아니다.

Amazon Inspector는 지원되는 EC2·ECR·Lambda·코드 저장소의 취약점·노출을 찾는
서비스이며 일반적인 SAST와 동일하지 않다. GuardDuty는 여러 AWS 데이터 소스를
분석해 위협 징후를 찾는다. Malware Protection을 활성화했다고 모든 악성 코드를
자동 치료하는 것은 아니다. Detective는 CloudTrail·GuardDuty 등의 보안 데이터를
조사 맥락으로 연결한다. 탐지 원본의 수집·보존·권한 설정을 대신하지 않는다.

### 인시던트 대응 흐름

1. **준비**: 연락망, 역할, 계정 간 조사 권한, 격리·증거 보존 런북을 사전 검증한다.
2. **식별·분석**: 경보와 로그의 범위·영향·공격 경로를 조사한다.
3. **격리**: 보안 그룹 변경, 격리 VPC·계정, 자격 증명 비활성화 등으로 피해 확산을
   제한한다. 보안 그룹만 바꿨다고 모든 경로가 차단되는지 라우팅·기존 세션·권한을
   함께 확인한다.
4. **증거 보존·제거·복구**: 로그, EBS snapshot 등 증거를 보존하고, 원인을 제거한
   뒤 검증된 환경으로 복구한다. EBS snapshot은 사용자의 S3 버킷으로 “보내는
   파일”이 아니라 AWS 관리형 snapshot 데이터다.
5. **사후 개선**: 원인, 탐지 지연, 의사소통, 자동화·가드레일의 보완점을 기록하고
   tabletop exercise로 반복 검증한다.

## 복습 체크

- [ ] public/private subnet을 route table 기준으로 설명할 수 있는가?
- [ ] 보안 그룹과 NACL의 상태 저장 차이 및 임시 포트 필요성을 설명하는가?
- [ ] gateway/interface endpoint와 PrivateLink를 구분하는가?
- [ ] CloudTrail, Flow Logs, CloudWatch Logs, S3의 로그 역할을 구분하는가?
- [ ] 탐지 후 격리·증거 보존·복구 순서를 갖춘 런북이 있는가?

## 확인하지 못한 것

이 과정은 **리포에 실습이 없다.** 실습에서 파생된 작업물은 벤더 독립 보안
에이전트로 분리해 [`agents/security/`](../../../agents/security)에 있고, 그쪽은
별도로 검증된다. 따라서 아래 노트는 **강의 내용을 AWS 공식 문서와 대조한
것까지**이고, 직접 실행해 확인한 것이 아니다.

구체적으로 실행하지 않은 것:

- VPC를 만들어 security group과 NACL의 상태 유지/비유지 차이를 실제로 관찰
- PrivateLink·VPC 엔드포인트를 통한 사설 연결
- WAF 규칙이 실제 요청을 차단하는지
- 인시던트 대응 흐름을 모의 사건으로 돌려보기 (탐지 → 격리 → 복구)

## 공식 자료

- [Amazon VPC 보안](https://docs.aws.amazon.com/vpc/latest/userguide/VPC_Security.html)
- [보안 그룹과 NACL의 상태 저장 차이](https://docs.aws.amazon.com/vpc/latest/userguide/flow-logs-records-examples.html)
- [VPC endpoints](https://docs.aws.amazon.com/vpc/latest/privatelink/vpc-endpoints.html)
- [AWS PrivateLink 개요](https://docs.aws.amazon.com/vpc/latest/privatelink/what-is-privatelink.html)
- [CloudFront VPC origin 보안](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-vpc-origins.html)
- [Elastic Load Balancing](https://docs.aws.amazon.com/elasticloadbalancing/latest/userguide/what-is-load-balancing.html)
- [AWS WAF](https://docs.aws.amazon.com/waf/latest/developerguide/what-is-aws-waf.html)
- [VPC Flow Logs](https://docs.aws.amazon.com/vpc/latest/userguide/flow-logs.html)
- [AWS Lambda quotas](https://docs.aws.amazon.com/lambda/latest/dg/gettingstarted-limits.html)
- [AWS 보안 인시던트 대응 안내](https://docs.aws.amazon.com/whitepapers/latest/aws-security-incident-response-guide/welcome.html)
