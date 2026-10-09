"""Tests for the StrategicSummary builder."""

from ck3_strategist.extract import SaveReader
from ck3_strategist.graph import WorldGraph
from ck3_strategist.reference import ReferenceData
from ck3_strategist.snapshot import bucket_strength, build_snapshots, compute_threats
from ck3_strategist.summary import (
    build_summaries,
    build_summary,
    compute_age,
    estimate_tokens,
)

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
    assert summary["major_opportunities"] == ["c_colmar"]  # claim on title 1
    assert summary["active_wars"] == 0


def test_build_summaries_token_budget():
    reader, graph, snapshots, reference = _setup()
    summaries = build_summaries(graph, snapshots, reference, reader.meta_date())
    assert len(summaries) == len(snapshots)
    for s in summaries:
        assert estimate_tokens(s) < 5000


def test_estimate_tokens():
    assert estimate_tokens({"a": "b"}) >= 0


def test_unknown_trait_does_not_crash():
    # Unknown trait IDs (mods/DLC) must not crash the summary/prompt.
    from ck3_strategist.strategist import build_prompt

    summary = {
        "ruler_name": "X", "title": "k_x", "rank": "king", "age": 30,
        "traits": ["unknown_trait_999"], "skills": {}, "realm_size": "small",
        "military_strength": "weak", "economic_strength": "weak",
        "succession_stability": "stable", "major_threats": [],
        "major_opportunities": [], "active_wars": 0, "claims_available": 0,
    }
    build_prompt(summary)  # must not raise


def test_truncate_summary():
    from ck3_strategist.summary import truncate_summary

    summary = {
        "traits": [f"t{i}" for i in range(50)],
        "major_threats": [
            {"ruler": f"r{i}", "power_ratio": i} for i in range(20)
        ],
        "major_opportunities": [f"o{i}" for i in range(50)],
    }
    out = truncate_summary(summary)
    assert len(out["traits"]) == 12
    assert len(out["major_threats"]) == 5
    assert len(out["major_opportunities"]) == 8
    # threats kept strongest-first
    assert out["major_threats"][0]["power_ratio"] == 19


def test_build_summaries_truncates_instead_of_aborting(caplog):
    reader, graph, snapshots, reference = _setup()
    # tiny budget forces truncation; must not raise
    summaries = build_summaries(
        graph, snapshots, reference, reader.meta_date(), max_tokens=1
    )
    assert len(summaries) == len(snapshots)


def test_build_summaries_includes_relationships():
    reader, graph, snapshots, reference = _setup()
    from ck3_strategist.relationships import RelationshipGraph

    rg = RelationshipGraph.from_save(
        graph, reader.memories(), current_date=reader.meta_date()
    )
    summaries = build_summaries(
        graph, snapshots, reference, reader.meta_date(), relationship_graph=rg
    )
    by_name = {s["ruler_name"]: s for s in summaries}
    blaz = by_name["Blaz"]
    kinds = {r["kind"] for r in blaz["relationships"]}
    assert "friend" in kinds
    assert "war_enemy" in kinds
    assert all("ruler" in r and "date" in r for r in blaz["relationships"])


def test_build_summary_includes_aggression_baseline():
    reader, graph, snapshots, reference = _setup()
    snap = next(s for s in snapshots if s.ruler_id == 16801936)
    threats = compute_threats(graph, snap, snapshots)
    summary = build_summary(graph, snap, reference, threats, reader.meta_date())
    assert 0 <= summary["aggression_baseline"] <= 10
    assert summary["moves"] == {}  # no menu supplied


def test_build_summary_renders_menu_as_moves():
    from ck3_strategist.menu import build_menu, extract_relations
    from ck3_strategist.relationships import RelationshipGraph

    reader, graph, snapshots, reference = _setup()
    snap = next(s for s in snapshots if s.ruler_id == 16801936)
    threats = compute_threats(graph, snap, snapshots)
    rg = RelationshipGraph.from_save(
        graph, reader.memories(), current_date=reader.meta_date()
    )
    truces, alliances = extract_relations(reader)
    menu = build_menu(graph, rg, 16801936, truces, alliances)
    summary = build_summary(
        graph, snap, reference, threats, reader.meta_date(), menu=menu
    )
    refs = {t["ref"] for t in summary["moves"]["war_targets"]}
    assert "c_colmar" in refs
