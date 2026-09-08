# Day 3 — 컨테이너 관리형 서비스, 관측성, Lambda·API Gateway

> 교육일: 2026-08-03
> AWS 공식 문서 확인일: 2026-08-04
> 범위: 컨테이너 이미지와 Docker 워크플로우, ECS/EKS/Fargate 역할 구분,
> CodeDeploy 블루/그린 배포, 관측성(ADOT/X-Ray/CloudTrail), Lambda 실행 모델,
> API Gateway API 유형

> 이 노트는 Kiro CLI(모델: claude-sonnet-5)와 함께 정리했습니다. 원 강의
> 필기를 바탕으로 AWS 공식 문서와 대조해 오개념을 짚고 사실을 재확인했으며,
> 정리 방향과 최종 내용은 사람이 검토·승인했습니다.

수업 필기 원본은 별도 문서(Google Docs)로 관리한다. 필기에 없던 사실은
추가하지 않았고, 공식 문서로 보강한 부분은 "공식 자료"에 출처를 달았다.

## 학습 목표

- Docker 이미지·컨테이너의 생명주기(build/pull/push/run)와 정적·동적 상태의
  차이를 설명한다.
- ECS/EKS/Fargate/ECR이 각각 담당하는 역할("관리 vs 호스팅 vs 레지스트리")을
  구분한다.
- ECS의 태스크와 서비스가 어떻게 다른지 설명한다.
- CodeDeploy 블루/그린 배포의 세 가지 트래픽 전환 방식(all-at-once, canary,
  linear)을 구분한다.
- 관측성 3요소와 ADOT·X-Ray·CloudTrail의 역할 차이를 설명한다.
- Lambda 핸들러 파라미터, 콜드 스타트/웜 스타트의 정확한 정의를 설명한다.
- API Gateway의 API 유형(REST/HTTP/WebSocket)을 선택 기준에 따라 구분한다.

## 1. 컨테이너와 CI/CD의 관계

CI/CD는 소스 → 빌드 → 테스트 → 스테이징 → 프로덕션 순서로 자동화한다.
소스 저장 방식이 파이프라인의 빌드 단계 유무를 가른다.

- **S3**: 코드를 zip으로 올리는 경우가 많고, 이는 로컬에서 이미 빌드를
  끝낸 아카이브를 올리는 것에 가깝다.
- **CodeCommit(또는 Git 계열 서드파티 리포지토리)**: 빌드를 파이프라인
  내부에서 수행하겠다는 의미다.

CodeDeploy가 배포할 수 있는 컴퓨트 플랫폼은 EC2/On-Premises, Lambda, ECS
세 가지뿐이며, CloudFormation은 S3와 함께 정적 웹사이트 등 인프라를
배포하는 데 쓰인다(Day 2에서 다룬 컴퓨트 플랫폼 제약과 동일).

## 2. 컨테이너를 쓰는 이유와 VM과의 차이

컨테이너를 쓰는 대표적 이유는 "개발 환경에서 잘 돌던 프로그램이 프로덕션
환경에서 에러가 나는" 문제, 즉 환경 차이로 인한 장애를 줄이는 것이다.

컨테이너와 가상머신(VM)은 모두 격리를 제공하지만 방식이 다르다. VM은 하이퍼
바이저 위에서 OS 전체를 포함한 게스트 OS를 통째로 가상화하고, 컨테이너는
호스트 OS의 커널을 공유하면서 프로세스 단위로 격리한다. 그래서 컨테이너가
VM보다 가볍다.

## 3. Docker 이미지와 컨테이너의 생명주기

Docker는 컨테이너를 만들고 실행·관리하는 컨테이너 가상화 엔진이다. 명령어로
컨테이너를 구축·시작·중지할 수 있고, AWS 위에서도 동일한 워크플로우로
컨테이너를 실행·관리한다.

**이미지(정적) vs 컨테이너(동적)**: 컨테이너 이미지는 CPU·메모리가 할당되지
않은 정적 상태이고, 이 이미지가 실행되어 CPU·메모리를 할당받으면 컨테이너가
된다(일반 프로그램이 스토리지에서 메모리로 올라가 실행되는 "로딩" 과정과
같은 대응 관계다).

| 명령 | 동작 |
|---|---|
| `docker build` | Dockerfile로 컨테이너 이미지 생성 |
| `docker pull` | 이미지 레지스트리에서 이미지 가져오기 |
| `docker push` | 이미지 레지스트리에 이미지 저장 |
| `docker run` | 이미지(정적)를 컨테이너(동적)로 실행 |

