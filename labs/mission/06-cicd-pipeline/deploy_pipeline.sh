#!/bin/bash
# deploy_pipeline.sh — dining-pipeline 구성 스크립트
#
# 사전 조건: AWS 자격증명이 유효한 상태(aws sts get-caller-identity로 확인)
# 실행 방법: bash deploy_pipeline.sh
#
# 이 스크립트는 다음을 순서대로 만듭니다:
#   1. 버전 관리를 켠 S3 버킷 dining-src-<ACCOUNT_ID>
#   2. IAM 역할 2개(CodeBuild용, CodePipeline용) — 최소 권한
#   3. CodeBuild 프로젝트 dining-test, dining-deploy
#   4. CodePipeline dining-pipeline (S3 소스 폴링 → Test → Deploy)
#   5. DiningConcierge/ 를 source.zip으로 묶어 업로드해 첫 실행 트리거
#
# 리전은 us-west-2로 고정합니다.
#
# 소스 감지 방식: PollForSourceChanges=true(5분 폴링)를 쓴다. false로 두면
# S3 이벤트 알림 + EventBridge 규칙이 별도로 있어야 새 업로드가 실행을
# 트리거한다 — 이 스크립트는 그 인프라를 만들지 않으므로 false는 재현되지
# 않는 실습이 된다(실제로 겪은 문제: source.zip 재업로드가 새 실행을
# 만들지 않음).

# set -e 예외: 리포 규칙(shell-conventions)은 종료 코드로 상태를 구분하는
# 스크립트에서 set -e를 금지한다. 이 스크립트는 그런 경우가 아니다 — 모든
# 단계가 순서대로 성공해야만 의미가 있는 1회성 인프라 구축 스크립트이므로,
# 중간 실패 시 즉시 중단하는 것이 안전하다.
set -euo pipefail

REGION="us-west-2"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== 0. 사전 확인 ==="
aws sts get-caller-identity --region "$REGION" > /tmp/caller_identity.json
ACCOUNT_ID=$(python3 -c "import json; print(json.load(open('/tmp/caller_identity.json'))['Account'])")
echo "Account ID: $ACCOUNT_ID"

SRC_BUCKET="dining-src-${ACCOUNT_ID}"
CODEBUILD_ROLE_NAME="dining-pipeline-codebuild-role"
PIPELINE_ROLE_NAME="dining-pipeline-codepipeline-role"

echo ""
echo "=== 1. 버전 관리를 켠 S3 소스 버킷 생성 ==="
if aws s3api head-bucket --bucket "$SRC_BUCKET" --region "$REGION" 2>/dev/null; then
    echo "버킷 이미 존재: $SRC_BUCKET"
else
    aws s3api create-bucket \
        --bucket "$SRC_BUCKET" \
        --region "$REGION" \
        --create-bucket-configuration LocationConstraint="$REGION"
    echo "버킷 생성: $SRC_BUCKET"
fi
aws s3api put-bucket-versioning \
    --bucket "$SRC_BUCKET" \
    --versioning-configuration Status=Enabled \
    --region "$REGION"
echo "버전 관리 활성화 완료"

echo ""
echo "=== 2. IAM 역할 생성 ==="

# CodeBuild 실행 역할 — CloudWatch Logs + S3 소스 읽기 + AgentCore 배포 권한
CODEBUILD_TRUST_POLICY=$(cat <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {"Service": "codebuild.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF
)

if aws iam get-role --role-name "$CODEBUILD_ROLE_NAME" >/dev/null 2>&1; then
    echo "CodeBuild 역할 이미 존재: $CODEBUILD_ROLE_NAME"
else
    aws iam create-role \
        --role-name "$CODEBUILD_ROLE_NAME" \
        --assume-role-policy-document "$CODEBUILD_TRUST_POLICY" \
        --region "$REGION" > /dev/null
    echo "CodeBuild 역할 생성: $CODEBUILD_ROLE_NAME"
fi

CODEBUILD_POLICY=$(cat <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
      "Resource": "arn:aws:logs:${REGION}:${ACCOUNT_ID}:log-group:/aws/codebuild/dining-*"
    },
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:GetObjectVersion", "s3:PutObject", "s3:GetBucketVersioning",
                 "s3:GetBucketAcl", "s3:GetBucketLocation", "s3:ListBucket"],
      "Resource": [
        "arn:aws:s3:::${SRC_BUCKET}",
        "arn:aws:s3:::${SRC_BUCKET}/*",
        "arn:aws:s3:::codepipeline-${REGION}-*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": ["bedrock-agentcore:*", "bedrock:InvokeModel*", "bedrock:GetInferenceProfile"],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": ["cloudformation:*", "iam:PassRole", "iam:CreateRole", "iam:GetRole",
                 "iam:AttachRolePolicy", "iam:PutRolePolicy", "ecr:*", "logs:*",
                 "sts:AssumeRole", "ssm:GetParameter"],
      "Resource": "*"
    }
  ]
}
EOF
)

