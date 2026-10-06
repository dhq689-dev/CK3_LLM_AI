"""Tests for the WorldGraph."""

from ck3_strategist.extract import SaveReader, title_rank
from ck3_strategist.graph import WorldGraph

FIXTURE = "tests/fixtures/small_gamestate.txt"


def test_title_rank():
    assert title_rank("b_darlington") == 0
    assert title_rank("c_colmar") == 1
    assert title_rank("d_swabia") == 2
    assert title_rank("k_france") == 3
    assert title_rank("e_byzantium") == 4
    assert title_rank("h_china") == -1


def test_title_rank_with_tier():
    # modded prefixes resolve via the tier string
    assert title_rank("x_mc_0", "duchy") == 2
    assert title_rank("x_mc_0", "kingdom") == 3
    assert title_rank("x_mc_0") == -1  # no tier -> unknown


def test_worldgraph_from_fixture():
    reader = SaveReader(FIXTURE)
    g = WorldGraph.from_save(reader)
    assert set(g.characters) == {16801936, 47802, 33597185}
    assert set(g.titles) == {0, 1, 2, 3}
    assert set(g.dynasties) == {2878, 2880}
    assert set(g.wars) == {469762048}


def test_primary_title():
    reader = SaveReader(FIXTURE)
    g = WorldGraph.from_save(reader)
    # 16801936 holds title 0 (d_swabia) and title 2 (k_france); primary is k_france
    assert g.primary_title(16801936).id == 2
    # 47802 holds title 1 (c_colmar)
    assert g.primary_title(47802).id == 1


def test_get_realm_titles():
    reader = SaveReader(FIXTURE)
    g = WorldGraph.from_save(reader)
    # 16801936's realm: k_france (2) + d_swabia (0) + c_colmar (1, de_facto_liege=0)
    realm = {t.id for t in g.get_realm_titles(16801936)}
    assert realm == {0, 1, 2}


def test_get_vassals():
    reader = SaveReader(FIXTURE)
    g = WorldGraph.from_save(reader)
    # 47802 holds c_colmar (1), whose de_facto_liege is d_swabia (0), held by 16801936
    vassals = {v.id for v in g.get_vassals(16801936)}
    assert vassals == {47802}


def test_get_liege():
    reader = SaveReader(FIXTURE)
    g = WorldGraph.from_save(reader)
    # 47802's primary title c_colmar has de_facto_liege=0 (d_swabia), held by 16801936
    liege = g.get_liege(47802)
    assert liege is not None and liege.id == 16801936
    # 16801936's primary title k_france has no de_facto_liege -> independent
    assert g.get_liege(16801936) is None
