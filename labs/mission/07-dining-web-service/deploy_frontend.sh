#!/bin/bash
# deploy_frontend.sh — Cloudscape 채팅 앱을 S3+CloudFront로 정적 호스팅
#
# 사전 조건:
#   - AWS 자격증명 유효
#   - frontend/.env.production에 VITE_API_URL=<dining-web API URL>(끝 슬래시 제외) 기록
#   - dining-web SAM 스택이 이미 배포되어 API URL을 알고 있음
#
# 실행 방법: bash deploy_frontend.sh
#
# 이 스크립트는:
#   1. frontend/를 프로덕션 빌드
#   2. S3 버킷 dining-web-<ACCOUNT_ID> 생성(퍼블릭 액세스 차단 유지)
#   3. dist/를 버킷에 업로드
#   4. CloudFront 배포를 OAC로 생성(이미 있으면 스킵 안내)
#   5. 배포 완료 후 URL 안내
#
# 주의: CloudFront 배포는 최초 생성 후 배포 완료까지 15~20분 정도 걸립니다.
# 이 스크립트는 배포 생성까지만 하고, 완료 대기는 별도로 확인해야 합니다.

set -euo pipefail

REGION="us-west-2"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== 0. 사전 확인 ==="
aws sts get-caller-identity --region "$REGION" > /tmp/caller_identity_frontend.json
ACCOUNT_ID=$(python3 -c "import json; print(json.load(open('/tmp/caller_identity_frontend.json'))['Account'])")
echo "Account ID: $ACCOUNT_ID"

WEB_BUCKET="dining-web-${ACCOUNT_ID}"

if [ ! -f "frontend/.env.production" ]; then
    echo "❌ frontend/.env.production이 없습니다."
    echo "   먼저 다음을 실행하세요:"
    echo "   echo 'VITE_API_URL=<YOUR_API_URL>' > frontend/.env.production"
    exit 1
fi

echo ""
echo "=== 1. 프로덕션 빌드 ==="
cd frontend
npm run build
cd ..
echo "빌드 완료: frontend/dist/"

echo ""
echo "=== 2. S3 버킷 생성(비공개 유지) ==="
if aws s3api head-bucket --bucket "$WEB_BUCKET" --region "$REGION" 2>/dev/null; then
    echo "버킷 이미 존재: $WEB_BUCKET"
else
    aws s3api create-bucket \
        --bucket "$WEB_BUCKET" \
        --region "$REGION" \
        --create-bucket-configuration LocationConstraint="$REGION"
    echo "버킷 생성: $WEB_BUCKET (퍼블릭 액세스 차단은 기본값 유지)"
fi

echo ""
echo "=== 3. 빌드 산출물 업로드 ==="
aws s3 sync frontend/dist/ "s3://${WEB_BUCKET}/" --region "$REGION"
echo "업로드 완료"

echo ""
echo "=== 4. CloudFront 배포 확인/생성 ==="

EXISTING_DIST=$(aws cloudfront list-distributions --region us-east-1 \
    --query "DistributionList.Items[?Origins.Items[0].DomainName=='${WEB_BUCKET}.s3.${REGION}.amazonaws.com'].Id" \
    --output text 2>/dev/null || echo "")

if [ -n "$EXISTING_DIST" ] && [ "$EXISTING_DIST" != "None" ]; then
    echo "CloudFront 배포 이미 존재: $EXISTING_DIST"
    DIST_DOMAIN=$(aws cloudfront get-distribution --id "$EXISTING_DIST" \
        --query "Distribution.DomainName" --output text)
    echo "도메인: https://${DIST_DOMAIN}"
else
    echo "새 CloudFront 배포를 생성합니다 (OAC 방식)..."

    OAC_ID=$(aws cloudfront create-origin-access-control \
        --origin-access-control-config "Name=dining-web-oac,SigningProtocol=sigv4,SigningBehavior=always,OriginAccessControlOriginType=s3" \
        --query "OriginAccessControl.Id" --output text)
    echo "OAC 생성: $OAC_ID"

    DIST_CONFIG=$(cat <<EOF
{
  "CallerReference": "dining-web-$(date +%s)",
  "Comment": "dining-web frontend",
  "Enabled": true,
  "DefaultRootObject": "index.html",
  "Origins": {
    "Quantity": 1,
    "Items": [
      {
        "Id": "dining-web-s3-origin",
        "DomainName": "${WEB_BUCKET}.s3.${REGION}.amazonaws.com",
        "OriginAccessControlId": "${OAC_ID}",
        "S3OriginConfig": {"OriginAccessIdentity": ""}
      }
    ]
  },
  "DefaultCacheBehavior": {
    "TargetOriginId": "dining-web-s3-origin",
    "ViewerProtocolPolicy": "redirect-to-https",
    "AllowedMethods": {"Quantity": 2, "Items": ["GET", "HEAD"]},
    "CachePolicyId": "658327ea-f89d-4fab-a63d-7e88639e58f6"
  }
}
EOF
)
    echo "$DIST_CONFIG" > /tmp/dining-web-cf-config.json

    CREATE_OUTPUT=$(aws cloudfront create-distribution --distribution-config file:///tmp/dining-web-cf-config.json)
    DIST_ID=$(echo "$CREATE_OUTPUT" | python3 -c "import json,sys; print(json.load(sys.stdin)['Distribution']['Id'])")
    DIST_DOMAIN=$(echo "$CREATE_OUTPUT" | python3 -c "import json,sys; print(json.load(sys.stdin)['Distribution']['DomainName'])")
    DIST_ARN=$(echo "$CREATE_OUTPUT" | python3 -c "import json,sys; print(json.load(sys.stdin)['Distribution']['ARN'])")

    echo "CloudFront 배포 생성: $DIST_ID"
    echo "도메인: https://${DIST_DOMAIN}"

    echo ""
    echo "=== 5. 버킷 정책 적용 (이 배포만 허용) ==="
    BUCKET_POLICY=$(cat <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowCloudFrontServicePrincipal",
      "Effect": "Allow",
      "Principal": {"Service": "cloudfront.amazonaws.com"},
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::${WEB_BUCKET}/*",
      "Condition": {
        "StringEquals": {"AWS:SourceArn": "${DIST_ARN}"}
      }
    }
  ]
}
EOF
)
    echo "$BUCKET_POLICY" > /tmp/dining-web-bucket-policy.json
    aws s3api put-bucket-policy --bucket "$WEB_BUCKET" --policy file:///tmp/dining-web-bucket-policy.json --region "$REGION"
    echo "버킷 정책 적용 완료"

    echo ""
    echo "⏳ CloudFront 배포는 완료까지 15~20분 정도 걸립니다."
    echo "   상태 확인: aws cloudfront get-distribution --id ${DIST_ID} --query 'Distribution.Status'"
fi

echo ""
echo "=== 완료 ==="
echo "이후 갱신 루프:"
echo "  npm run build (frontend/)"
echo "  aws s3 sync frontend/dist/ s3://${WEB_BUCKET}/ --delete --region ${REGION}"
echo "  aws cloudfront create-invalidation --distribution-id <DIST_ID> --paths '/*'"