Dockerfile은 대문자 명령어로 계층을 쌓는 방식이며, 기본 이미지(base image)
위에 사용자 지정 이미지를 계층으로 얹는 구조다. 이미지 레지스트리는
Docker Hub(오픈소스)와 Amazon ECR(AWS 관리형 서비스) 두 축이 있다.

컨테이너는 VM과 마찬가지로 stateless로 다뤄진다. 필요할 때 만들고 필요 없어
지면 삭제하는 1회성 리소스이므로, 로그처럼 남겨야 하는 데이터는 컨테이너
바깥(CloudWatch 등)으로 빼서 모아야 한다.

## 4. ECS/EKS/Fargate/ECR: 역할 구분

강의에서 나온 "관리/호스팅/레지스트리" 구분을 역할별로 정리하면 다음과 같다.

| 축 | 서비스 |
|---|---|
| 컨테이너 오케스트레이션(관리) | ECS, EKS |
| 호스팅(컴퓨트) | EC2, Fargate |
| 이미지 레지스트리 | ECR |

EC2 기반은 인스턴스를 직접 관리해야 해서 자유도는 높지만 번거롭고, Fargate는
서버 관리가 없어 편하지만 그만큼 제약(세부 설정 자유도)이 있다. 대표적인
Fargate 제약은 **특권(privileged) 컨테이너 실행 불가**, **`hostNetwork`·
`hostPort` 설정 불가**다 — AWS가 인프라를 관리하는 서버리스 launch type이라
호스트 수준 접근이 필요한 구성은 지원하지 않는다. 이런 구성이 필요하면
EC2 launch type을 선택해야 한다.

**EKS**: 쿠버네티스 자체가 복잡하므로, AWS가 컨트롤 플레인과 etcd 관리를
대신 맡고 사용자는 애플리케이션 단만 관리하도록 만든 관리형 서비스다.
AWS 공식 문서 기준으로 EKS 컨트롤 플레인은 최소 2개의 API 서버 인스턴스를
서로 다른 가용 영역에, etcd는 3개 가용 영역에 걸쳐 실행해 가용성을
확보한다 — 필기의 "가용성을 위해 3중화 가용영역을 3개로 구축"이라는 설명은
etcd 기준으로는 맞다.

**ECS**: 컨테이너를 개별 단위로 관리하지 않고, 하나 이상의 컨테이너를 묶은
**태스크(task)** 단위로 관리한다(쿠버네티스의 파드에 대응). 여러 태스크를
묶는 단위가 **ECS 클러스터**다.

### 태스크 vs 서비스

AWS 공식 문서 기준으로 정확한 구분은 다음과 같다.

| | 태스크(단독 실행) | 서비스 |
|---|---|---|
| 성격 | 배치 작업처럼 실행 후 종료 | 지정한 개수를 계속 유지하는 장기 실행 |
| 실패 시 동작 | 재생성되지 않고 종료된 채로 끝남 | 스케줄러가 실패한 태스크를 자동으로 새로 실행해 개수를 맞춤 |

필기의 "태스크는 1회성, 유지하려면 서비스를 첨부"라는 요약은 이 구분과
일치한다.

## 5. 이미지 빌드부터 배포까지: CI/CD와 블루/그린 배포

ECR이나 Docker Hub에서 이미지를 pull하고 CI를 거치는 과정까지가 컨테이너
"구축" 단계이며, 배포 후 트래픽 분산은 로드밸런서(ELB)가 담당한다(Day 2 참고).

컨테이너용 CI/CD 파이프라인에서는 Git 저장소에 소스 코드와 Dockerfile을
함께 올려두고, CloudFormation으로 ECS 같은 인프라를 만들고 CodeBuild로
Docker 이미지를 빌드해 ECR에 올린 뒤 실행하는 흐름을 구성할 수 있다.

### 블루/그린 배포 트래픽 전환 방식

CodeDeploy가 Lambda·ECS 컴퓨트 플랫폼에 배포할 때, 기존 버전(블루)에서 새
버전(그린)으로 트래픽을 옮기는 방식은 세 가지다. AWS 공식 문서 기준으로
정리하면 다음과 같다.

| 방식 | 동작 |
|---|---|
| All-at-once | 트래픽을 한 번에 전부 새 버전으로 전환 |
| Canary | 첫 증분(예: 10%)을 옮기고, 지정한 시간(예: 5분/15분) 후 나머지를 한 번에 전환 — 총 2단계 |
| Linear | 동일한 비율(예: 10%)을 동일한 간격(예: 1분/3분)마다 반복 전환 — 여러 단계 |

