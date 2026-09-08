# Day 1 — DevOps 개론, CI/CD, IaC 기초

> 교육일: 2026-07-30
> AWS 공식 문서 확인일: 2026-07-31
> 범위: 현대적 애플리케이션 아키텍처, DevOps 방법론, AMI·컨테이너 격리,
> CloudFormation 구조, CodePipeline 개요, AWS CLI 인증

> 이 노트는 Kiro CLI(모델: claude-opus-5)와 함께 정리했습니다. 원 강의
> 필기를 바탕으로 AWS 공식 문서와 대조해 오개념을 짚고 사실을 재확인했으며,
> 정리 방향과 최종 내용은 사람이 검토·승인했습니다.

수업 필기 원본은 별도 문서(Google Docs)로 관리한다. 필기에 없던 사실은
추가하지 않았고, 공식 문서로 보강한 부분은 "공식 자료"에 출처를 달았다.

## 학습 목표

- 모놀리스에서 마이크로서비스로의 전환 배경과 DevOps 방법론의 대응 관계를
  설명한다.
- AWS 관측성 3요소(메트릭·로그·트레이스)와 담당 서비스를 구분한다.
- AMI·컨테이너가 "이미지화"로 해결하는 문제(격리, 복제)를 설명한다.
- CloudFormation의 서비스/리소스/템플릿/스택 개념과 스택 단위 삭제의 의미를
  설명한다.
- AWS CLI 인증에 필요한 두 파일(`credentials`, `config`)의 역할을 구분한다.

## 1. 모놀리스에서 마이크로서비스로

과거에는 애플리케이션 전체를 한 코드 덩어리(모놀리스)로 구현했다. 클라우드
사용이 늘면서 서비스 단위로 쪼개 배포하는 **마이크로서비스 아키텍처(MSA)**가
늘었고, 이에 따라 팀 구성도 서비스별로 개발자와 운영자가 함께 있는 형태
("피자팀")로 바뀌는 경향이 있다.

MSA·서버리스 같은 현대적 애플리케이션은 다음 특성을 함께 요구한다.

- 지속적 통합(CI), 지속적 전달/배포(CD)
- 코드형 인프라(IaC)
- 모니터링 및 로깅
- 협업 문화

이 다섯 가지를 아우르는 방법론이 **DevOps**다.

애플리케이션 배포 대상은 크게 EC2, ECS/EKS, Lambda다. Lambda는 VPC 안에
반드시 있어야 하는 리소스가 아니며, VPC 연동은 필요할 때 선택적으로 구성한다.
EC2 인스턴스를 생성할 때 함께 붙는 스토리지는 기본적으로 **EBS(Elastic Block
Store)** 볼륨이다.

애플리케이션 간 연계 방식도 변화했다. 과거에는 동기식 API 호출
(API Gateway 등)이 중심이었고, 최근에는 비동기식 이벤트 기반 연계
(EventBridge 등)를 함께 쓰는 사례가 늘고 있다.

## 2. DevOps 방법론과 담당 서비스

| 방법론 | 담당 AWS 서비스 |
|---|---|
| CI/CD | CodePipeline, CodeBuild, CodeDeploy |
| IaC | CloudFormation, SAM, CDK |

### 관측성(Observability) 3요소

| 요소 | 담당 서비스 |
|---|---|
| Metric | CloudWatch |
| Log | CloudWatch Logs |
| Trace | X-Ray (AWS 자체 서비스, 최근 비중이 줄고 있음) 또는 OpenTelemetry |

X-Ray는 AWS 전용 트레이싱 서비스이지만, 최근에는 벤더 중립 표준인
**OpenTelemetry**로 메트릭·로그·트레이스 3요소를 함께 표준화해 다루는 흐름이
있다. OpenTelemetry는 AWS 서비스가 아니다.

## 3. 격리와 이미지화: AMI와 컨테이너

클라우드·가상화 환경에서 중요한 개념은 **격리**다. 한 서버의 장애가 다른
서버로 전이(장애연쇄)되지 않도록 막는다.

서버가 여러 대 필요할 때 하나씩 새로 만들지 않고, 완성된 구성을 이미지로
만들어 복제한다.

- **EC2 → AMI(Amazon Machine Image)**: OS를 포함한 인스턴스 구성을 이미지화.
  AMI는 리전·OS·프로세서 아키텍처·루트 볼륨 타입·가상화 타입에 종속되며, 하나의
  AMI로 동일한 구성의 인스턴스를 여러 개 실행할 수 있다.
