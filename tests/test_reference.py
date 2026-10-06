"""Tests for the reference data loader."""

from ck3_strategist.extract import SaveReader
from ck3_strategist.reference import ReferenceData

FIXTURE = "tests/fixtures/small_gamestate.txt"


def test_reference_data_from_fixture():
    # The fixture has no traits_lookup/culture_manager/religion sections, so
    # those mappings are empty; it does have a dynasty_house section.
    reader = SaveReader(FIXTURE)
    ref = ReferenceData.from_save(reader)
    assert ref.traits == {}
    assert ref.cultures == {}
    assert ref.faiths == {}
    assert ref.houses == {2878: "dynn_Chandela", 2880: "dynn_Solanki"}


def test_lookup_methods_return_none_for_unknown():
    ref = ReferenceData(traits={63: "lustful"}, cultures={180: "akan"})
    assert ref.trait_name(63) == "lustful"
    assert ref.trait_name(999) is None
    assert ref.culture_name(180) == "akan"
    assert ref.faith_name(1) is None
    assert ref.house_name(1) is None