`CodeDeployDefault.ECSAllAtOnce`처럼 기본값 이름 자체가 "즉시 100% 전환"을
뜻하는 것은 필기 내용과 일치한다. 다만 필기에 있던 canary "25%×2회",
linear "10%×10회" 같은 구체적 수치는 AWS가 제공하는 사전 정의 구성표
(`ECSCanary10Percent5Minutes`, `ECSLinear10PercentEvery1Minutes` 등)와는
다르다 — 사전 정의 값은 canary 10%/5분 또는 10%/15분, linear 10%씩 1분 또는
3분 간격이며, 필요하면 커스텀 구성도 만들 수 있다. 실제 프로젝트에서는
필기의 수치를 그대로 쓰지 말고 콘솔이나 문서에서 최신 사전 정의 값을
확인해야 한다.

## 6. 관측성(Observability)

관측성의 3요소는 지표(메트릭)·로그·트레이싱이다. 마이크로서비스
아키텍처(MSA)로 서비스가 여러 개로 나뉘면서, 요청 하나가 여러 서비스를
거치는 흐름을 추적할 필요가 커져 관측성이 중요해졌다.

전통적으로는 CloudWatch(지표), CloudWatch Logs(로그), X-Ray(트레이싱)로
나눠 담당했지만, 최근에는 OpenTelemetry(오픈소스 표준)가 세 요소를 함께
다루는 방식으로 수렴하는 추세다(Day 1의 관측성 3요소 표와 같은 맥락).

**ADOT(AWS Distro for OpenTelemetry)**는 OpenTelemetry의 AWS 배포판으로,
CNCF OpenTelemetry 프로젝트를 기반으로 AWS가 테스트·최적화·지원하는
SDK·계측 에이전트·컬렉터 모음이다. ADOT로 계측하면 CloudWatch, X-Ray,
OpenSearch, Amazon Managed Service for Prometheus 등 여러 AWS 모니터링
서비스로 지표·트레이스를 함께 보낼 수 있다.

- AWS 공식 문서 기준으로 AgentCore Runtime처럼 관리형 배포 환경에 ADOT가
  기본 통합된 사례가 있다는 필기 내용은, ADOT가 Lambda·ECS·App Runner 등에
  플러그인 방식으로 통합된다는 공식 설명과 방향이 일치한다.
- 트레이스 안에 세그먼트(X-Ray 용어), 그 하위에 하위 세그먼트가 있다.
  OpenTelemetry에서는 세그먼트를 루트 스팬(root span), 하위 세그먼트를 자식
  스팬(child span)에 대응시켜 **둘 다 스팬(span)**이라 부른다는 점에서 두
  용어 체계 간 대응 관계로 맞다.
- EC2 인스턴스에서는 ADOT 컬렉터를 직접 설치해야 한다(과거의 X-Ray 데몬은
  이제 쓰이지 않는 추세다). 여러 대에 반복 설치해야 한다면 AMI로
  복제하거나 유저 데이터 스크립트로 자동화하는 방법을 생각해볼 수 있다 —
  이 부분은 필기의 추측(`[해석]`)이며 직접 검증하지 않았다.

**CloudTrail**은 API 수준에서 계정 내 AWS API 호출을 기록한다. 호출자
신원, 호출 시각, 발신 IP, 요청 파라미터, 응답 값까지 남기며, 콘솔·SDK·CLI·
CloudFormation 같은 상위 서비스를 거친 호출도 모두 포함한다. 단, 트레일은
기본적으로 **관리 이벤트(control plane, 예: 리소스 생성·삭제)만** 기록하고,
**데이터 이벤트(data plane, 예: S3 `GetObject`, Lambda `Invoke`)와 네트워크
활동 이벤트는 기본 비활성이며 명시적으로 켜야 하고 추가 비용이 든다** —
"모든 API 호출을 수집한다"는 표현은 이 기본값 차이 때문에 과장일 수 있다.

## 7. Lambda 실행 모델

Lambda 함수는 **이벤트**로 호출되는 경우가 대부분이므로 이벤트 개념이
중요하다. 가장 먼저 실행되는 핸들러 함수는 **event**와 **context** 두
파라미터를 받는다. event는 JSON 형태로 전달된다.

CloudWatch 로그는 로그 그룹 > 로그 스트림(인스턴스 단위) > 로그 이벤트
계층으로 쌓인다. 호출마다 고유한 request ID가 생성된다.

### 동기 호출과 비동기 호출

