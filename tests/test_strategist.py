"""Tests for the LLM strategist layer."""

from ck3_strategist.strategist import Intent, Strategist, build_prompt, parse_intent


def test_build_prompt_contains_summary_fields():
    summary = {
        "ruler_name": "King Edward",
        "title": "k_england",
        "rank": "king",
        "age": 43,
        "traits": ["ambitious", "wrathful"],
        "skills": {"diplomacy": 6, "martial": 8},
        "realm_size": "large",
        "military_strength": "strong",
        "economic_strength": "average",
        "succession_stability": "stable",
        "active_wars": 1,
        "major_threats": [{"ruler": "Scotland", "power_ratio": 1.4}],
        "major_opportunities": ["Claim on Wales"],
    }
    prompt = build_prompt(summary)
    assert "King Edward" in prompt
    assert "ambitious, wrathful" in prompt
    assert "Scotland" in prompt
    assert "five_year_goal" in prompt


def test_parse_intent_plain_json():
    text = '{"five_year_goal": "Unify Britannia", "focus": "Military", "aggression": 8, "secondary_goal": "Secure succession"}'
    intent = parse_intent(text)
    assert intent.five_year_goal == "Unify Britannia"
    assert intent.focus == "Military"
    assert intent.aggression == 8
    assert intent.secondary_goal == "Secure succession"


def test_parse_intent_with_markdown_fence():
    text = '```json\n{"five_year_goal": "Expand", "focus": "Diplomacy", "aggression": 3, "secondary_goal": "Marry well"}\n```'
    intent = parse_intent(text)
    assert intent.five_year_goal == "Expand"
    assert intent.focus == "Diplomacy"
    assert intent.aggression == 3


def test_parse_intent_clamps_aggression():
    text = '{"five_year_goal": "x", "focus": "Military", "aggression": 99, "secondary_goal": "y"}'
    intent = parse_intent(text)
    assert intent.aggression == 10


def test_parse_intent_rejects_no_json():
    try:
        parse_intent("no json here")
        assert False, "should have raised"
    except ValueError:
        pass


def test_strategist_with_mock_llm():
    def mock_llm(prompt: str) -> str:
        return '{"five_year_goal": "Conquer", "focus": "Military", "aggression": 7, "secondary_goal": "Build army"}'

    strategist = Strategist(mock_llm)
    intent = strategist.plan({"ruler_name": "Test"})
    assert isinstance(intent, Intent)
    assert intent.five_year_goal == "Conquer"
    assert intent.aggression == 7
