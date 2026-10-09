"""Tests for the script_docs name validator (review v4 §2)."""

from ck3_strategist.translation import load_translation_table
from ck3_strategist.validate import check, check_effects, check_tiers, normalize


def test_normalize_dedupes():
    assert normalize({"effects": ["a", "a", "b"]}) == {"effects": {"a", "b"}}


def test_check_effects_reports_missing():
    table = load_translation_table()
    missing = check_effects(table, {"effects": ["start_war"]})
    assert missing == {"alliance": "create_alliance", "peace": "end_war"}


def test_check_effects_ok_when_all_present():
    table = load_translation_table()
    dump = {"effects": ["start_war", "create_alliance", "end_war"]}
    assert check_effects(table, dump) == {}


def test_check_tiers_detects_missing_modifiers():
    table = load_translation_table()
    missing = check_tiers(table, {"modifiers": ["ck3llm_aggressive_1"]})
    assert missing == [f"ck3llm_aggressive_{n}" for n in range(2, 6)]


def test_check_aggregates_effects():
    table = load_translation_table()
    report = check(table, {"effects": []})
    assert "effects" in report