"호출은 부메랑임 돌아옴"이라는 필기는 **동기(synchronous) 호출**을 가리킨다.
AWS 공식 문서 기준으로 Lambda 호출 방식은 두 가지다.

| 호출 방식 | InvocationType | 동작 |
|---|---|---|
| 동기 | `RequestResponse`(기본값) | 호출자가 응답을 기다림 — 결과가 그대로 돌아옴(부메랑) |
| 비동기 | `Event` | 호출자는 큐에 넣고 바로 반환 — 결과를 기다리지 않음 |

API Gateway → Lambda 연동은 보통 동기 호출이다(사용자가 응답을 기다려야
하므로). 반면 S3 이벤트, EventBridge처럼 "발생시키고 결과를 기다리지 않는"
트리거는 비동기 호출로 동작하며, Lambda가 이벤트를 큐에 넣은 뒤 처리하고
실패 시 재시도(기본 최대 2회 추가 시도)한다.

### 콜드 스타트와 웜 스타트

Lambda 같은 서버리스 서비스도 호출될 때마다 EC2처럼 격리된 실행 환경
(인스턴스에 대응)이 필요하다. 다만 매 호출마다 새로 만드는 게 아니라, 이미
쓰던 실행 환경을 작업이 끝난 뒤에도 일정 시간 유지해 재사용한다.

AWS 공식 문서 기준으로 정리하면:

- **콜드 스타트**: Lambda API로 요청이 오면 코드를 다운로드하고 실행
  환경을 초기화하는 과정(init) — 이 초기화 단계가 콜드 스타트다.
- **웜 스타트**: 초기화(init) 없이 이미 준비된 실행 환경을 재사용하는
  경우다.

필기의 "init 스타트 → 콜드스타트 / init 없으면 웜스타트" 구분은 공식
설명과 일치한다. 콜드 스타트는 전체 호출의 1% 미만에서 발생하며 지속
시간은 100ms 미만에서 1초 이상까지 다양하다고 문서에 명시되어 있다.

## 8. API Gateway: API 유형 선택

REST API를 구축하려면 결국 CRUD에 대응하는 HTTP 메서드(GET/POST/PUT/
DELETE)를 호출해야 하고, 이는 HTTP 프로토콜의 표준이다. AWS는 모든 리소스를
경로(path)로 구분하며, API Gateway에서는 리소스를 만들고 그 리소스에
메서드(GET/POST/PUT/DELETE)를 붙이는 순서로 구성한다.

API Gateway가 제공하는 API 유형은 REST API, HTTP API, WebSocket API
세 가지다. AWS 공식 문서 기준으로 선택 기준을 정리하면 다음과 같다.

| 유형 | 특징 | 선택 기준 |
|---|---|---|
| REST API | 기능이 더 많음(API 키, 클라이언트별 스로틀링, 요청 검증, WAF 연동, 프라이빗 엔드포인트 등) | 고급 기능이 필요할 때 |
| HTTP API | 기능은 최소화, 가격이 더 낮음, 서버리스 워크로드에 최적화 | API 프록시 기능만 필요할 때 |
| WebSocket API | 상태를 유지하는 양방향 통신(채팅, 실시간 대시보드) | 실시간 양방향 통신이 필요할 때 |

**필기와 다른 점**: 필기는 "REST API가 가장 강력하고 많이 쓰인다"고
적었는데, "기능이 더 많다"는 것까지는 맞지만 AWS 공식 문서는 REST API가
HTTP API보다 **가격이 더 높다**고 명시하며, 서버리스 워크로드에는 오히려
HTTP API를 최적화된 선택으로 권장한다. "강력함"과 "널리 쓰임"은 다른
축이므로, 실무에서는 필요한 기능 수준에 따라 선택하는 것이 정확하다.

## 핵심 요약

1. 컨테이너 이미지는 정적, 컨테이너는 CPU·메모리가 할당되어 실행 중인
   동적 상태다(`docker build/pull/push/run`으로 전환).
2. ECS/EKS는 관리(오케스트레이션), EC2/Fargate는 호스팅, ECR은 이미지
   레지스트리로 역할이 나뉜다. ECS의 태스크는 1회성, 서비스는 개수를
   유지하는 장기 실행이다.
3. CodeDeploy 블루/그린 배포는 all-at-once(즉시 100%), canary(첫 증분 후
   나머지 한 번에), linear(동일 비율을 반복 전환) 세 가지다.
4. 관측성 3요소(지표·로그·트레이스)는 전통적으로 CloudWatch·X-Ray가
   나눠 맡았고, 최근에는 OpenTelemetry(AWS 배포판 ADOT)로 수렴한다.
   CloudTrail은 계정의 모든 API 호출 기록을 남긴다.
