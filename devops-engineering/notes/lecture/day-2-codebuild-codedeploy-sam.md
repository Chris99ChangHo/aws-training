# Day 2 — 컨테이너 빌드, CodeBuild/CodeDeploy, 로드밸런서, SAM

> 교육일: 2026-07-31
> AWS 공식 문서 확인일: 2026-07-31
> 범위: 컨테이너 이미지 빌드, CodeBuild 빌드스펙, CodeDeploy 배포 그룹과
> 컴퓨트 플랫폼, Auto Scaling, 로드밸런서, AWS SAM 워크플로우

> 이 노트는 Kiro CLI(모델: claude-opus-5)와 함께 정리했습니다. 원 강의
> 필기를 바탕으로 AWS 공식 문서와 대조해 오개념을 짚고 사실을 재확인했으며,
> 정리 방향과 최종 내용은 사람이 검토·승인했습니다.

수업 필기 원본은
[`_raw/2026-07-31-day2.txt`](../_raw/2026-07-31-day2.txt)에 가공하지 않고 둔다.
필기에 없던 사실은 추가하지 않았고, 공식 문서로 보강한 부분은 "공식 자료"에
출처를 달았다.

## 학습 목표

- CodeBuild 빌드스펙의 4단계 구조와 각 단계의 역할을 설명한다.
- CodeDeploy가 지원하는 컴퓨트 플랫폼과 지원하지 않는 대상을 구분한다.
- Auto Scaling이 수직 확장 대신 사용되는 이유를 설명한다.
- 로드밸런서가 EC2와 함께 쓰이는 이유를 설명한다.
- AWS SAM의 워크플로우(init → build → deploy)와 템플릿 구조를 설명한다.

## 1. 컨테이너 이미지 빌드

컨테이너는 Dockerfile을 이미지로 만드는 과정(도커 빌드)을 거친다. AWS
환경에서는 이 빌드 과정을 CodeBuild로 실행하는 경우가 많다.

전날 실습이 AgentCore의 CI/CD(백엔드 자동화)였다면, 이어지는 실습은
프론트엔드까지 포함한 자동화다. 이 구조는 아이디어만 있으면 그대로 재사용할
수 있는 템플릿이자 포트폴리오로 쓸 수 있다.

## 2. IaC와 CI/CD의 관계

서비스는 중단되면 안 되므로 인프라부터 코드로 관리한다는 것이 IaC의
출발점이다. 애플리케이션을 배포하기 전에 인프라를 먼저 코드로 배포하고, 이
전체 과정(인프라 배포 + 애플리케이션 배포)을 자동화하는 것이 CI/CD다. 여기에
마이크로서비스 아키텍처(MSA)까지 세트로 고려하는 것이 현대적인 접근이다.

**SAM(서버리스 애플리케이션 모델)**은 이 흐름에서 서버리스 워크로드를 다루는
도구다(자세한 내용은 6절).

## 3. 관측성과 코드 리뷰의 자동화 흐름

관측성 3요소(메트릭·로그·트레이스)는 최근 표준으로 OpenTelemetry가 세 요소를
함께 다루는 방식으로 수렴하고 있다 (Day 1 참고).

CodeGuru Reviewer는 도구가 코드를 검토하고 사람 검토자가 최종 확인하는
조합이었다. 최근에는 에이전트 두 개를 띄워 하나는 작성, 하나는 검토를
전담시키는 방식도 쓰인다.

## 4. CodeBuild: 빌드 환경과 빌드스펙

CodeBuild에서 알아야 할 두 가지는 다음과 같다.

- **빌드 환경**: 빌드가 실행될 때 생성되고, 끝나면 사라지는 일시적 환경.
- **빌드스펙(buildspec)**: 빌드에 필요한 절차를 정의한 YAML 파일.

빌드스펙의 `phases`는 다음 4단계로 고정되어 있고, 이름을 바꿀 수 없으며 새
단계를 추가할 수도 없다. 필요한 단계만 골라 쓰면 된다.

| 단계 | 역할 |
|---|---|
| `install` | 런타임·의존성 설치 |
| `pre_build` | 빌드 전 준비 작업 (예: 로그인) |
| `build` | 실제 빌드 명령 실행 |
| `post_build` | 빌드 후 처리 (예: 알림, 아티팩트 정리) |

