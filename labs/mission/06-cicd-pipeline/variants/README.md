# 게이트 차단 실증용 변형 버전

이 폴더는 "게이트 차단과 복구" 미션(prompts.txt 2번)에서 쓸 두 가지
`main.py` 변형을 미리 준비해둔 것입니다. 실제 실습 시 아래 순서로
사용합니다.

## 사용 순서

1. **정상 배포 확인** (선행 미션 "다이닝 에이전트 배포 파이프라인" 완료 상태)
   ```bash
   agentcore invoke "강남역 근처 이탈리안 식당 추천해 주세요"
   # → 트라토리아 벨라가 포함된 응답 확인
   ```

2. **개악 버전으로 차단 실증**
   ```bash
   cp variants/main_broken.py DiningConcierge/app/DiningConcierge/main.py
   cd DiningConcierge
   zip -r ../source.zip . \
       -x "agentcore/.env.local" \
       -x "agentcore/.cli/*" \
       -x "app/DiningConcierge/.venv/*"
   cd ..
   aws s3 cp source.zip s3://dining-src-<ACCOUNT_ID>/source.zip --region us-west-2
   # → CodePipeline 콘솔에서 Test 스테이지 Failed, Deploy 미실행 확인
   ```

3. **CodeBuild 로그 판독**
   - CodePipeline 콘솔 > 실패한 실행 > Test 스테이지 > Details 링크
   - `evals/gate_eval.py` 출력에서 케이스 3(공휴일 질문)의 점수 0.0과
     평균 점수(약 0.67 < 0.7) 확인

4. **복구 버전으로 자동 재배포**
   ```bash
   cp variants/main_recovered.py DiningConcierge/app/DiningConcierge/main.py
   cd DiningConcierge
   zip -r ../source.zip . \
       -x "agentcore/.env.local" \
       -x "agentcore/.cli/*" \
       -x "app/DiningConcierge/.venv/*"
   cd ..
   aws s3 cp source.zip s3://dining-src-<ACCOUNT_ID>/source.zip --region us-west-2
   # → Test·Deploy 모두 Succeeded, invoke 응답에 가격대·위치 포함 확인
   ```

5. **앱에서 비교**
   - `DiningConcierge/app.py`(streamlit run app.py)로 통과/차단 상태의
     응답 변화를 브라우저에서 확인합니다.

## 변경 지점 요약

| 파일 | 시스템 프롬프트 | 게이트 결과 |
|---|---|---|
| `main.py` (원본, 06-cicd-pipeline 최초 버전) | 추측 금지 규칙 | 통과 (평균 1.0) |
| `main_broken.py` | 역지시(추측 허용)로 교체 | 차단 (케이스 3 실패, 평균 약 0.67) |
| `main_recovered.py` | 추측 금지 규칙 복구 + 가격대·위치 안내 추가 | 통과 (평균 1.0) |