- **컨테이너**: 마이크로서비스 중에서도 무거운 서비스를 경량화해 이미지로
  찍어낸 것. 컨테이너는 OS 전체를 포함하지 않지만 OS의 기능(커널 등)은
  공유해서 쓴다 — "OS가 없는 것"이 아니라 "OS를 무겁게 포함하지 않는 것"이다.

## 4. AWS 글로벌 인프라와 접근 방식

AWS 글로벌 인프라는 **리전, 가용 영역(AZ), 엣지 로케이션**으로 구성된다.
대부분의 서비스는 리전 단위로 제공된다.

학습 순서로는 콘솔로 서비스를 먼저 익히고, 이후 IaC로 전환하는 방식이
권장된다. 코드형 인프라는 같은 구성을 재사용하기 쉽다는 장점이 있다.

AWS에 접근하는 세 가지 방법은 콘솔, CLI, SDK다. 콘솔과 CLI도 결국 내부적으로
API를 호출하는 것이고, 콘솔·CLI는 API 호출을 사람이 편하게 쓰도록 감싼
인터페이스다.

IaC를 구현하는 수단은 셸 스크립트, 애플리케이션 코드, AWS CloudFormation,
서드파티 도구(Terraform 등)로 나뉜다.

## 5. CloudFormation: 서비스, 리소스, 템플릿, 스택

**서비스와 리소스는 다른 개념이다.** 예를 들어 EC2는 서비스이고 그 서비스가
만드는 인스턴스는 리소스다. Lambda는 서비스이고 그 함수는 리소스다.
서비스와 리소스가 1:1로 대응하는 것도 아니다 — AMI도 EC2 서비스가 다루는
리소스 중 하나다.

CloudFormation 템플릿은 YAML(또는 JSON) 형식이며, 대부분의 섹션이
선택사항이지만 **Resources 섹션은 필수**다. 여기서 생성할 AWS 자산을 정의한다.

템플릿을 배포하면 **스택(stack)** 이 만들어진다. 스택은 템플릿에 정의된
여러 리소스를 하나의 단위로 묶은 것이다.

- 콘솔에서 VPC를 만들고 그 안에 EC2를 만들었다면, 삭제할 때는 역순으로
  EC2를 먼저 지우고 VPC를 지워야 한다.
- CloudFormation은 스택을 삭제하면 그 안의 리소스가 종속성 순서에 따라
  자동으로 삭제된다. 리소스 간 종속 관계는 템플릿에서 `Ref`/`GetAtt`/`Sub`로
  참조되면 암묵적으로 생기고, `DependsOn` 속성으로 명시할 수도 있다. 생성은
  참조 대상이 먼저, 삭제는 참조 대상이 나중이다.

AgentCore를 CDK로 배포할 때도 내부적으로 CloudFormation을 호출하므로, 콘솔의
CloudFormation 스택 화면에서 배포 이벤트와 생성된 리소스를 확인할 수 있다.

### 변경 세트(Change Set)와 드리프트 감지

스택을 업데이트할 때 바로 적용하는 대신, **변경 세트(change set)**로 어떤
리소스가 추가·수정·삭제되는지 먼저 미리 볼 수 있다. CloudFormation은 제출한
템플릿·파라미터와 현재 스택을 비교해 변경 세트를 만들고, 이 시점에는 실제
스택을 바꾸지 않는다. 변경 세트를 검토한 뒤 실행(execute)해야 실제로
적용된다 — "적용하면 무엇이 바뀌는지 모른 채 업데이트하는" 위험을 줄이는
장치다.

콘솔에서 리소스를 직접 수정하면 스택 정의와 실제 상태가 달라질 수 있다.
이런 어긋남을 **드리프트(drift)**라 하고, CloudFormation은 드리프트
감지로 스택이 마지막 배포 상태와 실제 상태 중 어디서 갈렸는지 확인할 수
있다. "IaC로 관리하는 리소스는 콘솔에서 손대지 않는다"는 원칙이 지켜지지
않았을 때 이를 발견하는 수단이 드리프트 감지다.

CodeDeploy는 **애플리케이션**을 배포하고, CloudFormation은 **인프라**를
배포한다. 애플리케이션과 인프라 코드의 빌드·테스트·배포까지 자동화하는 것이
CodePipeline이다.

