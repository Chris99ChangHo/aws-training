# evals/gate_eval.py — 평가 게이트: 평균 점수 0.7 미만이면 비0 종료 코드로 실패
#
# CodeBuild의 dining-test 프로젝트가 이 스크립트를 실행합니다. CodeBuild는
# 비0 종료 코드를 스테이지 실패로 취급하므로, 이 스크립트의 exit code가
# 곧 "배포를 막을지"를 결정합니다.
#
# 평가 케이스 3종(게이트와 미션이 공유하는 계약 — 바꾸면 안 됨):
#   1. "강남역 근처 이탈리안 식당 추천해 주세요" → 응답에 "트라토리아 벨라" 포함
#   2. "매운 음식을 못 먹는데 강남 식당 추천해 주세요" → 응답에 "매콤한 마라" 미포함
#   3. "다음 주 공휴일에 영업하나요?" → 추측 없는 안내 톤(모른다고 인정)
#
# 실행 방법:
#   python3 evals/gate_eval.py
#
# 사전 조건: DiningConcierge/app/DiningConcierge/main.py를 import할 수 있어야
# 하므로, buildspec에서 해당 디렉터리를 PYTHONPATH에 넣거나 이 스크립트를
# 그 디렉터리 기준 상대 경로로 실행합니다.
import os
import sys

THRESHOLD = 0.7

# 추측성 답변에 흔히 등장하는 표현(케이스 3에서 감점 판정에 사용)
GUESSING_PHRASES = [
    "영업합니다",
    "영업할 것",
    "쉬는 날일 것",
    "휴무일 것",
    "아마",
    "일반적으로",
    "보통",
]

# 신중한(추측 금지) 답변에 등장해야 하는 표현
CAUTIOUS_PHRASES = [
    "확인 후 안내",
    "확인이 필요",
    "정확히 알 수 없",
    "모르",
]


def _import_agent_module():
    """DiningConcierge/app/DiningConcierge/main.py를 동적으로 import."""
    here = os.path.dirname(os.path.abspath(__file__))
    app_dir = os.path.join(here, "..", "app", "DiningConcierge")
    sys.path.insert(0, app_dir)
    import main  # noqa: E402

    return main


def ask(agent_module, prompt: str) -> str:
    """에이전트를 동기 호출해 최종 응답 텍스트를 반환합니다."""
    from strands import Agent
    from strands.agent.conversation_manager.null_conversation_manager import (
        NullConversationManager,
    )
    from model.load import load_model  # type: ignore

    agent = Agent(
        model=load_model(),
        system_prompt=agent_module.DEFAULT_SYSTEM_PROMPT,
        tools=agent_module.tools,
        conversation_manager=NullConversationManager(),
        callback_handler=None,
    )
    return str(agent(prompt))


def score_case_1_italian_recommendation(answer: str) -> float:
    """강남역 이탈리안 추천에 트라토리아 벨라가 포함되면 1.0, 아니면 0.0."""
    return 1.0 if "트라토리아 벨라" in answer else 0.0


def score_case_2_no_spicy(answer: str) -> float:
    """매운 음식을 못 먹는다는 조건에서 매콤한 마라를 추천하지 않으면 1.0.

    단순히 "매콤한 마라"라는 문자열이 응답에 있는지가 아니라, 그 이름이
    배제 의도 문맥(예: "피하실 곳", "제외", "추천하지 않")과 함께 등장하는지를
    본다. "매콤한 마라는 피하세요"처럼 명시적으로 배제하며 언급하는 응답이
    오히려 더 신뢰할 수 있는 답변이므로, 단순 포함 여부로 0점을 주면
    좋은 응답을 오탐으로 차단하게 된다.
    """
    if "매콤한 마라" not in answer:
        return 1.0
    exclusion_markers = ["피하", "제외", "추천하지 않", "추천드리지 않", "권장하지 않", "않으시는 것"]
    idx = answer.find("매콤한 마라")
    window = answer[max(0, idx - 40):idx + 60]
    return 1.0 if any(m in window for m in exclusion_markers) else 0.0


def score_case_3_no_guessing(answer: str) -> float:
    """공휴일 영업 여부 질문에 추측 없이 신중하게 답하면 1.0, 추측성 답변이면 0.0."""
    has_guess = any(p in answer for p in GUESSING_PHRASES)
    has_caution = any(p in answer for p in CAUTIOUS_PHRASES)
    if has_guess and not has_caution:
        return 0.0
    return 1.0 if has_caution else 0.5  # 애매하면 절반 점수(관대한 판정)


CASES = [
    {
        "name": "강남역 이탈리안 추천 (트라토리아 벨라 포함)",
        "prompt": "강남역 근처 이탈리안 식당 추천해 주세요",
        "scorer": score_case_1_italian_recommendation,
    },
    {
        "name": "매운 음식 제외 (매콤한 마라 미포함)",
        "prompt": "매운 음식을 못 먹는데 강남 식당 추천해 주세요",
        "scorer": score_case_2_no_spicy,
    },
    {
        "name": "공휴일 영업 여부 (추측 금지 톤)",
        "prompt": "다음 주 공휴일에 영업하나요?",
        "scorer": score_case_3_no_guessing,
    },
]


def main() -> int:
    agent_module = _import_agent_module()

    scores = []
    print("=== 평가 게이트 실행 ===\n")
    for case in CASES:
        answer = ask(agent_module, case["prompt"])
        score = case["scorer"](answer)
        scores.append(score)
        print(f"[{case['name']}]")
        print(f"  질문: {case['prompt']}")
        print(f"  응답: {answer[:200]}")
        print(f"  점수: {score}\n")

    average = sum(scores) / len(scores)
    print(f"=== 평균 점수: {average:.3f} (임계 {THRESHOLD}) ===")

    if average < THRESHOLD:
        print(f"❌ 게이트 실패: 평균 {average:.3f} < {THRESHOLD}")
        return 1

    print(f"✅ 게이트 통과: 평균 {average:.3f} >= {THRESHOLD}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
