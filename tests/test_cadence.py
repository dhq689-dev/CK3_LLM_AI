"""Tests for cycle cadence and save watching (Milestone 22)."""

from dataclasses import asdict

from ck3_strategist.cadence import (
    PlanStore,
    intent_from_plan,
    is_due,
    new_saves,
    plan_from_dict,
    plan_start_year,
    ruler_ref_of,
    scan_saves,
    watch_saves,
)
from ck3_strategist.strategist import Intent, Move
from ck3_strategist.translation import translate


def _plan(date="1066.1.1"):
    intent = Intent("G", "Military", 5, 0, "S", [Move("war", "k_england", "r")])
    return translate(intent, {"title": "k_france"}, date)


def test_plan_start_year():
    assert plan_start_year({"ck3llm_plan_start": 1066}) == 1066
    assert plan_start_year({}) is None


def test_is_due():
    assert is_due({}, "1066.1.1") is True  # no plan yet
    assert is_due({"ck3llm_plan_start": 1066}, "1066.1.1") is False
    assert is_due({"ck3llm_plan_start": 1066}, "1070.1.1") is False
    assert is_due({"ck3llm_plan_start": 1066}, "1071.1.1") is True
    assert is_due({"ck3llm_plan_start": 1066}, "1071.1.1", interval=10) is False


def test_ruler_ref_of():
    assert ruler_ref_of(_plan()) == "k_france"


def test_intent_from_plan_is_narrative_only():
    intent = intent_from_plan(_plan())
    assert intent.five_year_goal == "G"
    assert intent.moves == []


def test_plan_store_roundtrip(tmp_path):
    store = PlanStore()
    store.put(_plan())
    path = store.save(tmp_path / "plans_store.json")
    got = PlanStore.load(path).get("k_france")
    assert got is not None
    assert got.plan_id == _plan().plan_id
    assert len(got.orders) == 1
    assert got.orders[0].var_name == "ck3llm_war_target"


def test_plan_store_load_missing_is_empty(tmp_path):
    assert PlanStore.load(tmp_path / "nope.json").all() == []


def test_plan_from_dict_reconstructs():
    plan = _plan()
    assert plan_from_dict(asdict(plan)) == plan


def test_scan_and_new_saves(tmp_path):
    a = tmp_path / "a.ck3"
    a.write_text("x", encoding="utf-8")
    before = scan_saves(tmp_path)
    assert str(a) in before
    before[str(a)] -= 1  # pretend the save was modified
    assert new_saves(before, scan_saves(tmp_path)) == [str(a)]
    b = tmp_path / "b.ck3"
    b.write_text("y", encoding="utf-8")
    assert new_saves({}, scan_saves(tmp_path)) == sorted([str(a), str(b)])


def test_watch_saves_reports_no_change(tmp_path):
    (tmp_path / "a.ck3").write_text("x", encoding="utf-8")
    calls: list[list[str]] = []
    watch_saves(tmp_path, calls.append, interval=0, max_polls=1)
    assert calls == []
