"""Tests for the script_docs name validator (review v4 §2)."""

from ck3_strategist.translation import load_translation_table
from ck3_strategist.validate import (
    check,
    check_effects,
    check_tiers,
    guard_trigger_names,
    normalize,
    parse_modifier_log,
    parse_named_log,
)


def test_normalize_dedupes():
    assert normalize({"effects": ["a", "a", "b"]}) == {"effects": {"a", "b"}}


def test_check_effects_reports_missing():
    table = load_translation_table()
    missing = check_effects(table, {"effects": ["add_pressed_claim"]})
    assert missing == {"alliance": "create_alliance"}


def test_check_effects_ok_when_all_present():
    table = load_translation_table()
    dump = {"effects": ["add_pressed_claim", "create_alliance"]}
    assert check_effects(table, dump) == {}


def test_check_tiers_detects_missing_modifiers():
    table = load_translation_table()
    missing = check_tiers(table, {"modifiers": ["ck3llm_aggressive_1"]})
    assert missing == [f"ck3llm_aggressive_{n}" for n in range(2, 6)]


def test_check_aggregates_effects():
    table = load_translation_table()
    report = check(table, {"effects": []})
    assert "effects" in report


def test_guard_trigger_names_extracts_triggers():
    names = guard_trigger_names(load_translation_table())
    assert "exists" in names
    assert "is_allied_to" in names


def test_check_reports_unknown_trigger():
    table = load_translation_table()
    report = check(
        table,
        {
            "effects": ["add_pressed_claim", "create_alliance"],
            "triggers": ["exists"],
        },
    )
    assert report["triggers"] == ["is_allied_to"]


def test_parse_named_log(tmp_path):
    p = tmp_path / "effects.log"
    p.write_text(
        "Effect Documentation:\n\n---\n\nfoo_bar - does a thing\n"
        "Supported Scopes: none\n\n---\n\nbaz - x\n",
        encoding="utf-8",
    )
    assert parse_named_log(p) == {"foo_bar", "baz"}


def test_parse_modifier_log(tmp_path):
    p = tmp_path / "modifiers.log"
    p.write_text(
        "Printing Modifier Definitions:\nTag: ai_boldness\n"
        "Use areas: character\n\nTag: ai_greed\n",
        encoding="utf-8",
    )
    assert parse_modifier_log(p) == {"ai_boldness", "ai_greed"}