```yaml
version: 0.2
phases:
  install:
    runtime-versions:
      java: corretto11
  pre_build:
    commands:
      - echo Nothing to do in the pre_build phase...
  build:
    commands:
      - mvn install
  post_build:
    commands:
      - echo Build completed on `date`
artifacts:
  files:
    - target/messageUtil-1.0.jar
```

빌드 중 SNS 알림은 필수는 아니지만, 빌드 상태를 계속 지켜볼 수 없으므로
편의·모니터링 목적으로 붙이는 경우가 많다.

CodeBuild의 모든 로그는 **CloudWatch**가 수집·관리한다. 단계별로 실행된
명령과 그 결과 상태가 로그에 기록되므로, 문제 진단에 로그 확인이 도움이 된다.

## 5. CodeDeploy: 배포 그룹과 컴퓨트 플랫폼

CodeDeploy는 **애플리케이션**과 **배포 그룹**을 만들어야 배포할 수 있다(빌드는
"빌드 프로젝트" 단위, 배포는 "애플리케이션" 단위로 리소스를 만든다).

**컴퓨트 플랫폼은 세 가지뿐이다**: EC2/On-Premises, AWS Lambda, Amazon ECS.
**Amazon EKS는 CodeDeploy의 배포 대상이 아니다.**

훅(Hook) 섹션은 `Hooks:` 형식으로 배포 생명주기 단계에 스크립트를 연결한다.

### Auto Scaling과 수직 확장

인스턴스를 수직으로 확장(예: `large` → `2xlarge`)하려면 재부팅이 필요해
서비스가 중단된다. 이를 피하기 위해 **Auto Scaling**으로 인스턴스 개수를
조절하는 수평 확장을 쓴다.

Auto Scaling 설정 요소:

- **최소/최대 개수**: 비용 폭탄을 막기 위한 하한·상한.
- **스케일링 정책**: 언제 개수를 늘리고 줄일지 결정하는 조건.
- **시작 템플릿(launch template)**: 새로 시작할 인스턴스의 유형·구성을 정의.

### 리비전 타입

CodeDeploy에 배포할 소스 코드가 어디에 저장되어 있는지를 나타내는 것이
리비전 타입이다(예: S3, GitHub).

### 자동화 설정의 의미

자동화를 위한 초기 설정만 잘 해두면, 이후로는 AWS 서비스들이 그 설정값을
읽고 실행·호출하는 방식으로 동작한다. AWS 서비스 대부분이 "설정값을
대입하면 동작하는" 구조로 설계되어 있다.

## 6. 로드밸런서

로드밸런서(ELB)를 EC2와 함께 쓰는 이유:

- 들어오는 요청을 받아 여러 서버 인스턴스에 분산한다.
- 클라이언트가 여러 서버의 개별 IP 주소를 알 필요 없이, 로드밸런서의
  엔드포인트 하나로 접근할 수 있다.

## 7. 기타: CLI vs CloudFormation, 환경 구성, MSA

- **AWS CLI**는 명령 실행을 위한 도구이고, **CloudFormation**은 IaC를 위한
  도구다. 인프라를 만들 때는 CloudFormation을 쓴다.
- 테스트 환경과 프로덕션 환경은 구조는 같되, 테스트는 필수 기능만 가볍게,
  프로덕션은 편의 기능까지 포함하는 방식으로 나눌 수 있다.
- **모놀리스**는 서비스 하나에 DB 하나, **마이크로서비스**는 서비스마다 DB를
  따로 두는 구조다. 마이크로서비스는 서비스별로 구현 언어가 달라도 된다.
- **Amazon API Gateway**는 API 관리를 전담하는 서비스로, Lambda와 함께 쓰이는
  경우가 많다. 로그는 CloudWatch로 수집된다. S3와 CloudFront도 함께 쓰이는
  조합이다.
