# 미션 8 (코딩 에이전트 구축) — RUN_GUIDE

4단계 전체의 실행 명령과 스크린샷 체크리스트.
검증 결과·트러블슈팅 같은 서술 내용은 같은 폴더의 `README.md`에 있다.

**스크린샷은 전부 이 폴더(미션 루트)에 캡처 완료됨** (`image.png` ~
`image-9.png`). README.md에 이미 삽입되어 있다.

---

## 준비

```bash
cd ~/aws-training/labs/mission/08-coding-agent-build/01-dining-coder
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
aws sts get-caller-identity --region us-west-2   # Account 표시 확인
```

---

## 1단계 (01-dining-coder/) — ✅ 스크린샷 완료 (image.png ~ image-4.png)

```bash
python3 tools.py                    # image.png    — 경계 테스트 5케이스
python3 coder.py                    # image-1.png  — 도구 호출 로그 + 요약
python3 -c "from coder import agent; print(str(agent('작성한 함수를 실제로 실행해서 한우명가 35명 요청이 거절되고 25명 요청이 통과하는지 확인해 주세요')))"
                                     # image-2.png  — 35명 거절/25명 통과
streamlit run console_coder.py      # image-3.png, image-4.png — 콘솔 화면
```

---

## 2단계 (01-dining-coder/) — 캡처 필요: **1장**

```bash
python3 orchestrator.py
```

3~5분 걸린다(Coder→품질Reviewer→보안Reviewer→Tester를 라운드마다 순차
호출). 마지막 줄 `최종 상태: APPROVED (라운드: N)`이 나오면 성공.

📸 **`image-5.png`** — 터미널 로그 마지막 부분. `token_usage={...}` 줄과
`최종 상태: APPROVED` 줄이 함께 보이게 캡처(로그가 길면 그 부분만 스크롤).
![alt text](image-5.png)
ㄴ 로그가 엄청 길어서 그 부분만 캡처함

> `reviewer.py`·`tester.py` 단독 실행, `app.py` 브라우저 확인은 위
> 스크린샷과 같은 정보를 보여주므로 생략 가능 — 필요하면 아래 명령으로
> 직접 확인만 하고 캡처는 안 해도 된다.
> ```bash
> streamlit run app.py   # http://localhost:8501, 확인만
> ```

---

## 3단계 (02-coding-runtime/) — 캡처 필요: **3장**

```bash
cd ../02-coding-runtime/CodingService
agentcore status
```

📸 **`image.png`** — `CodingService: Deployed - Runtime: READY` 줄이
보이는 출력.

![alt text](image-6.png)

```bash
cd ..
python3 test_invoke.py
```

3~5분 걸린다. `git clone exit: 0`과 `git push exit: 0`이 함께 나오면
성공.

📸 **`image-1.png`** — `git clone exit`·`git push exit` 두 줄이 함께
보이는 로그.

![alt text](image-7.png)

```bash
python3 test_multisession.py
```

1분 정도. "세션 A가 본 워크스페이스"에 `bob.txt` 없음, "세션 B가 본
워크스페이스"에 `alice.txt` 없음, 마지막 "판정" 줄까지 확인.

📸 **`image-2.png`** — 세션 A·B 교차 조회 결과 + 판정 줄.
![alt text](image-8.png)

> CodeCommit 콘솔 커밋 화면, S3 콘솔 work-log.json, 팀 콘솔 브라우저
> 화면은 위 두 스크린샷이 이미 같은 사실(코드 push 성공, 세션 격리)을
> 증명하므로 생략. 궁금하면 아래로 직접 확인만:
> ```bash
> aws s3 cp s3://coding-service-files-$(aws sts get-caller-identity --query Account --output text)/work-log.json /tmp/work-log.json --region us-west-2 && cat /tmp/work-log.json
> streamlit run console_app.py   # 확인만
> ```

---

## 4단계 (03-coding-microvm/) — 캡처 필요: **2장**

```bash
cd ../03-coding-microvm
python3 test_isolation.py
```

1~2분. 3개 섹션(파일시스템 격리·테넌트 간 격리·상태 소멸) 전부 "확인
완료"로 끝나고 마지막에 "모든 격리 테스트 통과"가 나오면 성공.

📸 **`image.png`** — 3개 섹션 결과 + 마지막 "모든 격리 테스트 통과" 줄.

```bash
python3 test_integration.py
```

1~2분. `[Tester] 결과: ## ✅ 테스트 결과: passed=N failed=0`이 나오면
성공.

📸 **`image-1.png`** — Tester 최종 결과(`passed=N failed=0`) 부분.
![alt text](image-9.png)
ㄴ 로그가 너무 길어서 끝부분만 캡처함

> `sandbox_runner.py`(실행 사이클), `test_suspend_resume.py`(도전
> 과제), `sandbox_console.py`(브라우저)는 위 두 스크린샷이 이미 핵심
> 사실(MicroVM 정상 작동, 격리 확인)을 증명하므로 생략. 실행만 확인하고
> 싶으면:
> ```bash
> python3 sandbox_runner.py         # 확인만
> python3 test_suspend_resume.py    # 확인만
> streamlit run sandbox_console.py  # 확인만
> ```

---

## 캡처 총정리 (완료 상태)

| 파일명 | 내용 | 상태 |
|---|---|---|
| `image.png` | 도구 경계 테스트 | ✅ 완료 |
| `image-1.png` | 코딩 에이전트 실행 | ✅ 완료 |
| `image-2.png` | 자기 실행 검증(35명/25명) | ✅ 완료 |
| `image-3.png`, `image-4.png` | 콘솔 화면 | ✅ 완료 |
| `image-5.png` | 자기 교정 루프 전체 로그 | ✅ 완료 |
| `image-6.png` | Runtime READY | ✅ 완료 |
| `image-7.png` | git clone/push 성공 | ✅ 완료 |
| `image-8.png` | 멀티세션 격리 확인 | ✅ 완료 |
| `image-9.png` | 격리 3축 통과 | ✅ 완료 |

**Coder+Tester(MicroVM) 통합 결과(`test_integration.py`)는 캡처하지
않았다** — 텍스트 검증 결과(29 passed 0 failed)만 README에 기록.
필요하면 추가로 캡처해서 `image-10.png`로 저장하면 반영한다.

---

## 정리 (과금 리소스, 스크린샷 다 찍은 뒤)

```bash
cd ../02-coding-runtime/CodingService && agentcore destroy -y
```

NAT 게이트웨이·VPC 엔드포인트·S3 Files는 콘솔에서 수동 삭제 권장.
워크숍 계정은 만료 시 자동 정리되므로 지금 당장 안 해도 된다.
