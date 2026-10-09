"""Tests for the intent -> guarded-action translation layer."""

from ck3_strategist.strategist import Intent, Move
from ck3_strategist.translation import (
    GuardedAction,
    Plan,
    aggression_tier,
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


def test_load_table_has_actions():
    table = load_translation_table()
    assert "war" in table["actions"]
    assert table["aggression_tiers"]["count"] == 5


def test_aggression_tier_mapping():
    table = load_translation_table()
    assert aggression_tier(0, table) == "ck3llm_aggressive_1"
    assert aggression_tier(3, table) == "ck3llm_aggressive_2"
    assert aggression_tier(5, table) == "ck3llm_aggressive_3"
    assert aggression_tier(7, table) == "ck3llm_aggressive_4"
    assert aggression_tier(10, table) == "ck3llm_aggressive_5"


def test_aggression_tier_clamps_high_value():
    table = load_translation_table()
    assert aggression_tier(99, table) == "ck3llm_aggressive_5"


def test_ref_to_scope_title_and_character():
    table = load_translation_table()
    assert ref_to_scope("k_england", table) == "title:k_england.holder"
    assert ref_to_scope("char:42", table) == "character:42"


def test_translate_sets_tier_and_years():
    plan = translate(_intent(aggression=8), _summary())
    assert isinstance(plan, Plan)
    assert plan.ruler_scope == "title:k_france.holder"
    assert plan.modifier == "ck3llm_aggressive_4"
    assert plan.modifier_years == 5


def test_translate_war_move_is_guarded():
    plan = translate(
        _intent(aggression=8, moves=[Move("war", "k_england", "claim")]),
        _summary(),
    )
    assert len(plan.actions) == 1
    action = plan.actions[0]
    assert isinstance(action, GuardedAction)
    assert action.effect == "add_pressed_claim"
    assert action.target_scope == "title:k_england"  # the claimed title itself
    assert action.unary is True
    assert action.params == {}
    assert action.guards == ["exists = title:k_england"]


def test_translate_lists_all_tiers_to_clear():
    plan = translate(_intent(), _summary())
    assert plan.clear_modifiers == [
        "ck3llm_aggressive_1",
        "ck3llm_aggressive_2",
        "ck3llm_aggressive_3",
        "ck3llm_aggressive_4",
        "ck3llm_aggressive_5",
    ]


def test_translate_alliance_and_landless_target():
    plan = translate(
        _intent(
            moves=[
                Move("alliance", "char:17313", "spouse"),
                Move("alliance", "k_castile", "friend"),
            ]
        ),
        _summary(),
    )
    assert [a.kind for a in plan.actions] == ["alliance", "alliance"]
    assert plan.actions[0].target_scope == "character:17313"
    assert plan.actions[1].target_scope == "title:k_castile.holder"


def test_translate_drops_unsupported_peace_move():
    # `end_war` is war-scoped; peace is not translatable yet, so it is dropped
    plan = translate(
        _intent(moves=[Move("peace", "k_castile", "war")]), _summary()
    )
    assert plan.actions == []


def test_translate_caps_hard_actions():
    plan = translate(
        _intent(
            moves=[
                Move("war", "k_a", "r"),
                Move("alliance", "k_b", "r"),
                Move("peace", "k_c", "r"),
            ]
        ),
        _summary(),
    )
    assert len(plan.actions) == 2


def test_translate_skips_unknown_kind():
    plan = translate(_intent(moves=[Move("gift", "k_a", "r")]), _summary())
    assert plan.actions == []


def test_translate_plan_id_is_numeric_and_date_sensitive():
    first = translate(_intent(), _summary("k_france"), current_date="1066.1.1")
    again = translate(_intent(), _summary("k_france"), current_date="1066.1.1")
    later = translate(_intent(), _summary("k_france"), current_date="1070.1.1")
    assert isinstance(first.plan_id, int)
    assert first.plan_id == again.plan_id  # deterministic
    assert first.plan_id != later.plan_id  # new cycle -> new plan var
    assert first.plan_date == "1066.1.1"
