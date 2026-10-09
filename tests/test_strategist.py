"""Tests for the LLM strategist layer."""

import json

import pytest

from ck3_strategist.strategist import (
    Intent,
    IntentError,
    Move,
    Strategist,
    build_prompt,
    parse_intent,
)


def _summary(**overrides):
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
        "aggression_baseline": 8,
        "active_wars": 1,
        "major_threats": [{"ruler": "Scotland", "power_ratio": 1.4}],
        "major_opportunities": ["Claim on Wales"],
        "moves": {
            "war_targets": [{"ref": "k_wales", "holder": "Wales"}],
            "alliance_candidates": [
                {"ref": "k_france", "ruler": "France", "reason": "friend"}
            ],
            "peace_options": [],
        },
    }
    summary.update(overrides)
    return summary


def _intent_json(**overrides):
    data = {
        "five_year_goal": "Unify Britannia",
        "focus": "Military",
        "secondary_goal": "Secure succession",
        "aggression_deviation": 3,
    }
    data.update(overrides)
    return json.dumps(data)


_MENU = {
    "war": {"k_wales"},
    "alliance": {"k_france"},
    "peace": {"d_warring"},
}


# --- prompt rendering -------------------------------------------------------


def test_build_prompt_contains_summary_fields():
    prompt = build_prompt(_summary())
    assert "King Edward" in prompt
    assert "ambitious, wrathful" in prompt
    assert "Scotland" in prompt
    assert "five_year_goal" in prompt


def test_build_prompt_includes_baseline_and_menu():
    prompt = build_prompt(_summary())
    assert "Aggression baseline" in prompt
    assert "8" in prompt
    assert "k_wales" in prompt
    assert "k_france" in prompt
    assert "aggression_deviation" in prompt


def test_build_prompt_handles_missing_menu():
    prompt = build_prompt(_summary(moves={}))
    assert "War targets: none" in prompt


def test_build_prompt_includes_previous_plan():
    prompt = build_prompt(
        _summary(previous_plan={"plan_id": 42, "since": 918})
    )
    assert "Previous plan: id=42 since year 918" in prompt


def test_build_prompt_previous_plan_none():
    assert "Previous plan: none" in build_prompt(_summary())


# --- parsing ----------------------------------------------------------------


def test_parse_intent_plain_json():
    intent = parse_intent(_intent_json(), baseline=5)
    assert intent.five_year_goal == "Unify Britannia"
    assert intent.focus == "Military"
    assert intent.aggression_deviation == 3
    assert intent.aggression == 8
    assert intent.secondary_goal == "Secure succession"


def test_parse_intent_with_markdown_fence():
    text = "```json\n" + _intent_json(
        focus="Diplomacy", aggression_deviation=-2
    ) + "\n```"
    intent = parse_intent(text, baseline=5)
    assert intent.focus == "Diplomacy"
    assert intent.aggression == 3


def test_parse_intent_clamps_effective_aggression():
    intent = parse_intent(_intent_json(aggression_deviation=99), baseline=9)
    assert intent.aggression_deviation == 3
    assert intent.aggression == 10


def test_parse_intent_clamps_negative_effective_aggression():
    intent = parse_intent(_intent_json(aggression_deviation=-99), baseline=2)
    assert intent.aggression_deviation == -3
    assert intent.aggression == 0


def test_parse_intent_uses_default_baseline():
    intent = parse_intent(_intent_json(aggression_deviation=0))
    assert intent.aggression == 5


def test_parse_intent_normalises_focus_case():
    intent = parse_intent(_intent_json(focus="military"), baseline=5)
    assert intent.focus == "Military"


def test_parse_intent_rejects_no_json():
    with pytest.raises(IntentError):
        parse_intent("no json here")


def test_parse_intent_rejects_invalid_focus():
    with pytest.raises(IntentError):
        parse_intent(_intent_json(focus="Conquest"))