aws iam put-role-policy \
    --role-name "$CODEBUILD_ROLE_NAME" \
    --policy-name "dining-pipeline-codebuild-policy" \
    --policy-document "$CODEBUILD_POLICY" \
    --region "$REGION"

CODEBUILD_ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${CODEBUILD_ROLE_NAME}"
echo "CodeBuild 역할 ARN: $CODEBUILD_ROLE_ARN"

# CodePipeline 실행 역할
PIPELINE_TRUST_POLICY=$(cat <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {"Service": "codepipeline.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF
)

if aws iam get-role --role-name "$PIPELINE_ROLE_NAME" >/dev/null 2>&1; then
    echo "CodePipeline 역할 이미 존재: $PIPELINE_ROLE_NAME"
else
    aws iam create-role \
        --role-name "$PIPELINE_ROLE_NAME" \
        --assume-role-policy-document "$PIPELINE_TRUST_POLICY" \
        --region "$REGION" > /dev/null
    echo "CodePipeline 역할 생성: $PIPELINE_ROLE_NAME"
fi

PIPELINE_POLICY=$(cat <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:GetBucketVersioning", "s3:GetBucketAcl", "s3:GetBucketLocation",
                 "s3:ListBucket"],
      "Resource": [
        "arn:aws:s3:::${SRC_BUCKET}",
        "arn:aws:s3:::codepipeline-${REGION}-*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:GetObjectVersion", "s3:GetObjectTagging",
                 "s3:GetObjectVersionTagging", "s3:PutObject", "s3:PutObjectAcl",
                 "s3:PutObjectTagging"],
      "Resource": [
        "arn:aws:s3:::${SRC_BUCKET}/*",
        "arn:aws:s3:::codepipeline-${REGION}-*/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": ["codebuild:BatchGetBuilds", "codebuild:StartBuild"],
      "Resource": "*"
    }
  ]
}
EOF
)

aws iam put-role-policy \
    --role-name "$PIPELINE_ROLE_NAME" \
    --policy-name "dining-pipeline-codepipeline-policy" \
    --policy-document "$PIPELINE_POLICY" \
    --region "$REGION"

PIPELINE_ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${PIPELINE_ROLE_NAME}"
echo "CodePipeline 역할 ARN: $PIPELINE_ROLE_ARN"

echo ""
echo "IAM 역할 전파 대기 (10초)..."
sleep 10

echo ""
echo "=== 3. CodeBuild 프로젝트 생성 ==="

create_or_update_codebuild() {
    local name=$1
    local buildspec=$2

    if aws codebuild batch-get-projects --names "$name" --region "$REGION" --query "projects[0].name" --output text 2>/dev/null | grep -q "$name"; then
        echo "CodeBuild 프로젝트 이미 존재, 업데이트: $name"
        aws codebuild update-project \
            --name "$name" \
            --source "type=CODEPIPELINE,buildspec=DiningConcierge/${buildspec}" \
            --artifacts "type=CODEPIPELINE" \
            --environment "type=LINUX_CONTAINER,image=aws/codebuild/amazonlinux-x86_64-standard:5.0,computeType=BUILD_GENERAL1_SMALL" \
            --service-role "$CODEBUILD_ROLE_ARN" \
            --region "$REGION" > /dev/null
    else
        aws codebuild create-project \
            --name "$name" \
            --source "type=CODEPIPELINE,buildspec=DiningConcierge/${buildspec}" \
            --artifacts "type=CODEPIPELINE" \
            --environment "type=LINUX_CONTAINER,image=aws/codebuild/amazonlinux-x86_64-standard:5.0,computeType=BUILD_GENERAL1_SMALL" \
            --service-role "$CODEBUILD_ROLE_ARN" \
            --region "$REGION" > /dev/null
        echo "CodeBuild 프로젝트 생성: $name"
    fi
}

