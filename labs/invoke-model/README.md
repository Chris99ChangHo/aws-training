# Bedrock InvokeModel — 제공자별 네이티브 포맷과 미디어 생성

![AWS](https://img.shields.io/badge/AWS-Bedrock-orange?logo=amazonaws&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.14-blue?logo=python&logoColor=white)
![boto3](https://img.shields.io/badge/boto3-1.43-232F3E?logo=amazonaws&logoColor=white)
![Meta Llama](https://img.shields.io/badge/Meta-Llama_4_Scout-0467DF?logo=meta&logoColor=white)
![Anthropic](https://img.shields.io/badge/Anthropic-Claude_Sonnet_4.6-191919?logo=anthropic&logoColor=white)

Converse API의 추상화를 걷어내고 `InvokeModel`을 직접 호출해, 모델
제공자마다 요청·응답 포맷이 어떻게 다른지 확인한 실습입니다.

## 아키텍처

```
boto3 bedrock-runtime
   │
   ├── invoke_text.py      InvokeModel                    Llama 4 Scout
   │      └─ prompt: 특수 토큰이 박힌 단일 문자열
   │         응답: result["generation"]
   │
   ├── invoke_stream.py    InvokeModelWithResponseStream   Claude Sonnet 4.6
   │      └─ messages 배열 + anthropic_version
   │         응답: message_start / content_block_delta / message_stop ...
   │
   ├── generate_image.py   InvokeModel                     Nova Canvas
   │      └─ 응답: base64 → PNG 파일로 저장
   │
   └── generate_video.py   StartAsyncInvoke + get_async_invoke   Nova Reel
          └─ 응답 본문에 비디오가 없음 → S3 출력 경로로 수신
```

## 이 실습의 핵심 — 같은 API, 다른 body

`InvokeModel`은 요청 본문을 검사하지 않고 모델에 그대로 전달합니다.
따라서 제공자별 포맷을 호출자가 맞춰야 합니다.

| 모델 | 요청 형태 | 응답 키 |
|---|---|---|
| Llama 4 Scout | `prompt` 단일 문자열 (`<\|begin_of_text\|>` 등 헤더 토큰으로 역할 구분) | `generation` |
| Claude Sonnet 4.6 | `messages` 배열 + `anthropic_version` | `content` 블록 배열 |
| Nova Canvas | `taskType` + `textToImageParams` | `images[0]` (base64) |
| Nova Reel | `taskType` + `textToVideoParams` | 없음 — S3로 출력 |

Converse API를 쓰면 이 차이가 감춰집니다. 반대로 말하면, 제공자 고유
파라미터를 써야 할 때는 `InvokeModel`이 필요합니다.

스트리밍도 텍스트 델타만 오지 않습니다. `invoke_stream.py`가 모든 이벤트
타입을 그대로 출력하는 이유는, UI에 붙일 때 `content_block_delta`만
골라 써야 한다는 걸 눈으로 확인하기 위함입니다.

## 실행 방법

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python invoke_text.py       # Llama 4, 기본 us-west-2
python invoke_stream.py     # Claude 스트리밍, 기본 us-west-2
python generate_image.py    # Nova Canvas, 기본 us-east-1
python generate_video.py    # Nova Reel, 기본 us-east-1
```

각 스크립트는 성공 시 `0`, 실패 시 `1`을 반환하므로 조합해서 쓸 수 있습니다.

## 환경변수

| 변수 | 기본값 | 용도 |
|---|---|---|
| `BEDROCK_REGION` | 스크립트별로 다름 (아래 참고) | 모델 호출 리전 |
| `NOVA_REEL_BUCKET` | `workshop-nova-reel-<계정ID>` | 비디오 출력 S3 버킷 |

**리전 기본값이 스크립트마다 다른 이유**: Nova Canvas와 Nova Reel은
확인 시점 기준 `us-east-1`에만 있고 `us-west-2`에는 없습니다. 리전이
맞지 않으면 `modelId`가 유효하지 않다는 `ValidationException`이 납니다.
그래서 텍스트 계열은 `us-west-2`, 미디어 계열은 `us-east-1`을 기본값으로
두고 `BEDROCK_REGION`으로 덮어쓸 수 있게 했습니다.

## 사전 조건

- Bedrock 모델 접근 권한: Llama 4 Scout, Claude Sonnet 4.6, Nova Canvas, Nova Reel
- `generate_video.py`는 출력 S3 버킷이 **모델 호출 리전과 같은 리전에**
  미리 있어야 합니다. 없으면 작업 제출 단계에서 실패합니다.

## 설계 결정

이 실습은 Kiro CLI(모델: claude-opus-5)와 함께 진행했습니다. 아래 내용은
AI 에이전트가 실행한 도구 결과(에러 메시지, 리전별 모델 카탈로그 조회)를
근거로 정리했으며, 어떤 해결 방향을 택할지는 사람이 검토·승인했습니다.

**리전 원인 규명** — `generate_image.py`·`generate_video.py`가
`us-west-2`에서 아래 오류로 실패했습니다.

```
botocore.errorfactory.ValidationException: An error occurred
(ValidationException) when calling the InvokeModel operation:
The provided model identifier is invalid.
```

모델 액세스 미승인처럼 보이지만 아니었습니다. Kiro가
`bedrock list-foundation-models`로 리전별 카탈로그를 조회한 결과:

| 리전 | Canvas / Reel |
|---|---|
| `us-west-2` | 없음 (nova-pro/lite/micro/premier/sonic — 텍스트·음성만) |
| `us-east-1` | `amazon.nova-canvas-v1:0`, `amazon.nova-reel-v1:0`, `amazon.nova-reel-v1:1` (전부 ON_DEMAND) |

Bedrock은 해당 리전 카탈로그에 없는 `modelId`를 "그 리전에 없다"가 아니라
"식별자가 유효하지 않다"로 응답합니다. 그래서 권한 문제로 오인하기 쉽습니다.

**계정 ID를 코드에 박지 않음** — 버킷 기본 이름에 계정 ID가 필요하지만,
`sts:GetCallerIdentity`로 런타임에 조회합니다. 공개 리포에 계정 ID가
노출되지 않고, 다른 계정에서도 그대로 실행됩니다.

**폴링에 상한을 둠** — 비디오 생성은 분 단위라 폴링이 필요한데,
`while True`로 두면 작업이 `InProgress`에 머무를 때 영구 대기합니다.
`MAX_WAIT_SECONDS = 900`으로 상한을 두고, 초과 시 작업이 계속 진행 중일
수 있다는 안내와 함께 확인용 CLI 명령을 출력합니다.

**파일 저장 경로를 스크립트 기준으로** — `generate_image.py`의 출력은
`Path(__file__).parent`를 기준으로 씁니다. 상대 경로로 두면 리포 루트에서
실행할 때 엉뚱한 위치에 저장됩니다.

## 검증 상태

| 항목 | 상태 |
|---|---|
| `us-west-2`에 Canvas/Reel 부재 | 확인 (`list-foundation-models` 조회) |
| `us-east-1`에 Canvas/Reel 존재 | 확인 (동일 조회) |
| 리전 수정 후 이미지·비디오 실제 생성 | **미검증** |

미검증인 이유: 리전 원인을 특정한 직후 워크숍 계정 자격 증명이 폐기됐습니다.
세션 만료(`ExpiredTokenException`)가 아니라 액세스 키 자체가 무효화된
상태(`UnrecognizedClientException`)여서 재로그인으로도 복구되지 않습니다.
새 워크숍 계정을 받은 뒤 실행 검증을 이어갈 예정입니다.

## 비용 주의사항

상시 과금되는 리소스는 없습니다. 다만 이미지·비디오는 텍스트보다 단가가
높고, Nova Reel은 생성 길이에 비례해 과금되므로 `durationSeconds`를
늘리면 비용도 함께 늘어납니다. 생성된 S3 객체에는 저장 비용이 남습니다.
현재 단가는 [Bedrock 요금 페이지](https://aws.amazon.com/bedrock/pricing/)에서
확인하세요.
