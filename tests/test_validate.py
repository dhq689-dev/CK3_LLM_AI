"""Tests for the script_docs name validator (CG1)."""

from ck3_strategist.translation import load_translation_table
from ck3_strategist.validate import (
    check,
    check_tiers,
    missing_effects,
    missing_triggers,
    normalize,
    parse_modifier_log,
    parse_named_log,
)


def test_normalize_dedupes():
    assert normalize({"effects": ["a", "a", "b"]}) == {"effects": {"a", "b"}}


def test_missing_effects():
    table = load_translation_table()
    missing = missing_effects(table, {"effects": []})
    assert "add_pressed_claim" in missing
    assert "create_alliance" in missing


def test_missing_effects_ok_when_all_present():
    table = load_translation_table()
    dump = {"effects": table["validated_names"]["effects"]}
    assert missing_effects(table, dump) == []


def test_missing_triggers():
    table = load_translation_table()
    missing = missing_triggers(table, {"triggers": ["exists"]})
    assert "has_claim_on" in missing
    assert "is_allied_to" in missing


def test_check_aggregates_effects_and_triggers():
    table = load_translation_table()
    report = check(table, {"effects": [], "triggers": []})
    assert "effects" in report
    assert "triggers" in report


def test_check_tiers_detects_missing_modifiers():
    table = load_translation_table()
    missing = check_tiers(table, {"modifiers": ["ck3llm_aggressive_1"]})
    assert missing == [f"ck3llm_aggressive_{n}" for n in range(2, 6)]


def test_parse_named_log(tmp_path):
    p = tmp_path / "effects.log"
    p.write_text("Effect Documentation:\n\n---\n\nfoo_bar - x\n", encoding="utf-8")
    assert parse_named_log(p) == {"foo_bar"}


def test_parse_modifier_log(tmp_path):
    p = tmp_path / "modifiers.log"
    p.write_text("Tag: ai_boldness\nTag: ai_greed\n", encoding="utf-8")
    assert parse_modifier_log(p) == {"ai_boldness", "ai_greed"}