## 6. AWS CLI 설치와 인증

AWS CLI는 내부적으로 Python으로 작성되어 있지만, 현재 표준인 **AWS CLI
v2**는 Python을 자체 번들하므로 별도 Python 설치가 필요 없다(v1은 별도
Python 설치가 전제조건이었으나 v1은 더 이상 표준이 아니다). 설치 후
`aws configure` 명령으로 인증 정보를 로컬에 저장할 수 있다.

인증에 필요한 값과 저장 파일:

| 파일 | 저장 값 |
|---|---|
| `credentials` | 액세스 키 ID, 시크릿 액세스 키 |
| `config` | 리전, 출력 형식 |

`ami-xxxxx` 형식의 리소스 ID는 EC2 관련 리소스(AMI)에서만 생성되는 식별자다.

## 7. CodePipeline 개요

CodePipeline 구성 시 옵션을 선택해 파이프라인을 세팅한다.

- **소스 스테이지**: 프로바이더(리포지토리 종류), 리포지토리, 브랜치 등을
  선택. **소스 스테이지는 필수**다 — 소스 변경이 있어야 파이프라인이
  성립하기 때문이다.
- 그 외 **빌드, 테스트, 배포, 리뷰 스테이지는 선택사항**이다. 파이프라인은
  최소 2개 스테이지가 필요하고, 두 번째 스테이지는 빌드 또는 배포 중
  하나면 된다.
- 호출(Lambda), 승인(SNS로 알림 후 사람이 승인) 같은 추가 작업도 붙일 수
  있다.
- 파이프라인 내에서 병렬 작업과 순차 작업을 모두 구성할 수 있다.
- 에이전트에 도구를 추가하는 것과 같은, "무언가가 바뀌면 후속 처리가
  일어나는" 구조는 넓게 보면 CodePipeline과 같은 패턴으로 볼 수 있다.

## 핵심 요약

1. MSA·서버리스로의 전환이 CI/CD·IaC·모니터링·협업을 요구했고, 이것이
   DevOps 방법론이다.
2. 관측성 3요소는 메트릭(CloudWatch)·로그(CloudWatch Logs)·트레이스(X-Ray
   또는 OpenTelemetry)다.
3. AMI(EC2)와 컨테이너는 모두 "이미지화를 통한 복제"로 격리와 장애 전파
   방지를 해결하는 수단이다.
4. CloudFormation의 리소스는 필수 섹션, 스택은 여러 리소스를 묶어 생성·삭제
   단위로 다루는 구조다.
5. CodePipeline은 소스 스테이지만 필수이고 나머지는 선택이다.

## 확인하지 못한 것

- AMI를 실제로 생성·복제해 인스턴스를 띄우는 과정은 직접 실행하지 않았다.
- CloudFormation 스택을 만들고 삭제해 종속성 순서(`DependsOn`, 암묵적 참조)를
  직접 재현하지 않았다. 문서로만 확인했다.
- CodePipeline을 실제로 구성해 소스/빌드/배포 스테이지가 동작하는 과정은
  이 노트에서 다루지 않는다(Day 2 실습 여부는 별도 확인 필요).
- "깃옵스"·쿠버네티스와의 관계는 Day 2 필기에 언급만 있고 이 노트에서
  검증하지 않았다.
- 변경 세트를 실제로 만들어 리소스 추가·수정·삭제 미리보기를 확인하거나,
  콘솔에서 리소스를 직접 고쳐 드리프트 감지를 실행해보는 것은 하지 않았다 —
  이 절은 강의 필기에 없어 전부 공식 문서로 보강한 내용이다.

## 공식 자료

- [Amazon Machine Images in Amazon EC2](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/AMIs.html)
- [DependsOn attribute (CloudFormation)](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-attribute-dependson.html)
- [Update CloudFormation stacks using change sets](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-cfn-updating-stacks-changesets.html)
- [Troubleshooting CloudFormation — Dependency error](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/troubleshooting.html)
- [Step 4: Add build stage (CodePipeline)](https://docs.aws.amazon.com/help-panel/codepipeline/latest/helppanel/hp-create-pipeline-wizard.build.html)
- [Infrastructure as Code (IaC) — AWS SAM](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/what-is-iac.html)
- [Install or update to the latest version of the AWS CLI (v2 설치 요구사항 — Python 불필요)](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
