# Structured Output (Pydantic)

응답을 문자열로 받아 파싱하는 대신, Pydantic 모델로 스키마를 지정해
타입이 보장된 객체로 받는다.

```python
from pydantic import BaseModel, Field

# 1. 모델 정의 — Field description이 모델에게 주는 지시가 된다
class MyModel(BaseModel):
    field: str = Field(description="설명")

# 2. structured_output_model로 전달
result = agent("질문", structured_output_model=MyModel)

# 3. .structured_output으로 접근
data = result.structured_output
print(data.field)
```

여러 건을 받을 때는 `List[Restaurant]`를 감싼 모델을 만든다. 최상위를
리스트로 두는 것보다 `class Restaurants(BaseModel): items: list[Restaurant]`
형태가 스키마가 명확하다.
