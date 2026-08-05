# `@tool` 데코레이터

함수를 에이전트 도구로 노출한다. docstring과 타입 힌트가 그대로 도구
스펙(설명·파라미터 스키마)이 되므로, 모델이 도구를 언제 어떻게 부를지
판단하는 근거가 된다. 즉 docstring은 주석이 아니라 인터페이스다.

```python
from strands import tool

@tool
def search_restaurants(query: str, location: str, budget: int = 50000) -> str:
    """지역과 조건에 맞는 식당을 검색합니다.

    Args:
        query: 음식 종류 또는 키워드 (예: "이탈리안", "데이트")
        location: 검색 지역 (예: "강남역")
        budget: 1인 예산 원 단위 (기본값: 50000)

    Returns:
        검색된 식당 목록 문자열
    """
    return f"{location} 근처 {query} 식당 3건 발견"
```

- 기본값이 있는 인자는 도구 스펙에서 선택 파라미터가 된다.
- 반환값은 모델이 읽을 문자열이다. 사람이 읽기 좋은 형태로 정리해서
  돌려주는 편이 후속 응답 품질에 유리하다.
