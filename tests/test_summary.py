"""Tests for the StrategicSummary builder."""

from ck3_strategist.extract import SaveReader
from ck3_strategist.graph import WorldGraph
from ck3_strategist.reference import ReferenceData
from ck3_strategist.snapshot import build_snapshots, bucket_strength, compute_threats
from ck3_strategist.summary import build_summary, build_summaries, compute_age, estimate_tokens

FIXTURE = "tests/fixtures/small_gamestate.txt"


def _setup():
    reader = SaveReader(FIXTURE)
    graph = WorldGraph.from_save(reader)
    snapshots = build_snapshots(graph)
    bucket_strength(snapshots)
    reference = ReferenceData.from_save(reader)
    return reader, graph, snapshots, reference


def test_compute_age():
    assert compute_age("868.3.23", "918.11.5") == 50
    assert compute_age("", "918.11.5") is None
    assert compute_age("868.3.23", "") is None


def test_build_summary():
    reader, graph, snapshots, reference = _setup()
    snap = next(s for s in snapshots if s.ruler_id == 16801936)
    threats = compute_threats(graph, snap, snapshots)
    summary = build_summary(graph, snap, reference, threats, reader.meta_date())
    assert summary["ruler_name"] == "Blaz"
    assert summary["title"] == "k_france"
    assert summary["rank"] == "king"
    assert summary["age"] == 50
    assert summary["military_strength"] in ("weak", "average", "strong")
    assert summary["succession_stability"] == "stable"
    assert summary["major_opportunities"] == []  # claim 3238 not in fixture titles
    assert summary["active_wars"] == 0


def test_build_summaries_token_budget():
    reader, graph, snapshots, reference = _setup()
    summaries = build_summaries(graph, snapshots, reference, reader.meta_date())
    assert len(summaries) == len(snapshots)
    for s in summaries:
        assert estimate_tokens(s) < 5000


def test_estimate_tokens():
    assert estimate_tokens({"a": "b"}) >= 0