create_or_update_codebuild "dining-test" "buildspec-test.yml"
create_or_update_codebuild "dining-deploy" "buildspec-deploy.yml"

echo ""
echo "=== 4. CodePipeline 생성 ==="

PIPELINE_DEFINITION=$(cat <<EOF
{
  "pipeline": {
    "name": "dining-pipeline",
    "roleArn": "${PIPELINE_ROLE_ARN}",
    "artifactStore": {
      "type": "S3",
      "location": "codepipeline-${REGION}-${ACCOUNT_ID}"
    },
    "stages": [
      {
        "name": "Source",
        "actions": [
          {
            "name": "Source",
            "actionTypeId": {
              "category": "Source",
              "owner": "AWS",
              "provider": "S3",
              "version": "1"
            },
            "outputArtifacts": [{"name": "SourceOutput"}],
            "configuration": {
              "S3Bucket": "${SRC_BUCKET}",
              "S3ObjectKey": "source.zip",
              "PollForSourceChanges": "true"
            }
          }
        ]
      },
      {
        "name": "Test",
        "actions": [
          {
            "name": "EvalGate",
            "actionTypeId": {
              "category": "Build",
              "owner": "AWS",
              "provider": "CodeBuild",
              "version": "1"
            },
            "inputArtifacts": [{"name": "SourceOutput"}],
            "outputArtifacts": [{"name": "TestOutput"}],
            "configuration": {"ProjectName": "dining-test"}
          }
        ]
      },
      {
        "name": "Deploy",
        "actions": [
          {
            "name": "AgentCoreDeploy",
            "actionTypeId": {
              "category": "Build",
              "owner": "AWS",
              "provider": "CodeBuild",
              "version": "1"
            },
            "inputArtifacts": [{"name": "SourceOutput"}],
            "outputArtifacts": [{"name": "DeployOutput"}],
            "configuration": {"ProjectName": "dining-deploy"}
          }
        ]
      }
    ]
  }
}
EOF
)

echo "$PIPELINE_DEFINITION" > /tmp/dining-pipeline-def.json

# CodePipeline용 아티팩트 버킷이 없으면 생성
ARTIFACT_BUCKET="codepipeline-${REGION}-${ACCOUNT_ID}"
if ! aws s3api head-bucket --bucket "$ARTIFACT_BUCKET" --region "$REGION" 2>/dev/null; then
    aws s3api create-bucket \
        --bucket "$ARTIFACT_BUCKET" \
        --region "$REGION" \
        --create-bucket-configuration LocationConstraint="$REGION"
    echo "아티팩트 버킷 생성: $ARTIFACT_BUCKET"
fi

if aws codepipeline get-pipeline --name "dining-pipeline" --region "$REGION" >/dev/null 2>&1; then
    echo "파이프라인 이미 존재, 업데이트: dining-pipeline"
    aws codepipeline update-pipeline --cli-input-json file:///tmp/dining-pipeline-def.json --region "$REGION" > /dev/null
else
    aws codepipeline create-pipeline --cli-input-json file:///tmp/dining-pipeline-def.json --region "$REGION" > /dev/null
    echo "파이프라인 생성: dining-pipeline"
fi

echo ""
echo "=== 5. 소스 zip 생성 및 업로드 (첫 실행 트리거) ==="
zip -r /tmp/source.zip DiningConcierge \
    -x "DiningConcierge/agentcore/.env.local" \
    -x "DiningConcierge/agentcore/.cli/*" \
    -x "DiningConcierge/agentcore/.cache/*" \
    -x "DiningConcierge/agentcore/cdk/node_modules/*" \
    -x "DiningConcierge/agentcore/cdk/cdk.out/*" \
    -x "DiningConcierge/app/DiningConcierge/.venv/*" \
    -x "*/__pycache__/*" \
    -x "*.pyc"

aws s3 cp /tmp/source.zip "s3://${SRC_BUCKET}/source.zip" --region "$REGION"

echo ""
echo "=== 완료 ==="
echo "S3 업로드로 파이프라인 첫 실행이 트리거됩니다."
echo "상태 확인: aws codepipeline get-pipeline-state --name dining-pipeline --region ${REGION}"
echo "콘솔: https://${REGION}.console.aws.amazon.com/codesuite/codepipeline/pipelines/dining-pipeline/view"
