"""Tests for the LLM strategist layer."""

import pytest

from ck3_strategist.strategist import (
    Intent,
    IntentError,
    Strategist,
    build_prompt,
    parse_intent,
)


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
    assert parse_intent(text).aggression == 10


def test_parse_intent_normalises_focus_case():
    text = '{"five_year_goal": "x", "focus": "military", "aggression": 5, "secondary_goal": "y"}'
    assert parse_intent(text).focus == "Military"


def test_parse_intent_rejects_no_json():
    with pytest.raises(IntentError):
        parse_intent("no json here")


def test_parse_intent_rejects_invalid_focus():
    text = '{"five_year_goal": "x", "focus": "Conquest", "aggression": 5, "secondary_goal": "y"}'
    with pytest.raises(IntentError):
        parse_intent(text)


def test_parse_intent_rejects_non_numeric_aggression():
    text = '{"five_year_goal": "x", "focus": "Military", "aggression": "high", "secondary_goal": "y"}'
    with pytest.raises(IntentError):
        parse_intent(text)


def test_parse_intent_accepts_numeric_string_aggression():
    text = '{"five_year_goal": "x", "focus": "Military", "aggression": "7", "secondary_goal": "y"}'
    assert parse_intent(text).aggression == 7


def test_parse_intent_rejects_empty_goal():
    text = '{"five_year_goal": "", "focus": "Military", "aggression": 5, "secondary_goal": "y"}'
    with pytest.raises(IntentError):
        parse_intent(text)


def test_strategist_with_mock_llm():
    def mock_llm(prompt: str) -> str:
        return '{"five_year_goal": "Conquer", "focus": "Military", "aggression": 7, "secondary_goal": "Build army"}'

    strategist = Strategist(mock_llm)
    intent = strategist.plan({"ruler_name": "Test"})
    assert isinstance(intent, Intent)
    assert intent.five_year_goal == "Conquer"
    assert intent.aggression == 7


def test_strategist_retries_on_bad_output():
    responses = iter(
        [
            "not json at all",
            '{"five_year_goal": "x", "focus": "Bogus", "aggression": 5, "secondary_goal": "y"}',
            '{"five_year_goal": "Recovered", "focus": "Intrigue", "aggression": 4, "secondary_goal": "Spy"}',
        ]
    )
    calls = []

    def mock_llm(prompt: str) -> str:
        calls.append(prompt)
        return next(responses)

    strategist = Strategist(mock_llm, max_retries=2)
    intent = strategist.plan({"ruler_name": "Test"})
    assert intent.five_year_goal == "Recovered"
    assert intent.focus == "Intrigue"
    assert len(calls) == 3
    # the retry prompt carries the error feedback
    assert "previous response was invalid" in calls[1]


def test_strategist_gives_up_after_max_retries():
    def mock_llm(prompt: str) -> str:
        return "still not json"

    strategist = Strategist(mock_llm, max_retries=1)
    with pytest.raises(IntentError):
        strategist.plan({"ruler_name": "Test"})
