"""Tests for significant-ruler detection."""

from ck3_strategist.extract import SaveReader
from ck3_strategist.graph import WorldGraph
from ck3_strategist.snapshot import build_snapshots
from ck3_strategist.tiers import TIER_1, TIER_2, TIER_3, classify_rulers, significant_rulers

FIXTURE = "tests/fixtures/small_gamestate.txt"


def _snaps():
    return build_snapshots(WorldGraph.from_save(SaveReader(FIXTURE)))


def test_classify_rulers():
    snaps = _snaps()
    tiers = classify_rulers(snaps)
    by_id = {s.ruler_id: s for s in snaps}
    # 16801936 (king) -> tier 1, 33597185 (emperor) -> tier 1, 47802 (count) -> tier 3
    assert tiers[16801936] == TIER_1
    assert tiers[33597185] == TIER_1
    assert tiers[47802] == TIER_3


def test_significant_rulers():
    snaps = _snaps()
    sig = significant_rulers(snaps)
    ids = {s.ruler_id for s in sig}
    assert ids == {16801936, 33597185}


def test_top_dukes_selection():
    # A duke is Tier 2 only if in the top N by strength.
    snaps = _snaps()
    # no dukes in the fixture, so tier 2 is empty
    tiers = classify_rulers(snaps, top_dukes=10)
    assert TIER_2 not in tiers.values()
