"""Tests for the trait-derived aggression baseline."""

from ck3_strategist.aggression import baseline_aggression, load_aggression_map


def test_baseline_default_with_no_traits():
    mapping = {"base": 5, "deltas": {}}
    assert baseline_aggression([], mapping) == 5


def test_baseline_applies_deltas():
    mapping = {"base": 5, "deltas": {"wrathful": 2, "ambitious": 1, "content": -2}}
    assert baseline_aggression(["wrathful", "ambitious"], mapping) == 8
    assert baseline_aggression(["content"], mapping) == 3


def test_baseline_clamps_to_range():
    mapping = {"base": 5, "deltas": {"wrathful": 2}}
    assert baseline_aggression(["wrathful"] * 10, mapping) == 10
    mapping_low = {"base": 5, "deltas": {"content": -2}}
    assert baseline_aggression(["content"] * 10, mapping_low) == 0


def test_unknown_traits_are_ignored():
    mapping = {"base": 5, "deltas": {"wrathful": 2}}
    assert baseline_aggression(["modded_trait_999"], mapping) == 5


def test_real_mapping_loads_and_scores():
    mapping = load_aggression_map()
    assert baseline_aggression(["wrathful", "ambitious"], mapping) == 8
    assert baseline_aggression(["content", "calm"], mapping) == 2