5. Lambda 핸들러는 event·context 두 파라미터를 받고, 콜드 스타트는
   실행 환경 초기화(init)가 포함된 호출, 웜 스타트는 기존 환경을
   재사용하는 호출이다.
6. API Gateway는 REST(기능 최다, 가격 높음), HTTP(기능 최소, 저가·서버리스
   최적화), WebSocket(양방향 실시간) 세 유형으로 나뉜다.

## 확인하지 못한 것

이 노트는 강의 필기를 AWS 공식 문서와 대조한 것까지이며, 아래는 직접
실행해 검증하지 않았다.

- Docker 이미지를 실제로 빌드해 ECR에 push하고 ECS 태스크로 실행하는 전체
  흐름.
- ECS 서비스가 태스크 실패 시 실제로 재생성하는 동작, EKS 클러스터를
  직접 구성해 가용 영역 분산을 확인하는 것.
- CodeDeploy canary/linear 배포를 실제로 실행해 트래픽 전환 로그를 확인하는
  것 — 사전 정의 구성표의 정확한 수치(퍼센트·간격)는 문서 확인으로
  대체했고 직접 실행하지 않았다.
- EC2 인스턴스에 ADOT 컬렉터를 직접 설치해 트레이스를 수집하는 과정, AMI
  복제 대비 유저 데이터 방식의 실효성 비교(필기의 추측을 검증하지 않음).
- Lambda 함수를 만들어 콜드 스타트/웜 스타트를 실제로 관찰하고 request ID를
  확인하는 것. 동기·비동기 호출을 각각 실제로 트리거해 응답 대기 여부와
  재시도 동작 차이를 관찰하는 것도 하지 않았다.
- API Gateway로 REST/HTTP API를 각각 만들어 리소스·메서드 구성 차이를
  실습으로 비교하는 것.
- Fargate에서 특권 컨테이너나 `hostNetwork` 설정을 실제로 시도해 오류를
  재현하는 것 — 이 제약은 강의 필기에 없어 전부 공식 문서로 보강한 내용이다.
- "시리즈 7/8 미션"으로 언급된 SAM 기반 백엔드 + S3/CloudFormation 프론트엔드
  구성, DynamoDB 연동, 코딩 에이전트 미션은 이 노트의 범위 밖이다.

## 공식 자료

- [Type — ECS service vs standalone task](https://docs.aws.amazon.com/help-panel/AmazonECS/latest/console/hp-service-update-applicationtype.html)
- [Working with deployment configurations in CodeDeploy](https://docs.aws.amazon.com/codedeploy/latest/userguide/deployment-configurations.html)
- [CodeDeploy primary components — Deployment configuration](https://docs.aws.amazon.com/codedeploy/latest/userguide/primary-components.html)
- [CodeDeploy blue/green deployments for Amazon ECS](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/deployment-type-bluegreen.html)
- [Amazon EKS architecture — Control plane](https://docs.aws.amazon.com/eks/latest/userguide/eks-architecture.html)
- [AWS Distro for OpenTelemetry and AWS X-Ray](https://docs.aws.amazon.com/xray/latest/devguide/xray-services-adot.html)
- [AWS X-Ray concepts — segment/subsegment ↔ OpenTelemetry span 대응](https://docs.aws.amazon.com/xray/latest/devguide/xray-concepts.html)
- [Management and governance — AWS CloudTrail](https://docs.aws.amazon.com/whitepapers/latest/aws-overview/management-governance.html)
- [Managing CloudTrail Lake event data stores — 기본은 관리 이벤트만 기록, 데이터 이벤트는 opt-in](https://docs.aws.amazon.com/help-panel/awscloudtrail/latest/console/create-trail-event-type.html)
- [Understanding the Lambda execution environment lifecycle — Cold starts and latency](https://docs.aws.amazon.com/lambda/latest/dg/lambda-runtime-environment.html)
- [Choose an API type (API Gateway)](https://docs.aws.amazon.com/help-panel/apigateway/latest/console/choose-api-type.html)
- [Choose between REST APIs and HTTP APIs](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-vs-rest.html)
- [Lambda Invoke API — RequestResponse vs Event](https://docs.aws.amazon.com/lambda/latest/api/API_Invoke.html)
- [Amazon EKS best practices — Fargate cannot run privileged containers or hostNetwork/hostPort](https://docs.aws.amazon.com/eks/latest/best-practices/pod-security.html)
