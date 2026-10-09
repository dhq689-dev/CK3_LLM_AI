"""Tests for the CK3 script generator and the static mod (Milestone 18)."""

from pathlib import Path

from ck3_strategist.inject import (
    DEFAULT_EFFECT_NAME,
    ORDERS_EFFECT,
    render_plans,
    write_mod_effect,
    write_plans,
)
from ck3_strategist.strategist import Intent, Move
from ck3_strategist.translation import Plan, translate

REPO = Path(__file__).resolve().parent.parent
MOD = REPO / "mod" / "ck3llm_strategist"
BOM = b"\xef\xbb\xbf"


def _intent(moves=None, aggression=8):
    return Intent("G", "Military", aggression, 0, "S", moves or [])


def test_render_plan_is_data_only():
    plan = translate(
        _intent([Move("war", "k_england", "claim")]),
        {"title": "k_france"},
        "1066.1.1",
    )
    text = render_plans([plan])
    assert text.startswith(f"{DEFAULT_EFFECT_NAME} = {{")
    assert "\t" in text  # CK3 uses tabs
    assert "title:k_france.holder ?= {" in text
    assert "set_variable = { name = ck3llm_plan_id value =" in text
    assert "set_variable = { name = ck3llm_plan_start value = 1066 }" in text
    assert "set_variable = { name = ck3llm_war_target value = title:k_england }" in text
    assert f"{ORDERS_EFFECT} = yes" in text
    assert "add_character_modifier = {" in text
    assert "modifier = ck3llm_aggressive_4" in text
    # the generated file carries no action logic or toast
    assert "add_pressed_claim" not in text
    assert "create_alliance" not in text
    assert "send_interface_toast" not in text


def test_render_clears_only_stale_order_var():
    plan = translate(
        _intent([Move("war", "k_england", "claim")]),
        {"title": "k_france"},
        "1066.1.1",
    )
    text = render_plans([plan])
    assert "remove_variable = ck3llm_ally_target" in text
    assert "remove_variable = ck3llm_war_target" not in text


def test_render_clears_previous_tiers_before_adding():
    plan = translate(_intent(), {"title": "k_france"}, "1066.1.1")
    text = render_plans([plan])
    for n in range(1, 6):
        assert f"remove_character_modifier = ck3llm_aggressive_{n}" in text
    assert text.index("remove_character_modifier") < text.index(
        "add_character_modifier"
    )


def test_render_omits_start_year_when_no_date():
    plan = translate(_intent(), {"title": "k_x"})  # no current_date
    assert "ck3llm_plan_start" not in render_plans([plan])


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
    assert "set_variable" not in render_plans([plan])


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


def test_static_orders_effect_exists():
    text = (
        MOD / "common" / "scripted_effects" / "ck3llm_orders.txt"
    ).read_text("utf-8-sig")
    assert f"{ORDERS_EFFECT} = {{" in text
    assert "add_pressed_claim = var:ck3llm_war_target" in text
    assert "create_alliance = var:ck3llm_ally_target" in text
    assert "has_claim_on = var:ck3llm_war_target" in text
