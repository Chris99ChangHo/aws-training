---
name: readme-audit
description: README 작성·점검 표준. 실습·랩·에이전트 README에 담을 항목, shields.io 기술 배지 색상 결정 규칙(simple-icons·AWS 카테고리 색), 상위 README 동기화. "README 검사해줘", "리드미 표준에 맞게 고쳐줘", "배지 추가해줘" 같은 요청에 사용한다.
---

# README 표준·점검·보완

## 원칙

**표준은 이 스킬에 있다.** `repo-structure.md`는 두 축(과정/에이전트)과
디렉토리 배치만 정하고, README 내용 표준은 여기로 모았다. 스티어링은 매 턴
로드되는데 README 표준은 README를 만질 때만 필요하기 때문이다.

**빠진 걸 만들어 채우지 않는다.** 트러블슈팅, 검증 결과, 비용 주의사항 같은
항목은 실제로 있었던 사실을 근거로 써야 한다. 근거가 없으면 "확인 필요"로
남기고 사용자에게 물어본다. 그럴듯한 문장을 지어내는 것은 포트폴리오
신뢰도를 해친다.

## 점검 대상

리포는 두 축이고 계층 깊이가 축마다 다르다.

| 대상 | 경로 | 확인할 것 |
|---|---|---|
| 최상위 | `README.md` | 두 축 표 + 과정 목록이 실제 폴더와 일치 |
| 과정 | `<과정명>/README.md` | 실습 목록 표가 실제 `<실습명>/` 폴더와 일치 |
| 실습 | `<과정명>/<실습명>/README.md` | 아래 6항목 체크리스트 전체 |
| 랩 | `labs/README.md`, `labs/<랩명>/README.md` | 실습과 같은 6항목. 과정에 속하지 않는 기능 단위 |
| 에이전트 계열 | `agents/README.md` | 에이전트 목록·공통 문서 표가 실제와 일치 |
| 개별 에이전트 | `agents/<도메인>/README.md` | 6항목 + 자기 트러블슈팅. 수치는 실측과 대조 (`agent-release-check` 스킬 5절) |

## 실습·랩·에이전트 README에 담을 6항목

단순 실행법만 적지 않는다. 이 리포는 학습 기록이자 포트폴리오이므로
**판단 근거가 결과보다 중요하다.**

| 항목 | 내용 | 확인할 것 |
|---|---|---|
| 1. 기술 배지 | shields.io 정적 배지. 제목 바로 아래, 첫 문단 위 | 실제 `requirements.txt`·코드에서 쓴 기술과 일치하는가 (안 쓰는 배지가 남았거나 쓴 기술이 빠지지 않았는가) |
| 2. 아키텍처 | 텍스트 다이어그램으로 충분 | 코드의 실제 흐름과 맞는가 |
| 3. 설계 결정과 트러블슈팅 | 겪은 문제, 원인 분석 과정, 해결 방법 | "됐다/안 됐다"가 아니라 왜 그 결과가 나왔는지 근거가 있는가. 없으면 커밋 히스토리·코드 주석에서 찾고, 없으면 사용자에게 묻는다 |
| 4. 실행 방법 | 명령어와 전제 | 실제로 실행해서 문서대로 동작하는지 확인 (가능한 경우) |
| 5. 검증 결과 | 수치·비교표 | "됐음"으로만 끝나지 않는가 |
| 6. 비용 주의사항 | 상시 과금 리소스 명시 | KB·컴퓨트 등이 있는데 언급이 없는가 |

3항목의 AI 협업 표기는 `ai-attribution.md`를 따른다.

## 기술 스택 배지

