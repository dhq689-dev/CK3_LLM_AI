"""Relationship graph derived from memories + family data.

The game encodes relationship semantics in memory participant keys (``rival``,
``enemy``, ``ally``, ``imprisoner``, ...). A configurable mapping
(``reference_data/relationships.json``) turns ``(memory_type, participant_key)``
into a relationship ``kind``.

Mod-added memory types that are not in the mapping are ignored by the graph but
remain visible in the raw memories passed to the LLM.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from .extract import Memory
from .graph import WorldGraph

_DEFAULT_MAPPING = (
    Path(__file__).resolve().parent.parent / "reference_data" / "relationships.json"
)


@dataclass
class Relationship:
    from_char: int
    to_char: int
    kind: str
    date: str = ""
    memory_type: str = ""


def load_mapping(path: str | Path | None = None) -> dict[str, dict[str, str]]:
    """Load the ``memory_type -> {participant_key -> kind}`` mapping."""
    p = Path(path) if path is not None else _DEFAULT_MAPPING
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def build_memory_owners(graph: WorldGraph) -> dict[int, int]:
    """Map ``memory_id -> owning character id`` (via ``Character.memories``)."""
    owners: dict[int, int] = {}
    for char in graph.characters.values():
        for mem_id in char.memories:
            owners[mem_id] = char.id
    return owners


def build_relationships(
    graph: WorldGraph,
    memories: Iterable[Memory],
    mapping: dict[str, dict[str, str]],
) -> list[Relationship]:
    """Derive relationship edges from memories."""
    owners = build_memory_owners(graph)
    relationships: list[Relationship] = []
    for mem in memories:
        owner = owners.get(mem.id)
        if owner is None:
            continue
        type_map = mapping.get(mem.type)
        if not type_map:
            continue  # unknown/modded type -> ignored by the graph
        for key, ids in mem.participants.items():
            kind = type_map.get(key)
            if kind is None:
                continue
            for other in ids:
                relationships.append(
                    Relationship(owner, other, kind, mem.creation_date, mem.type)
                )
    return relationships


def family_relationships(graph: WorldGraph) -> list[Relationship]:
    """Spouse/child edges from ``family_data``."""
    rels: list[Relationship] = []
    for char in graph.characters.values():
        for spouse in char.spouses:
            rels.append(
                Relationship(char.id, spouse, "spouse", memory_type="family_data")
            )
        for child in char.children:
            rels.append(
                Relationship(char.id, child, "child", memory_type="family_data")
            )
    return rels


def _dedupe(relationships: list[Relationship]) -> list[Relationship]:
    seen: set[tuple[int, int, str]] = set()
    out: list[Relationship] = []
    for r in relationships:
        key = (r.from_char, r.to_char, r.kind)
        if key not in seen:
            seen.add(key)
            out.append(r)
    return out


class RelationshipGraph:
    """Relationships indexed by originating character."""

    def __init__(self, relationships: list[Relationship]):
        self.relationships = relationships
        self._by_char: dict[int, list[Relationship]] = {}
        for r in relationships:
            self._by_char.setdefault(r.from_char, []).append(r)

    @classmethod
    def from_save(
        cls,
        graph: WorldGraph,
        memories: Iterable[Memory],
        mapping: dict[str, dict[str, str]] | None = None,
    ) -> RelationshipGraph:
        if mapping is None:
            mapping = load_mapping()
        rels = build_relationships(graph, memories, mapping)
        rels.extend(family_relationships(graph))
        return cls(_dedupe(rels))

    def of(self, char_id: int) -> list[Relationship]:
        """Relationships originating from ``char_id``."""
        return self._by_char.get(char_id, [])

    def by_kind(self, char_id: int, *kinds: str) -> list[Relationship]:
        return [r for r in self.of(char_id) if r.kind in kinds]
