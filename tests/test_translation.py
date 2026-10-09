"""Tests for the intent -> standing-order translation layer."""

from ck3_strategist.strategist import Intent, Move
from ck3_strategist.translation import (
    Order,
    Plan,
    aggression_tier,
    all_order_vars,
    load_translation_table,
    ref_to_scope,
    translate,
)


def _intent(moves=None, aggression=5):
    return Intent(
        five_year_goal="G",
        focus="Military",
        aggression=aggression,
        aggression_deviation=0,
        secondary_goal="S",
        moves=moves or [],
    )


def _summary(title="k_france"):
    return {"title": title}


def test_load_table_has_orders():
    table = load_translation_table()
    assert "war" in table["orders"]
    assert table["aggression_tiers"]["count"] == 5


def test_aggression_tier_mapping():
    table = load_translation_table()
    assert aggression_tier(0, table) == "ck3llm_aggressive_1"
    assert aggression_tier(3, table) == "ck3llm_aggressive_2"
    assert aggression_tier(5, table) == "ck3llm_aggressive_3"
    assert aggression_tier(7, table) == "ck3llm_aggressive_4"
    assert aggression_tier(10, table) == "ck3llm_aggressive_5"


def test_aggression_tier_clamps_high_value():
    assert aggression_tier(99, load_translation_table()) == "ck3llm_aggressive_5"


def test_ref_to_scope_title_and_character():
    table = load_translation_table()
    assert ref_to_scope("k_england", table) == "title:k_england.holder"
    assert ref_to_scope("char:42", table) == "character:42"
    assert ref_to_scope("k_england", table, "title_self") == "title:k_england"


def test_translate_sets_tier_and_years():
    plan = translate(_intent(aggression=8), _summary())
    assert isinstance(plan, Plan)
    assert plan.ruler_scope == "title:k_france.holder"
    assert plan.modifier == "ck3llm_aggressive_4"
    assert plan.modifier_years == 5


def test_translate_carries_narrative():
    intent = _intent()
    plan = translate(intent, _summary())
    assert plan.goal == intent.five_year_goal
    assert plan.focus == intent.focus
    assert plan.secondary_goal == intent.secondary_goal


def test_translate_war_order_targets_claimed_title():
    plan = translate(_intent([Move("war", "k_england", "claim")]), _summary())
    assert len(plan.orders) == 1
    order = plan.orders[0]
    assert isinstance(order, Order)
    assert order.kind == "war"
    assert order.var_name == "ck3llm_war_target"
    assert order.target_scope == "title:k_england"  # the claimed title itself


def test_translate_alliance_order_targets_holder():
    plan = translate(_intent([Move("alliance", "k_castile", "f")]), _summary())
    assert plan.orders[0].var_name == "ck3llm_ally_target"
    assert plan.orders[0].target_scope == "title:k_castile.holder"


def test_translate_landless_alliance_target():
    plan = translate(_intent([Move("alliance", "char:17313", "s")]), _summary())
    assert plan.orders[0].target_scope == "character:17313"


def test_order_vars_and_tiers_to_clear():
    plan = translate(_intent(), _summary())
    assert plan.clear_orders == ["ck3llm_war_target", "ck3llm_ally_target"]
    assert all_order_vars(load_translation_table()) == [
        "ck3llm_war_target",
        "ck3llm_ally_target",
    ]
    assert plan.clear_modifiers == [
        f"ck3llm_aggressive_{n}" for n in range(1, 6)
    ]


def test_translate_caps_orders():
    plan = translate(
        _intent(
            [
                Move("war", "k_a", "r"),
                Move("alliance", "k_b", "r"),
                Move("alliance", "k_c", "r"),
            ]
        ),
        _summary(),
    )
    assert len(plan.orders) == 2


def test_translate_drops_unknown_and_unsupported():
    assert translate(_intent([Move("gift", "k_a", "r")]), _summary()).orders == []
    peaceful = translate(_intent([Move("peace", "k_a", "r")]), _summary())
    assert peaceful.orders == []
