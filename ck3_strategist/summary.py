"""StrategicSummary builder: the only structure sent to the LLM.

Projects a RealmSnapshot (plus reference data and threats) into a compact,
JSON-serializable dict, and enforces a token budget.
"""

from __future__ import annotations

import logging

from .graph import WorldGraph
from .reference import ReferenceData
from .snapshot import RealmSnapshot, Threat

logger = logging.getLogger(__name__)

_SKILL_NAMES = [
    "diplomacy",
    "martial",
    "stewardship",
    "intrigue",
    "learning",
    "prowess",
]


def compute_age(birth: str, current: str) -> int | None:
    """Age in whole years.

    Placeholder: compares birth/current years only, so it can be off by one
    depending on the month/day. Refine with full date comparison later.
    """
    if not birth or not current:
        return None
    try:
        return int(current.split(".")[0]) - int(birth.split(".")[0])
    except (ValueError, IndexError):
        return None


def _realm_size(title_count: int) -> str:
    if title_count < 10:
        return "small"
    if title_count < 50:
        return "medium"
    return "large"


def build_summary(
    graph: WorldGraph,
    snapshot: RealmSnapshot,
    reference: ReferenceData,
    threats: list[Threat],
    current_date: str,
    relationships: list[dict] | None = None,
    menu=None,
    aggression_map: dict | None = None,
) -> dict:
    char = graph.get_ruler(snapshot.ruler_id)
    skills = {}
    if char is not None:
        for i, name in enumerate(_SKILL_NAMES):
            skills[name] = char.skills[i] if i < len(char.skills) else 0

    realm_titles = graph.get_realm_titles(snapshot.ruler_id)

    opportunities = [
        graph.titles[cid].key
        for cid in snapshot.claim_ids
        if cid in graph.titles
    ]

    traits = [
        reference.trait_name(t) or f"trait_{t}"
        for t in (char.traits if char else [])
    ]
    from .aggression import baseline_aggression, load_aggression_map

    baseline = baseline_aggression(
        traits, aggression_map if aggression_map is not None else load_aggression_map()
    )

    return {
        "ruler_name": snapshot.ruler_name,
        "title": snapshot.primary_title_key,
        "rank": snapshot.rank,
        "age": compute_age(char.birth if char else "", current_date),
        "traits": traits,
        "skills": skills,
        "realm_size": _realm_size(len(realm_titles)),
        "military_strength": snapshot.strength_bucket,
        "economic_strength": snapshot.economic_bucket,
        "succession_stability": snapshot.succession_stability,
        "aggression_baseline": baseline,
        "major_threats": [
            {
                "ruler": t.ruler_name,
                "id": t.ruler_id,
                "power_ratio": round(t.power_ratio, 2),
            }
            for t in threats
        ],
        "major_opportunities": opportunities,
        "relationships": relationships or [],
        "moves": _moves_block(menu),
        "active_wars": len(snapshot.war_ids),
        "claims_available": len(snapshot.claim_ids),
    }


def _moves_block(menu) -> dict:
    """Render a LegalMoves menu into a compact, LLM-facing dict."""
    if menu is None:
        return {}
    return {
        "war_targets": [
            {"ref": t.ref, "holder": t.holder_name} for t in menu.war_targets
        ],
        "alliance_candidates": [
            {"ref": c.ref, "ruler": c.ruler_name, "reason": c.reason}
            for c in menu.alliance_candidates
        ],
        "peace_options": [
            {"ref": c.ref, "ruler": c.ruler_name, "reason": c.reason}
            for c in menu.peace_options
        ],
    }


def estimate_tokens(summary: dict) -> int:
    """Rough token estimate (4 chars per token)."""
    import json

    return len(json.dumps(summary)) // 4


def truncate_summary(
    summary: dict,
    max_traits: int = 12,
    max_threats: int = 5,
    max_opportunities: int = 8,
    max_relationships: int = 10,
) -> dict:
    """Cap lower-priority fields so the summary stays within the token budget."""
    summary["traits"] = summary.get("traits", [])[:max_traits]
    summary["major_threats"] = sorted(
        summary.get("major_threats", []),
        key=lambda t: t.get("power_ratio", 0),
        reverse=True,
    )[:max_threats]
    summary["major_opportunities"] = summary.get("major_opportunities", [])[
        :max_opportunities
    ]
    summary["relationships"] = summary.get("relationships", [])[:max_relationships]
    return summary


def build_summaries(
    graph: WorldGraph,
    snapshots: list[RealmSnapshot],
    reference: ReferenceData,
    current_date: str,
    relationship_graph=None,
    menus: dict | None = None,
    aggression_map: dict | None = None,
    max_tokens: int = 5000,
) -> list[dict]:
    """Build summaries for all snapshots, truncating any that exceed the budget.

    Unlike a bare ``assert``, this never aborts the batch and survives
    ``python -O``: oversized summaries are capped and logged.
    """
    summaries = []
    for snap in snapshots:
        threats = _threats_for(graph, snap, snapshots)
        relationships = _relationships_for(
            relationship_graph, graph, snap.ruler_id
        )
        menu = (menus or {}).get(snap.ruler_id)
        summary = build_summary(
            graph,
            snap,
            reference,
            threats,
            current_date,
            relationships,
            menu,
            aggression_map,
        )
        if estimate_tokens(summary) >= max_tokens:
            summary = truncate_summary(summary)
            logger.warning(
                "summary for %s exceeded %d tokens; truncated to %d",
                snap.ruler_name,
                max_tokens,
                estimate_tokens(summary),
            )
        summaries.append(summary)
    return summaries


def _relationships_for(
    relationship_graph, graph: WorldGraph, char_id: int, max_items: int = 20
) -> list[dict]:
    """Project a ruler's relationships into compact, LLM-facing dicts."""
    if relationship_graph is None:
        return []
    from .relationships import date_key

    rels = sorted(
        relationship_graph.of(char_id),
        key=lambda r: date_key(r.date),
        reverse=True,
    )
    items = []
    for r in rels[:max_items]:
        other = graph.characters.get(r.to_char)
        name = other.name if other else str(r.to_char)
        items.append(
            {"ruler": name, "id": r.to_char, "kind": r.kind, "date": r.date}
        )
    return items


def _threats_for(
    graph: WorldGraph,
    snapshot: RealmSnapshot,
    snapshots: list[RealmSnapshot],
) -> list[Threat]:
    from .snapshot import compute_threats

    return compute_threats(graph, snapshot, snapshots)