- Lambda는 기본 설정으로 CloudWatch에 로그를 보낸다.
- "깃옵스(GitOps)"는 코드뿐 아니라 인프라 상태까지 Git 저장소로 관리하고,
  Git의 변경을 배포 트리거로 쓰는 방식이다. 쿠버네티스 환경에서 널리 쓰인다는
  언급이 있었으나, 이 노트에서 직접 검증하지는 않았다(아래 "확인하지 못한
  것" 참고).

## 8. AWS SAM(서버리스 애플리케이션 모델)

SAM은 서버리스 애플리케이션 구축에 쓰는 오픈소스 프레임워크다. CloudFormation
템플릿을 확장한 것으로, 템플릿에 `Transform: AWS::Serverless-2016-10-31`을
선언하면 SAM 템플릿이 된다.

```yaml
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31
Resources:
  HelloWorldFunction:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: hello-world/
      Handler: app.lambdaHandler
      Runtime: nodejs12.x
      Events:
        HelloWorld:
          Type: Api
          Properties:
            Path: /hello
            Method: get
```

`AWS::Serverless::Function` 같은 SAM 리소스 타입은 Lambda 함수·실행
역할·이벤트 소스 매핑을 한 번에 생성한다. 기본 CloudFormation 문법으로는 이
구성들을 각각 따로 작성해야 한다 — API Gateway, Lambda 함수, DB 등을 개별로
만들어야 하는 것을 SAM이 한 번에 묶어 처리한다.

SAM CLI 워크플로우는 AgentCore CLI와 유사한 패턴이다.

```text
sam init → sam build → sam local (test) → sam deploy
```

`sam init`을 실행하면 설정값을 입력받아 프로젝트를 생성한다. 생성된
프로젝트는 보통 `app.py`(Lambda 함수 코드)와 `template.yaml`(SAM 템플릿
파일)로 구성된다.

Lambda 관련 커스텀 설정 두 가지가 새로 추가되었다는 언급이 있었으나, 구체적
내용은 이 필기에 없다(다음 시간 설명 예정이었음).

## 핵심 요약

1. CodeBuild 빌드스펙은 install/pre_build/build/post_build 4단계로 고정.
2. CodeDeploy 컴퓨트 플랫폼은 EC2/On-Premises, Lambda, ECS 세 가지이며
   EKS는 지원하지 않는다.
3. 수직 확장은 서비스 중단을 유발하므로 Auto Scaling(수평 확장)을 쓴다.
4. 로드밸런서는 다중 서버로 요청을 분산하고 단일 엔드포인트를 제공한다.
5. SAM은 `Transform` 선언으로 CloudFormation을 확장해 서버리스 리소스를
   한 번에 정의하는 프레임워크이며, `sam init → build → deploy` 워크플로우를
   따른다.

## 확인하지 못한 것

이 노트는 강의 필기를 AWS 공식 문서와 대조한 것까지이며, 아래는 직접 실행해
검증하지 않았다.

- CodeBuild 빌드스펙을 실제로 작성해 4단계가 로그에 어떻게 기록되는지 확인.
- CodeDeploy 배포 그룹을 EC2/Lambda/ECS 각각에 실제로 구성해보고 동작 차이를
  비교.
- Auto Scaling 정책(스케일링 조건)을 실제로 트리거해 개수 변화를 관찰.
- SAM `init → build → deploy` 전체 워크플로우를 직접 실행.
- GitOps와 쿠버네티스의 관계, "쿠버네티스는 다 깃옵스"라는 필기 내용의
  정확성.
- Lambda에 새로 추가되었다고 언급된 커스텀 설정 두 가지의 구체적 내용.

## 공식 자료

- [Build specification reference for CodeBuild](https://docs.aws.amazon.com/codebuild/latest/userguide/build-spec-ref.html)
- [What is CodeDeploy? — Overview of CodeDeploy compute platforms](https://docs.aws.amazon.com/codedeploy/latest/userguide/welcome.html)
- [CodeDeploy primary components — Compute platform](https://docs.aws.amazon.com/codedeploy/latest/userguide/primary-components.html)
- [Deploy your application and resources with AWS SAM](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-deploying.html)
- [Tutorial: Deploy a serverless application (SAM template example)](https://docs.aws.amazon.com/codecatalyst/latest/userguide/deploy-tut-lambda.html)
- [Infrastructure as Code (IaC) — AWS SAM과 CloudFormation의 관계](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/what-is-iac.html)
