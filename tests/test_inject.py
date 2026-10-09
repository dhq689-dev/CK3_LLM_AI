"""Tests for the CK3 script generator and the static mod (Milestone 18)."""

from pathlib import Path

from ck3_strategist.inject import (
    DEFAULT_EFFECT_NAME,
    render_plans,
    write_mod_effect,
    write_plans,
)
from ck3_strategist.strategist import Intent, Move
from ck3_strategist.translation import GuardedAction, Plan, translate

REPO = Path(__file__).resolve().parent.parent
MOD = REPO / "mod" / "ck3llm_strategist"
BOM = b"\xef\xbb\xbf"


def _intent(moves=None, aggression=8):
    return Intent(
        five_year_goal="G",
        focus="Military",
        aggression=aggression,
        aggression_deviation=0,
        secondary_goal="S",
        moves=moves or [],
    )


# --- rendering --------------------------------------------------------------


def test_render_plan_contains_scope_modifier_and_guard():
    plan = translate(
        _intent(moves=[Move("war", "k_england", "claim")]),
        {"title": "k_france"},
        "1066.1.1",
    )
    text = render_plans([plan])
    assert text.startswith(f"{DEFAULT_EFFECT_NAME} = {{")
    assert "\t" in text  # CK3 uses tabs
    assert "title:k_france.holder ?= {" in text
    assert "set_variable = { name = ck3llm_plan_id value =" in text
    assert "set_variable = { name = ck3llm_plan_start value = 1066 }" in text
    assert "add_character_modifier = {" in text
    assert "modifier = ck3llm_aggressive_4" in text
    assert "years = 5" in text
    assert "add_pressed_claim = title:k_england" in text
    assert "exists = title:k_england" in text
    assert "send_interface_toast" not in text  # plans steer AI rulers only


def test_render_omits_start_year_when_no_date():
    plan = translate(_intent(), {"title": "k_x"})  # no current_date
    assert "ck3llm_plan_start" not in render_plans([plan])


def test_render_clears_previous_tiers_before_adding():
    plan = translate(_intent(), {"title": "k_france"}, "1066.1.1")
    text = render_plans([plan])
    for n in range(1, 6):
        line = f"remove_character_modifier = ck3llm_aggressive_{n}"
        assert line in text
    assert "remove_character_modifier = {" not in text  # unary, not a block
    # all removals come before the new tier is added
    assert text.index("remove_character_modifier") < text.index(
        "add_character_modifier"
    )


def test_render_omits_debug_log_when_asked():
    plan = translate(_intent(), {"title": "k_x"}, "d")
    assert "debug_log" in render_plans([plan])
    assert "debug_log" not in render_plans([plan], debug=False)


def test_render_skips_plan_without_scope():
    plan = Plan(
        ruler_scope="",
        plan_id=1,
        aggression=5,
        modifier="ck3llm_aggressive_3",
        modifier_years=5,
    )
    text = render_plans([plan])
    assert "set_variable" not in text


def test_render_action_without_guards_is_boolean():
    action = GuardedAction(
        kind="war",
        effect="do_thing",
        target_ref="k_a",
        target_scope="title:k_a.holder",
    )
    plan = Plan(
        ruler_scope="title:k_r.holder",
        plan_id=2,
        aggression=5,
        modifier="m",
        modifier_years=5,
        actions=[action],
    )
    assert "do_thing = yes" in render_plans([plan])


# --- writing ----------------------------------------------------------------


def test_write_plans_writes_utf8_bom(tmp_path):
    plan = translate(_intent(), {"title": "k_france"}, "1066.1.1")
    path = tmp_path / "nested" / "ck3llm_plans.txt"
    write_plans(path, [plan])
    data = path.read_bytes()
    assert data.startswith(BOM)
    assert data.decode("utf-8-sig").endswith("\n")


def test_write_mod_effect_uses_mod_layout(tmp_path):
    plan = translate(_intent(), {"title": "k_france"}, "1066.1.1")
    path = write_mod_effect([plan], tmp_path)
    assert path == tmp_path / "common" / "scripted_effects" / "ck3llm_plans.txt"
    assert path.exists()


# --- static mod -------------------------------------------------------------


def test_static_mod_descriptors_present():
    assert (REPO / "mod" / "ck3llm_strategist.mod").is_file()
    assert (MOD / "descriptor.mod").is_file()


def test_static_script_files_have_single_bom():
    for path in (MOD / "common").rglob("*.txt"):
        data = path.read_bytes()
        assert data.startswith(BOM), path
        assert not data[len(BOM) :].startswith(BOM), f"double BOM: {path}"


def test_static_localization_has_single_bom():
    path = MOD / "localization" / "english" / "ck3llm_l_english.yml"
    data = path.read_bytes()
    assert data.startswith(BOM)
    assert not data[len(BOM) :].startswith(BOM)


def test_static_modifiers_define_all_tiers():
    text = (MOD / "common" / "modifiers" / "ck3llm_modifiers.txt").read_text(
        "utf-8-sig"
    )
    for n in range(1, 6):
        assert f"ck3llm_aggressive_{n} = {{" in text


def test_on_action_calls_generated_effect():
    text = (MOD / "common" / "on_action" / "ck3llm_on_actions.txt").read_text(
        "utf-8-sig"
    )
    assert "yearly_global_pulse = {" in text
    assert "on_actions = { ck3llm_yearly_pulse }" in text
    assert f"{DEFAULT_EFFECT_NAME} = yes" in text
