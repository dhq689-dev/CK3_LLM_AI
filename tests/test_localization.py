"""Tests for plan localization (Milestone 21)."""

from ck3_strategist.localization import (
    LOC_FILE,
    TITLE_KEY,
    loc_key,
    plan_text,
    render_localization,
    write_localization,
    write_mod_localization,
)
from ck3_strategist.translation import Plan

BOM = b"\xef\xbb\xbf"
NL = chr(92) + "n"  # literal backslash-n, which CK3 reads as a line break


def _plan(plan_id=42, **overrides):
    data = {
        "ruler_scope": "title:k_france.holder",
        "plan_id": plan_id,
        "aggression": 5,
        "modifier": "ck3llm_aggressive_3",
        "modifier_years": 5,
        "goal": "Unify Britannia",
        "focus": "Military",
        "secondary_goal": "Secure succession",
    }
    data.update(overrides)
    return Plan(**data)


def test_loc_key():
    assert loc_key(42) == "ck3llm_plan_42"


def test_plan_text_escapes_quotes():
    assert plan_text(_plan(goal='Say "hi"', focus="", secondary_goal="")) == (
        "Goal: Say 'hi'"
    )


def test_plan_text_joins_lines():
    assert plan_text(_plan()) == (
        f"Goal: Unify Britannia{NL}Focus: Military{NL}Then: Secure succession"
    )


def test_render_localization_has_title_and_plan():
    text = render_localization([_plan(42)])
    assert text.startswith("l_english:")
    assert f"{TITLE_KEY}:0" in text
    assert 'ck3llm_plan_42:0 "Goal: Unify Britannia' in text


def test_write_localization_is_utf8_bom(tmp_path):
    path = tmp_path / "loc" / LOC_FILE
    write_localization(path, [_plan()])
    data = path.read_bytes()
    assert data.startswith(BOM)
    assert data.decode("utf-8-sig").startswith("l_english:")


def test_write_mod_localization_layout(tmp_path):
    path = write_mod_localization([_plan()], tmp_path)
    assert path == tmp_path / "localization" / "english" / LOC_FILE
    assert path.exists()


def test_render_skips_plans_without_narrative():
    text = render_localization(
        [_plan(goal="", focus="", secondary_goal="", plan_id=7)]
    )
    assert "ck3llm_plan_7" not in text
