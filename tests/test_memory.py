"""Tests for the memory extractor."""

from ck3_strategist.extract import SaveReader, extract_memory
from ck3_strategist.parser import parse

FIXTURE = "tests/fixtures/small_gamestate.txt"


def test_extract_memory():
    d = parse(
        "16778116={ type=became_friends participants={ new_relation=43344 } "
        "creation_date=883.9.1 end_date=1013.9.1 }"
    )
    m = extract_memory(16778116, d["16778116"])
    assert m.id == 16778116
    assert m.type == "became_friends"
    assert m.participants == {"new_relation": [43344]}
    assert m.creation_date == "883.9.1"
    assert m.end_date == "1013.9.1"


def test_extract_memory_repeated_participants():
    # repeated keys become lists (witness=10 witness=11)
    d = parse("1={ type=foo participants={ witness=10 witness=11 victim=5 } }")
    m = extract_memory(1, d["1"])
    assert m.participants == {"witness": [10, 11], "victim": [5]}


def test_extract_memory_skips_non_int_participants():
    d = parse("1={ type=foo participants={ bar=123 baz=qux } }")
    m = extract_memory(1, d["1"])
    assert m.participants == {"bar": [123]}


def test_memories_from_fixture():
    reader = SaveReader(FIXTURE)
    mems = {m.id: m for m in reader.memories()}
    assert set(mems) == {16778116, 16778117}
    assert mems[16778116].type == "became_friends"
    assert mems[16778116].participants == {"new_relation": [47802]}
    assert mems[16778116].creation_date == "883.9.1"
    assert mems[16778117].type == "offensive_war"
    assert mems[16778117].participants == {"other_party": [33597185]}
