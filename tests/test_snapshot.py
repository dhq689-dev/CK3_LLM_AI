"""Tests for the RealmSnapshot layer."""

from ck3_strategist.extract import SaveReader
from ck3_strategist.graph import WorldGraph
from ck3_strategist.snapshot import (
    bucket_strength,
    build_snapshot,
    build_snapshots,
    compute_threats,
)

FIXTURE = "tests/fixtures/small_gamestate.txt"


def _graph():
    return WorldGraph.from_save(SaveReader(FIXTURE))


def test_build_snapshot():
    g = _graph()
    snap = build_snapshot(g, 16801936)
    assert snap.ruler_name == "Blaz"
    assert snap.primary_title_key == "k_france"
    assert snap.rank == "king"
    assert snap.independent is True
    assert snap.vassal_ids == [47802]
    assert snap.claim_ids == [3238]
    assert snap.succession == [16796577, 16808732]
    assert snap.succession_stability == "stable"
    assert snap.strength == 535
    assert snap.realm_strength == 535 + 112  # own + vassal 47802


def test_build_snapshot_vassal():
    g = _graph()
    snap = build_snapshot(g, 47802)
    assert snap.rank == "count"
    assert snap.independent is False
    assert snap.vassal_ids == []


def test_build_snapshots_count():
    g = _graph()
    snaps = build_snapshots(g)
    # 16801936 (king), 47802 (count), 33597185 (emperor)
    assert len(snaps) == 3


def test_bucket_strength():
    g = _graph()
    snaps = build_snapshots(g)
    bucket_strength(snaps)
    by_id = {s.ruler_id: s for s in snaps}
    # emperor (2000) strongest, count (112) weakest
    assert by_id[33597185].strength_bucket == "strong"
    assert by_id[47802].strength_bucket == "weak"
    # every bucket is a valid label
    assert {s.strength_bucket for s in snaps} <= {"weak", "average", "strong"}


def test_compute_threats():
    g = _graph()
    snaps = build_snapshots(g)
    # war 469762048: attacker 33604054 vs defender 16800639 (not in fixture chars)
    # so no threats for our fixture rulers
    for snap in snaps:
        assert compute_threats(g, snap, snaps) == []
