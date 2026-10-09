"""Legal-move menu: a candidate set of moves per ruler.

The menu is *plausible*, not *legal* -- in-game triggers remain the final
arbiter. It gives the LLM a constrained list to choose from instead of free
text.

Sources:

- war targets    <- ``Character.claims`` on titles held by someone else
- alliance cands <- positive relationships (friend/spouse/lover/crush/ally)
- peace options  <- active wars
- truces/allies  <- the save's ``relations`` section

Adjacency is **not** used yet (the save has none); war targets are claim-based.
Static map data is a future enhancement (see ``roadmap.md`` Milestone 15).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .extract import SaveReader
from .graph import WorldGraph
from .relationships import RelationshipGraph

# relationship kinds that make a ruler a plausible ally
_ALLIANCE_KINDS = frozenset({"friend", "spouse", "lover", "crush", "ally"})


@dataclass
class WarTarget:
    title_id: int
    title_key: str
    holder_id: int | None
    holder_name: str

    @property
    def ref(self) -> str:
        """Stable reference used in the intent contract (a title key)."""
        return self.title_key


@dataclass
class Candidate:
    ruler_id: int
    ruler_name: str
    reason: str
    ref: str = ""


@dataclass
class LegalMoves:
    ruler_id: int
    ruler_name: str
    war_targets: list[WarTarget] = field(default_factory=list)
    alliance_candidates: list[Candidate] = field(default_factory=list)
    peace_options: list[Candidate] = field(default_factory=list)
    truces: list[int] = field(default_factory=list)
    allies: list[int] = field(default_factory=list)


def extract_relations(
    reader: SaveReader,
) -> tuple[dict[int, set[int]], dict[int, set[int]]]:
    """Return ``(truces, alliances)`` as ``char_id -> {other_char_id, ...}``."""
    rel = reader.read_section("relations") or {}
    truces: dict[int, set[int]] = {}
    alliances: dict[int, set[int]] = {}
    entries = rel.get("active_relations") if isinstance(rel, dict) else None
    for entry in entries or []:
        if not isinstance(entry, dict):
            continue
        first = entry.get("first")
        second = entry.get("second")
        if not isinstance(first, int) or not isinstance(second, int):
            continue
        if any(k.startswith("truce_") for k in entry):
            truces.setdefault(first, set()).add(second)
            truces.setdefault(second, set()).add(first)
        if "alliances" in entry:
            alliances.setdefault(first, set()).add(second)
            alliances.setdefault(second, set()).add(first)
    return truces, alliances


def _name(graph: WorldGraph, char_id: int | None) -> str:
    if char_id is None:
        return "unheld"
    char = graph.characters.get(char_id)
    return char.name if char else str(char_id)


def _ref(graph: WorldGraph, char_id: int) -> str:
    """Stable ref: the ruler's primary title key, or ``char:<id>`` if landless."""
    primary = graph.primary_title(char_id)
    return primary.key if primary else f"char:{char_id}"


def build_menu(
    graph: WorldGraph,
    relationships: RelationshipGraph,
    ruler_id: int,
    truces: dict[int, set[int]] | None = None,
    alliances: dict[int, set[int]] | None = None,
) -> LegalMoves:
    """Build the candidate menu for one ruler."""
    truces = truces or {}
    alliances = alliances or {}
    char = graph.characters.get(ruler_id)
    menu = LegalMoves(
        ruler_id=ruler_id, ruler_name=char.name if char else str(ruler_id)
    )
    if char is None:
        return menu

    truced = truces.get(ruler_id, set())
    allied = alliances.get(ruler_id, set())
    menu.truces = sorted(truced)
    menu.allies = sorted(allied)

    # --- war targets: claims on titles held by someone else ---
    for title_id in char.claims:
        title = graph.titles.get(title_id)
        if title is None or title.holder in (None, ruler_id):
            continue
        if title.holder in truced:
            continue  # a truce blocks pressing the claim
        menu.war_targets.append(
            WarTarget(
                title_id=title_id,
                title_key=title.key,
                holder_id=title.holder,
                holder_name=_name(graph, title.holder),
            )
        )

    # --- alliance candidates: positive relationships, not already allied ---
    seen: set[int] = set()
    for rel in relationships.of(ruler_id):
        if rel.kind not in _ALLIANCE_KINDS:
            continue
        other = rel.to_char
        if other == ruler_id or other in seen:
            continue
        if other in allied or other in truced:
            continue
        seen.add(other)
        menu.alliance_candidates.append(
            Candidate(other, _name(graph, other), rel.kind, _ref(graph, other))
        )

    # --- peace options: opponents in active wars ---
    seen.clear()
    for war in graph.wars.values():
        if war.attacker == ruler_id and war.defender is not None:
            opponent = war.defender
        elif war.defender == ruler_id and war.attacker is not None:
            opponent = war.attacker
        else:
            continue
        if opponent == ruler_id or opponent in seen:
            continue
        seen.add(opponent)
        menu.peace_options.append(
            Candidate(
                opponent, _name(graph, opponent), war.war_type, _ref(graph, opponent)
            )
        )

    return menu