색을 임의로 고르지 않는다. 아래 3순위로 결정한다.
[정적 배지 문법](https://shields.io/badges/static-badge)은 `라벨-메시지-색상`이다.

### 1순위 — simple-icons에 아이콘이 있으면 로고 + 공식 브랜드 hex

```markdown
![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
```

slug와 hex는 추측하지 않고 조회한다. 추측한 slug는 조용히 무시된다.
출처: https://github.com/simple-icons/simple-icons `slugs.md`(slug),
`data/simple-icons.json`의 `hex`(브랜드 색). 검색용 사이트:
https://simpleicons.org/

### 2순위 — AWS 서비스는 공식 아키텍처 아이콘 카테고리 색

**simple-icons에 Amazon·AWS 아이콘은 없다**(`slugs.md` 실측: `amazon`·`aws`
매칭 0건). `logo=amazonaws`처럼 쓰면 shields.io가 **조용히 무시**하므로,
로고 없이 색만 남는다. 그래서 AWS 서비스는 로고를 붙이지 않고 카테고리 색을
쓴다.

출처: https://github.com/awslabs/aws-icons-for-plantuml `AWSSymbols.md`
(`AWSCommon.puml`에 정의된 색이며 AWS 공식 아키텍처 아이콘 세트에서 나온다)

| 색 | hex | 카테고리 |
|---|---|---|
| Smile | `ED7100` | Compute, Containers, Media Services, Blockchain, Quantum |
| Endor | `7AA116` | Storage, IoT, Cloud Financial Management |
| Nebula | `C925D1` | Database, Developer Tools, Customer Enablement, Satellite |
| Cosmos | `E7157B` | Application Integration, Management & Governance, Multicloud & Hybrid |
| Galaxy | `8C4FFF` | Analytics, Networking & Content Delivery, Serverless, Games |
| Mars | `DD344C` | Security Identity & Compliance, Business Applications, Front-End Web & Mobile |
| Orbit | `01A88D` | Artificial Intelligence, End User Computing, Migration & Modernization |
| Squid | `232F3E` | General (AWS 브랜드 다크) |

서비스가 어느 카테고리인지도 같은 문서에서 확인한다. 실측 예:
Bedrock → Artificial Intelligence(`01A88D`), Lambda → Compute(`ED7100`),
S3 → Storage(`7AA116`), OpenSearch Service → Analytics(`8C4FFF`).

```markdown
![AWS](https://img.shields.io/badge/AWS-Bedrock-01A88D)
```

### 3순위 — 아이콘도 카테고리도 없으면 로고 없이 그 제품의 공식 브랜드 색

Cohere, FAISS, Nuclei, SARIF처럼 simple-icons에 없는 대상이 해당한다.
색을 새로 만들지 말고 공식 사이트·리포에서 쓰는 색을 가져온다.

```markdown
![Strands Agents](https://img.shields.io/badge/Strands_Agents-1.x-4B32C3)
```

### 배지 검증

`logo=`가 무시돼도 배지는 정상 렌더되므로 눈으로는 구분되지 않는다.
SVG에 `<image>` 요소가 들어갔는지로 판정한다.

```bash
curl -s "https://img.shields.io/badge/T-M-blue?logo=<slug>" | grep -q "<image" \
  && echo "로고 렌더됨" || echo "slug 무시됨"
```

버전 표기(`Python-3.12`)는 실제 `requirements.txt`나 실행 환경의 버전과
맞춘다. 임의로 넣지 않는다.

## 절차

1. **스캔** — 대상 폴더의 README와 실제 코드/구조를 함께 읽는다. README만
   보고 판단하지 않는다 (예: "아키텍처"가 실제 코드 구조와 다르게 서술되어
   있을 수 있다).
2. **격차 보고** — 항목별로 아래 형식으로 보고한다. 사용자 승인 전에 파일을
   먼저 고치지 않는다.
   ```
   ## <폴더명>

   - [빠짐] <항목> — <무엇이 없는지>
   - [불일치] <항목> — <문서와 실제가 다른 지점>
   - [근거 필요] <항목> — <채우려면 사용자에게 물어야 하는 것>
   ```
3. **보완** — 사용자가 승인한 항목만 수정한다. 기술 배지처럼 코드에서
   기계적으로 확인 가능한 항목은 바로 고쳐도 되지만, 트러블슈팅·설계
   결정처럼 서술이 필요한 항목은 사용자가 준 사실을 그대로 반영한다.
4. **상위 README 동기화** — 폴더를 새로 추가하거나 이름을 바꿨다면 상위
   README의 표도 함께 갱신한다.

## 과정을 추가할 때

1. 과정 폴더와 `notes/` 생성
2. 과정 `README.md` 작성 (실습 목록 표)
3. 최상위 `README.md`의 과정 목록 표에 한 줄 추가
