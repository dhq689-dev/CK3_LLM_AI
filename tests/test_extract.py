"""Tests for the character/title extractors."""

from ck3_strategist.extract import SaveReader, extract_character, extract_title
from ck3_strategist.parser import parse

FIXTURE = "tests/fixtures/small_gamestate.txt"


def test_extract_character():
    d = parse(
        "16801936={ first_name=\"Blaz\" birth=868.3.23 culture=180 faith=135 "
        "dynasty_house=2878 skill={ 0 0 9 4 7 7 } traits={ 63 59 55 3 } "
        "alive_data={ prestige={ currency=529.32 } piety={ currency=332.31 } "
        "claim={ { title=3238 } } memories={ 1 2 3 } } "
        "family_data={ primary_spouse=17313 spouse=17313 child={ 16808732 } } "
        "landed_data={ domain={ 0 2 } strength=535 levy=335 power=11900 "
        "balance=2.9 succession={ 16796577 } government=feudal_government } }"
    )
    c = extract_character(16801936, d["16801936"])
    assert c.id == 16801936
    assert c.name == "Blaz"
    assert c.birth == "868.3.23"
    assert c.culture == 180
    assert c.faith == 135
    assert c.dynasty_house == 2878
    assert c.skills == [0, 0, 9, 4, 7, 7]
    assert c.traits == [63, 59, 55, 3]
    assert c.prestige == 529.32
    assert c.piety == 332.31
    assert c.gold == 2.9
    assert c.memories == [1, 2, 3]
    assert c.primary_spouse == 17313
    assert c.spouses == [17313]
    assert c.children == [16808732]
    assert c.claims == [3238]
    assert c.domain == [0, 2]
    assert c.strength == 535
    assert c.levy == 335
    assert c.power == 11900
    assert c.succession == [16796577]
    assert c.government == "feudal_government"


def test_extract_character_missing_landed_data():
    # Courtiers have no landed_data; fields should default safely.
    d = parse("47802={ first_name=\"Urmas\" skill={ 8 5 5 6 8 7 } }")
    c = extract_character(47802, d["47802"])
    assert c.strength == 0
    assert c.gold == 0.0
    assert c.government is None
    assert c.domain == []


def test_extract_character_multiple_spouses():
    d = parse(
        "1={ family_data={ spouse=16793754 spouse=33571628 } }"
    )
    c = extract_character(1, d["1"])
    assert c.spouses == [16793754, 33571628]


def test_extract_character_plan_vars_only_ck3llm():
    d = parse(
        "1={ alive_data={ variables={ data={ "
        "{ flag=ck3llm_plan_id data={ type=value identity=4200000 } } "
        "{ flag=ck3llm_plan_start data={ type=value identity=91800000 } } "
        "{ flag=unrelated data={ type=boolean identity=1 } } "
        "} } } }"
    )
    c = extract_character(1, d["1"])
    # type=value is fixed-point x100000, so it is normalised back
    assert c.plan_vars == {"ck3llm_plan_id": 42, "ck3llm_plan_start": 918}


def test_variable_value_normalises_fixed_point():
    from ck3_strategist.extract import _variable_value

    assert _variable_value({"type": "value", "identity": 150000}) == 1.5
    assert _variable_value({"type": "value", "identity": 4200000}) == 42
    assert _variable_value({"type": "char", "identity": 42}) == 42
    assert _variable_value({"type": "flag", "flag": "doll"}) == "doll"
    assert _variable_value({"type": "boolean", "identity": 1}) == 1


def test_extract_title():
    d = parse(
        "0={ key=d_swabia holder=16801936 de_facto_liege=2 de_jure_liege=2 "
        "capital=1234 heir={ 16796577 } }"
    )
    t = extract_title(0, d["0"])
    assert t.id == 0
    assert t.key == "d_swabia"
    assert t.holder == 16801936
    assert t.de_facto_liege == 2
    assert t.de_jure_liege == 2
    assert t.capital == 1234
    assert t.heir == [16796577]


def test_save_reader_characters():
    reader = SaveReader(FIXTURE)
    chars = {c.id: c for c in reader.characters()}
    assert set(chars) == {16801936, 47802, 33597185}
    assert chars[16801936].name == "Blaz"
    assert chars[16801936].prestige == 529.32
    assert chars[16801936].claims == [3238, 1]
    assert chars[33597185].strength == 2000


def test_save_reader_reads_plan_vars():
    reader = SaveReader(FIXTURE)
    chars = {c.id: c for c in reader.characters()}
    assert chars[16801936].plan_vars == {
        "ck3llm_plan_id": 843151954,
        "ck3llm_plan_start": 918,
    }
    assert chars[47802].plan_vars == {}


def test_save_reader_titles():
    reader = SaveReader(FIXTURE)
    titles = {t.id: t for t in reader.titles()}
    assert set(titles) == {0, 1, 2, 3}
    assert titles[0].key == "d_swabia"
    assert titles[1].de_facto_liege == 0
    assert titles[2].key == "k_france"


def test_stream_entries_ignores_nested_numeric_blocks(tmp_path):
    # a numeric-keyed block nested inside an entry must not be yielded
    content = (
        "living={\n"
        "16801936={\n"
        'first_name="Test"\n'
        "nested={\n"
        "999={\n"
        "key=x\n"
        "}\n"
        "}\n"
        "}\n"
        "}\n"
    )
    p = tmp_path / "save.txt"
    p.write_text(content)
    reader = SaveReader(str(p))
    entries = list(reader.stream_entries("living"))
    assert [k for k, _ in entries] == ["16801936"]


def test_stream_entries_indented_entries(tmp_path):
    # memory-style entries are indented inside a wrapper block
    content = (
        "character_memory_manager={\n"
        "database={\n"
        "111={\n"
        "type=became_friends\n"
        "}\n"
        "222={\n"
        "type=offensive_war\n"
        "}\n"
        "}\n"
        "}\n"
    )
    p = tmp_path / "save.txt"
    p.write_text(content)
    reader = SaveReader(str(p))
    entries = list(reader.stream_entries("character_memory_manager"))
    assert [k for k, _ in entries] == ["111", "222"]


def test_extract_error_is_counted_and_skipped(tmp_path):
    content = "living={\n1={\nfirst_name=\"A\"\n}\n2={\nfirst_name=\"B\"\n}\n}\n"
    p = tmp_path / "save.txt"
    p.write_text(content)
    reader = SaveReader(str(p))

    def flaky_extractor(cid: int, d: dict):
        if cid == 1:
            raise ValueError("boom")
        return cid

    results = [
        obj
        for key, d in reader.stream_entries("living")
        if (obj := reader._extract(flaky_extractor, key, d)) is not None
    ]
    assert results == [2]
    assert reader.errors == 1
