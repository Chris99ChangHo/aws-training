# DevOps Engineering on AWS — 이론 정리

## 폴더가 갈리는 이유

`notes/`는 **근거의 출처**로 갈립니다. 섞으면 "수업에서 들은 것"과 "AI가 아는
것"을 독자가 구분할 수 없습니다. 규약은 `.kiro/steering/ai-attribution.md`에
있습니다.

| 폴더 | 근거 | 성격 |
|---|---|---|
| 수업 필기 원본 | 별도 문서(Google Docs) | 가공하지 않습니다. 이 리포에는 정리본만 둡니다 |
| [`lecture/`](./lecture) | 강의 + AWS 공식 문서 대조 | 필기에 없던 사실을 추가하지 않습니다. 보강한 부분은 출처를 답니다 |
| `practice/` | 실습에서 측정한 값 | **아직 없습니다** — 실습이 진행되면 추가합니다 |

## 강의 정리

| 노트 | 범위 |
|---|---|
| [`lecture/day-1-cicd-and-iac-basics.md`](./lecture/day-1-cicd-and-iac-basics.md) | 모놀리스→MSA, DevOps 방법론, AMI·컨테이너 격리, CloudFormation 구조, CodePipeline 개요, CLI 인증 |
| [`lecture/day-2-codebuild-codedeploy-sam.md`](./lecture/day-2-codebuild-codedeploy-sam.md) | 컨테이너 빌드, CodeBuild 빌드스펙, CodeDeploy 배포 그룹, Auto Scaling, 로드밸런서, AWS SAM |
| [`lecture/day-3-containers-observability-serverless.md`](./lecture/day-3-containers-observability-serverless.md) | Docker/ECS/EKS/Fargate/ECR 역할 구분, 블루/그린 배포 트래픽 전환, 관측성(ADOT·X-Ray·CloudTrail), Lambda 실행 모델, API Gateway 유형 |

## 실습에서 도출한 정리

아직 없습니다. 이 과정의 실습은 진행 예정입니다.

## 강의 노트의 공통 골격

```
# Day N — 제목
> 교육일 / AWS 공식 문서 확인일 / 범위
> AI 협업 표기
## 학습 목표
## 1..N 본문
## 복습 체크  또는  핵심 요약
## 확인하지 못한 것
## 공식 자료
```

다른 과정과 같은 골격입니다. 자세한 설명은
[`security-engineering/notes/README.md`](../../security-engineering/notes)를
보세요.

`확인하지 못한 것`은 **필수**입니다. 무엇을 검증하지 않았는지 적지 않으면
읽는 사람이 전부 확인된 것으로 오해합니다. 이 과정은 리포에 실습 코드가 아직
없으므로, 세 노트 모두 강의 내용을 AWS 공식 문서와 대조한 것까지이고 직접
실행해 확인한 것이 아닙니다.
