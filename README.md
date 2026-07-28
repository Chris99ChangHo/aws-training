# AWS Training

AWS 오프라인 교육 과정에서 진행한 실습과 정리 노트 모음입니다.

## 과정 목록

| 과정 | 폴더 | 내용 |
|---|---|---|
| Generative AI Essentials on AWS | [`generative-ai-essentials/`](./generative-ai-essentials) | Bedrock Knowledge Base, RAG, 검색 품질 튜닝 |
| Security Engineering on AWS | [`security-engineering/`](./security-engineering) | (진행 예정) |
| Developing Generative AI Applications on AWS | [`developing-genai-apps/`](./developing-genai-apps) | (진행 예정) |
| DevOps Engineering on AWS | [`devops-engineering/`](./devops-engineering) | (진행 예정) |

## 구조

각 과정 폴더 안에는 실습(`*-실습이름/`)과 이론 정리(`notes/`)가 함께 있습니다.

```
aws-training/
├── generative-ai-essentials/
│   ├── README.md
│   ├── notes/                          <- 이론 정리 (선택)
│   └── seoul-travel-planner-kb/        <- 실습
├── security-engineering/
├── developing-genai-apps/
└── devops-engineering/
```

## 참고

- 각 실습 폴더는 독립적으로 실행 가능하도록 자체 `README.md`와
  `requirements.txt`를 포함합니다.
- AWS 계정 자격 증명, 계정 ID, 리소스 ID(KB ID, 버킷명 등)는
  포함되어 있지 않습니다.
