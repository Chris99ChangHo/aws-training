# UI 작성 규칙

이 리포는 포트폴리오로 쓰인다. 다만 UI 디자인 자체(카드 스타일, 간격,
타이포그래피 체계)는 업계 표준이라 부를 단일 기준이 없다. 여기에는
**출처가 명확한 규칙만** 넣는다.

## 색상 대비 (WCAG 2.1, Level AA — 법적 표준)

> "The visual presentation of text and images of text has a contrast
> ratio of at least 4.5:1", 큰 텍스트(18pt 이상 또는 14pt bold 이상)는
> 3:1 이상.
> 출처: https://www.w3.org/WAI/WCAG21/quickref/ (Success Criterion 1.4.3)

WCAG는 W3C 국제 표준이며 미국 ADA, EU EAA, 한국 웹접근성 지침의 법적
근거로 쓰인다. "권장사항"이 아니라 지켜야 하는 규칙으로 취급한다.

- 본문 텍스트-배경 대비 4.5:1 이상.
- 큰 텍스트(제목 등)는 3:1 이상.
- 다크 모드로 전환할 때 반드시 재확인한다. 대비가 라이트 모드에서만
  맞고 다크에서 깨지는 경우가 많다.

## Streamlit 테마 (공식 문서 기준)

> "You can configure a light and dark theme for your app... specified
> separately for dark and light themes (`[theme.light]`, `[theme.dark]`)."
> "Most theme configuration options can be updated while an app is
> running."
> 출처: https://docs.streamlit.io/develop/concepts/configuration/theming

두 방식 중 상황에 맞게 고른다.

- **표준 위젯 색상만 바꿀 때**: `.streamlit/config.toml`의
  `[theme.light]` / `[theme.dark]`. 사용자가 Streamlit 기본 설정 메뉴로
  전환 가능하고, 커스텀 CSS 없이 위젯 스타일이 자동으로 맞춰진다.
- **카드 등 커스텀 컴포넌트가 필요할 때**: 세션 상태로 현재 테마를
  들고, `st.markdown(..., unsafe_allow_html=True)`로 커스텀 CSS를
  주입한다. 색상은 의미 기반 이름(`bg`, `text`, `accent`)의 딕셔너리
  하나로 모은다.

## 기술 스택 배지 색상 (출처 기반)

색을 임의로 고르지 않는다. 아래 3순위로 결정한다.

**1순위 — simple-icons에 아이콘이 있으면 로고 + 공식 브랜드 hex**

```markdown
![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
```

slug와 hex는 추측하지 않고 조회한다.
출처: https://github.com/simple-icons/simple-icons `slugs.md`(slug),
`data/simple-icons.json`의 `hex`(브랜드 색).

**2순위 — AWS 서비스는 공식 아키텍처 아이콘 카테고리 색**

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

**3순위 — 아이콘도 카테고리도 없으면 로고 없이 그 제품의 공식 브랜드 색**

Cohere, FAISS, Nuclei, SARIF처럼 simple-icons에 없는 대상이 해당한다.
색을 새로 만들지 말고 공식 사이트·리포에서 쓰는 색을 가져온다.

### 검증

`logo=`가 무시돼도 배지는 정상 렌더되므로 눈으로는 구분되지 않는다.
SVG에 `<image>` 요소가 들어갔는지로 판정한다.

```bash
curl -s "https://img.shields.io/badge/T-M-blue?logo=<slug>" | grep -q "<image" \
  && echo "로고 렌더됨" || echo "slug 무시됨"
```

## 검증

UI가 완성됐다고 판단하기 전에 실제로 띄워서 확인한다.

```bash
streamlit run app.py --server.headless true --server.port <포트>
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:<포트>
```

라이트/다크 두 모드를 모두 확인하고, 색상 대비를 실제로 계산한다
(WebAIM Contrast Checker 등). 스크린샷의 계정 ID·리소스 ID 마스킹
기준은 `git-conventions.md`를 따른다.

## 아직 정하지 않은 것

카드 디자인, 간격 체계, 아이콘 사용 규칙, TypeScript/React 기반 UI의
스타일링 표준은 여기 넣지 않는다. 근거 없이 "예쁘다"는 기준으로 규칙을
만들지 않기 위해서다. 해당 프레임워크(Tailwind, shadcn/ui 등)를 실제로
쓰게 되면, 그 공식 문서를 조회해서 근거와 함께 추가한다.
