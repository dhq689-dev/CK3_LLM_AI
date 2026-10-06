"""Tests for the relationship graph."""

from ck3_strategist.extract import Memory, SaveReader
from ck3_strategist.graph import WorldGraph
from ck3_strategist.relationships import (
    RelationshipGraph,
    build_memory_owners,
    build_relationships,
    load_mapping,
)

FIXTURE = "tests/fixtures/small_gamestate.txt"


def _setup():
    reader = SaveReader(FIXTURE)
    graph = WorldGraph.from_save(reader)
    memories = list(reader.memories())
    return graph, memories


def test_load_mapping():
    mapping = load_mapping()
    assert mapping["became_friends"]["new_relation"] == "friend"
    assert mapping["became_rivals"]["rival"] == "rival"
    assert mapping["offensive_war"]["other_party"] == "war_enemy"


def test_build_memory_owners():
    graph, _ = _setup()
    owners = build_memory_owners(graph)
    assert owners[16778116] == 16801936
    assert owners[16778117] == 16801936


def test_build_relationships():
    graph, memories = _setup()
    rels = build_relationships(graph, memories, load_mapping())
    kinds = {(r.from_char, r.to_char): r.kind for r in rels}
    assert kinds[(16801936, 47802)] == "friend"
    assert kinds[(16801936, 33597185)] == "war_enemy"


def test_relationship_graph_from_save():
    graph, memories = _setup()
    rg = RelationshipGraph.from_save(graph, memories)
    assert any(r.to_char == 47802 for r in rg.by_kind(16801936, "friend"))
    assert any(r.to_char == 33597185 for r in rg.by_kind(16801936, "war_enemy"))
    # family_data edges
    assert any(r.to_char == 17313 for r in rg.by_kind(16801936, "spouse"))
    children = rg.by_kind(16801936, "child")
    assert {r.to_char for r in children} == {16808732, 16807449}


def test_unknown_memory_type_ignored():
    graph, _ = _setup()
    graph.characters[16801936].memories.append(999)
    mem = Memory(id=999, type="modded_new_type", participants={"rival": [1]})
    rels = build_relationships(graph, [mem], load_mapping())
    assert rels == []


def test_repeated_participants_create_multiple_edges():
    graph, _ = _setup()
    graph.characters[16801936].memories.append(1000)
    mem = Memory(
        id=1000, type="became_friends", participants={"new_relation": [11, 22]}
    )
    rels = build_relationships(graph, [mem], load_mapping())
    assert {(r.to_char, r.kind) for r in rels} == {(11, "friend"), (22, "friend")}
