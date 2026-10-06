"""Reference data: ID -> name lookup tables extracted from the save.

The save stores numeric IDs for traits, cultures, faiths, and dynasty houses.
The human-readable keys live in the save itself:

- ``traits_lookup``            -> trait ID -> key (a flat list, index = ID)
- ``culture_manager.cultures`` -> culture ID -> ``culture_template``
- ``religion.faiths``          -> faith ID -> ``faith_type``
- ``dynasties.dynasty_house``  -> house ID -> ``name``

These are extracted once and cached in a ``ReferenceData`` object.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ReferenceData:
    traits: dict[int, str] = field(default_factory=dict)
    cultures: dict[int, str] = field(default_factory=dict)
    faiths: dict[int, str] = field(default_factory=dict)
    houses: dict[int, str] = field(default_factory=dict)

    @classmethod
    def from_save(cls, reader) -> "ReferenceData":
        traits = {}
        lookup = reader.read_section("traits_lookup")
        if isinstance(lookup, list):
            for i, key in enumerate(lookup):
                traits[i] = key

        cultures = {}
        cm = reader.read_section("culture_manager") or {}
        for id_str, entry in (cm.get("cultures") or {}).items():
            cultures[int(id_str)] = entry.get("culture_template", "")

        faiths = {}
        rel = reader.read_section("religion") or {}
        for id_str, entry in (rel.get("faiths") or {}).items():
            faiths[int(id_str)] = entry.get("faith_type", "")

        houses = {}
        dyn = reader.read_section("dynasties") or {}
        for id_str, entry in (dyn.get("dynasty_house") or {}).items():
            if isinstance(entry, dict):
                houses[int(id_str)] = entry.get("name", "")

        return cls(traits=traits, cultures=cultures, faiths=faiths, houses=houses)

    def trait_name(self, trait_id: int) -> str | None:
        return self.traits.get(trait_id)

    def culture_name(self, culture_id: int) -> str | None:
        return self.cultures.get(culture_id)

    def faith_name(self, faith_id: int) -> str | None:
        return self.faiths.get(faith_id)

    def house_name(self, house_id: int) -> str | None:
        return self.houses.get(house_id)
