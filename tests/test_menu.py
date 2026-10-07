"""Tests for the legal-move menu."""

from ck3_strategist.extract import SaveReader
from ck3_strategist.graph import WorldGraph
from ck3_strategist.menu import build_menu, extract_relations
from ck3_strategist.relationships import RelationshipGraph

FIXTURE = "tests/fixtures/small_gamestate.txt"


def _setup():
    reader = SaveReader(FIXTURE)
    graph = WorldGraph.from_save(reader)
    rg = RelationshipGraph.from_save(
        graph, reader.memories(), current_date=reader.meta_date()
    )
    truces, alliances = extract_relations(reader)
    return graph, rg, truces, alliances


def test_extract_relations_empty_for_fixture():
    _, _, truces, alliances = _setup()
    assert truces == {}
    assert alliances == {}


def test_build_menu_war_targets():
    graph, rg, truces, alliances = _setup()
    menu = build_menu(graph, rg, 16801936, truces, alliances)
    assert menu.ruler_name == "Blaz"
    keys = {t.title_key for t in menu.war_targets}
    assert "c_colmar" in keys
    target = next(t for t in menu.war_targets if t.title_key == "c_colmar")
    assert target.holder_id == 47802
    assert target.holder_name == "Urmas"


def test_build_menu_alliance_candidates():
    graph, rg, truces, alliances = _setup()
    menu = build_menu(graph, rg, 16801936, truces, alliances)
    cands = {c.ruler_id: c.reason for c in menu.alliance_candidates}
    assert cands.get(47802) == "friend"


def test_truce_blocks_war_target():
    graph, rg, _, _ = _setup()
    # a truce with 47802 should remove the c_colmar war target
    menu = build_menu(
        graph, rg, 16801936, truces={16801936: {47802}}, alliances={}
    )
    assert all(t.holder_id != 47802 for t in menu.war_targets)
    assert menu.truces == [47802]


def test_alliance_removes_candidate():
    graph, rg, _, _ = _setup()
    menu = build_menu(
        graph, rg, 16801936, truces={}, alliances={16801936: {47802}}
    )
    assert all(c.ruler_id != 47802 for c in menu.alliance_candidates)
    assert menu.allies == [47802]