def test_parse_intent_rejects_non_numeric_deviation():
    with pytest.raises(IntentError):
        parse_intent(_intent_json(aggression_deviation="high"))


def test_parse_intent_accepts_numeric_string_deviation():
    intent = parse_intent(_intent_json(aggression_deviation="2"), baseline=5)
    assert intent.aggression_deviation == 2


def test_parse_intent_rejects_empty_goal():
    with pytest.raises(IntentError):
        parse_intent(_intent_json(five_year_goal=""))


# --- constrained moves ------------------------------------------------------


def test_parse_intent_with_moves():
    text = _intent_json(
        moves=[
            {"kind": "war", "ref": "k_wales", "reason": "claim"},
            {"kind": "alliance", "ref": "k_france", "reason": "friend"},
        ]
    )
    intent = parse_intent(text, baseline=5, valid_refs=_MENU)
    assert [(m.kind, m.ref) for m in intent.moves] == [
        ("war", "k_wales"),
        ("alliance", "k_france"),
    ]
    assert isinstance(intent.moves[0], Move)
    assert intent.moves[0].reason == "claim"


def test_parse_intent_drops_moves_not_in_menu():
    text = _intent_json(
        moves=[
            {"kind": "war", "ref": "k_ghost"},
            {"kind": "war", "ref": "k_wales"},
        ]
    )
    intent = parse_intent(text, baseline=5, valid_refs=_MENU)
    assert [m.ref for m in intent.moves] == ["k_wales"]


def test_parse_intent_drops_kind_ref_mismatch():
    text = _intent_json(moves=[{"kind": "war", "ref": "k_france"}])
    intent = parse_intent(text, baseline=5, valid_refs=_MENU)
    assert intent.moves == []


def test_parse_intent_drops_unknown_kind_and_duplicates():
    text = _intent_json(
        moves=[
            {"kind": "marriage", "ref": "k_france"},
            {"kind": "alliance", "ref": "k_france"},
            {"kind": "alliance", "ref": "k_france"},
        ]
    )
    intent = parse_intent(text, baseline=5, valid_refs=_MENU)
    assert len(intent.moves) == 1


def test_parse_intent_accepts_moves_without_menu():
    text = _intent_json(moves=[{"kind": "war", "ref": "whatever"}])
    intent = parse_intent(text, baseline=5)
    assert [m.ref for m in intent.moves] == ["whatever"]


# --- strategist -------------------------------------------------------------


def test_strategist_with_mock_llm():
    def mock_llm(prompt: str) -> str:
        return _intent_json(
            five_year_goal="Conquer",
            secondary_goal="Build army",
            aggression_deviation=1,
        )

    strategist = Strategist(mock_llm)
    intent = strategist.plan(_summary())
    assert isinstance(intent, Intent)
    assert intent.five_year_goal == "Conquer"
    assert intent.aggression == 9


def test_strategist_retries_on_bad_output():
    responses = iter(
        [
            "not json at all",
            _intent_json(focus="Bogus"),
            _intent_json(five_year_goal="Recovered", focus="Intrigue"),
        ]
    )
    calls = []

    def mock_llm(prompt: str) -> str:
        calls.append(prompt)
        return next(responses)

    strategist = Strategist(mock_llm, max_retries=2)
    intent = strategist.plan(_summary())
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
        strategist.plan(_summary())


def test_strategist_constrains_moves_to_menu():
    def mock_llm(prompt: str) -> str:
        return _intent_json(
            moves=[
                {"kind": "war", "ref": "k_wales", "reason": "claim"},
                {"kind": "war", "ref": "k_ghost", "reason": "hallucinated"},
            ]
        )

    intent = Strategist(mock_llm).plan(_summary())
    assert [m.ref for m in intent.moves] == ["k_wales"]


def test_strategist_uses_baseline_for_aggression():
    def mock_llm(prompt: str) -> str:
        return _intent_json(aggression_deviation=-2)

    intent = Strategist(mock_llm).plan(_summary(aggression_baseline=6))
    assert intent.aggression == 4
