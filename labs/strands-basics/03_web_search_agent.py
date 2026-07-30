"""커스텀 도구 — @tool 데코레이터로 DuckDuckGo 웹검색 도구를 만듭니다."""
from strands import Agent, tool
from strands.models import BedrockModel
from ddgs import DDGS

REGION = "us-west-2"

model = BedrockModel(
    model_id="us.anthropic.claude-sonnet-4-6",
    region_name=REGION,
)

@tool
def web_search(query: str, max_results: int = 5) -> str:
    """DuckDuckGo에서 웹검색을 수행합니다.

    Args:
        query: 검색할 키워드 또는 문장
        max_results: 반환할 최대 결과 수 (기본값: 5)

    Returns:
        검색 결과를 포맷팅한 문자열
    """
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, region="kr-kr", max_results=max_results))

        if not results:
            return "검색 결과가 없습니다."

        formatted = []
        for i, r in enumerate(results, 1):
            formatted.append(
                f"{i}. {r['title']}\n"
                f"   URL: {r['href']}\n"
                f"   {r['body']}\n"
            )
        return "\n".join(formatted)
    except Exception as e:
        return f"검색 중 오류 발생: {str(e)}"

# 웹검색 도구를 에이전트에 연결
agent = Agent(
    model=model,
    system_prompt="""당신은 실시간 웹검색이 가능한 식당 컨시어지 AI입니다.

역할:
- 웹검색으로 최신 식당 정보를 찾아 추천합니다
- 검색 결과를 바탕으로 정확한 정보를 제공합니다

규칙:
- 한국어로 답변합니다
- 반드시 웹검색 결과를 기반으로 답변합니다
- 출처(URL)를 함께 제공합니다""",
    tools=[web_search],
    callback_handler=None,  # 스트리밍 콜백 끄기 — print 결과만 출력
)

response = agent("강남역 근처 새로 오픈한 이탈리안 식당을 알려주세요.")
print(response)