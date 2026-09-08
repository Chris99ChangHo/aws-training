#!/bin/bash
# setup_fullstack_pipeline.sh — 풀스택 모노레포를 CodeCommit에 올리고
# dining-web-pipeline(agent → api → frontend 순차 배포) 구성을 안내합니다.
#
# 이 스크립트는 1단계(모노레포 조립 + CodeCommit push)까지 자동화합니다.
# 2단계(CodeBuild 프로젝트 3개, CodePipeline 생성/편집)는 콘솔 작업이
# 섞여 있어(위저드 Deploy 스테이지에 CodeBuild를 고를 수 없어 생성 후
# 편집이 필요) 이 스크립트 아래에 안내 명령으로 남겨둡니다.
#
# 사전 조건:
#   - git, pip install git-remote-codecommit 설치됨
#   - DiningConcierge/ 가 이 디렉터리(labs/Mission/07-dining-web-service/)에 이미 존재
#     (04 또는 06 미션에서 만든 프로젝트를 복사해서 준비)
#   - frontend/.env.production에 VITE_API_URL 기록됨

set -euo pipefail

REGION="us-west-2"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== 0. 사전 확인 ==="
if [ ! -d "DiningConcierge" ]; then
    echo "❌ DiningConcierge/ 가 없습니다."
    echo "   agentcore create --name DiningConcierge --framework Strands --model-provider Bedrock --memory none"
    echo "   또는 앞 미션의 DiningConcierge/ 를 이 디렉터리로 복사하세요."
    exit 1
fi

if [ -d "DiningConcierge/.git" ]; then
    echo "⚠️  DiningConcierge/.git 발견 — 제거합니다 (남기면 파일이 push되지 않음)"
    rm -rf DiningConcierge/.git
fi

echo ""
echo "=== 1. git-remote-codecommit 설치 확인 ==="
if ! python3 -c "import git_remote_codecommit" 2>/dev/null; then
    echo "git-remote-codecommit 설치 중..."
    pip3 install git-remote-codecommit
else
    echo "이미 설치됨"
fi

echo ""
echo "=== 2. CodeCommit 리포지토리 생성 ==="
if aws codecommit get-repository --repository-name dining-web --region "$REGION" >/dev/null 2>&1; then
    echo "리포지토리 이미 존재: dining-web"
else
    aws codecommit create-repository --repository-name dining-web --region "$REGION" > /dev/null
    echo "리포지토리 생성: dining-web"
fi

echo ""
echo "=== 3. git init 및 push ==="
if [ ! -d ".git" ]; then
    git init -b main
fi

if ! git remote get-url origin >/dev/null 2>&1; then
    git remote add origin "codecommit::${REGION}://dining-web"
fi

git add .
git commit -m "풀스택 모노레포 초기 커밋: DiningConcierge + api + frontend" || echo "커밋할 변경사항 없음"
git push -u origin main

echo ""
echo "=== 완료: 1단계(모노레포 조립 + push) ==="
echo ""
echo "=== 다음 단계(수동, 콘솔 작업 포함) ==="
cat <<'EOF'

[2단계: CodeBuild 프로젝트 3개 생성]

aws codebuild create-project --name dining-web-agent \
    --source type=CODEPIPELINE,buildspec=buildspec-agent.yml \
    --artifacts type=CODEPIPELINE \
    --environment type=LINUX_CONTAINER,image=aws/codebuild/amazonlinux-x86_64-standard:5.0,computeType=BUILD_GENERAL1_SMALL \
    --service-role <AGENT_DEPLOY_ROLE_ARN> --region us-west-2

aws codebuild create-project --name dining-web-api \
    --source type=CODEPIPELINE,buildspec=buildspec-api.yml \
    --artifacts type=CODEPIPELINE \
    --environment type=LINUX_CONTAINER,image=aws/codebuild/amazonlinux-x86_64-standard:5.0,computeType=BUILD_GENERAL1_SMALL \
    --service-role <API_DEPLOY_ROLE_ARN> --region us-west-2

aws codebuild create-project --name dining-web-frontend \
    --source type=CODEPIPELINE,buildspec=buildspec-web.yml \
    --artifacts type=CODEPIPELINE \
    --environment "type=LINUX_CONTAINER,image=aws/codebuild/amazonlinux-x86_64-standard:5.0,computeType=BUILD_GENERAL1_SMALL,environmentVariables=[{name=WEB_BUCKET,value=dining-web-<ACCOUNT_ID>},{name=CLOUDFRONT_DIST_ID,value=<DIST_ID>}]" \
    --service-role <FRONTEND_DEPLOY_ROLE_ARN> --region us-west-2

[3단계: CodePipeline 콘솔 위저드]
  - Source: CodeCommit dining-web / main (EventBridge 규칙 자동 생성)
  - Build 스테이지: dining-web-agent 지정 (위저드는 여기까지만 지원)
  - 생성 후 편집: Build 스테이지 삭제 → Deploy 스테이지 추가
    - Action 1: dining-web-agent, RunOrder 1
    - Action 2: dining-web-api,   RunOrder 2
    - Action 3: dining-web-frontend, RunOrder 3

[4단계: 검증]
  - 작은 변경(예: README 한 줄)을 커밋 후 git push
  - CodePipeline 콘솔에서 자동 시작 확인 (Release change 수동 실행 금지)
  - 3액션 모두 Succeeded 확인

EOF
