"""StrategicSummary builder: the only structure sent to the LLM.

Projects a RealmSnapshot (plus reference data and threats) into a compact,
JSON-serializable dict, and enforces a token budget.
"""

from __future__ import annotations

from .graph import WorldGraph
from .reference import ReferenceData
from .snapshot import RealmSnapshot, Threat

_SKILL_NAMES = [
    "diplomacy",
    "martial",
    "stewardship",
    "intrigue",
    "learning",
    "prowess",
]


def compute_age(birth: str, current: str) -> int | None:
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

    return {
        "ruler_name": snapshot.ruler_name,
        "title": snapshot.primary_title_key,
        "rank": snapshot.rank,
        "age": compute_age(char.birth if char else "", current_date),
        "traits": [
            reference.trait_name(t) for t in (char.traits if char else [])
        ],
        "skills": skills,
        "realm_size": _realm_size(len(realm_titles)),
        "military_strength": snapshot.strength_bucket,
        "economic_strength": snapshot.economic_bucket,
        "succession_stability": snapshot.succession_stability,
        "major_threats": [
            {"ruler": t.ruler_name, "power_ratio": round(t.power_ratio, 2)}
            for t in threats
        ],
        "major_opportunities": opportunities,
        "active_wars": len(snapshot.war_ids),
        "claims_available": len(snapshot.claim_ids),
    }


def estimate_tokens(summary: dict) -> int:
    """Rough token estimate (4 chars per token)."""
    import json

    return len(json.dumps(summary)) // 4


def build_summaries(
    graph: WorldGraph,
    snapshots: list[RealmSnapshot],
    reference: ReferenceData,
    current_date: str,
    max_tokens: int = 5000,
) -> list[dict]:
    """Build summaries for all snapshots, asserting the token budget."""
    summaries = []
    for snap in snapshots:
        threats = _threats_for(graph, snap, snapshots)
        summary = build_summary(graph, snap, reference, threats, current_date)
        assert estimate_tokens(summary) < max_tokens, (
            f"summary for {snap.ruler_name} exceeds {max_tokens} tokens"
        )
        summaries.append(summary)
    return summaries


def _threats_for(
    graph: WorldGraph,
    snapshot: RealmSnapshot,
    snapshots: list[RealmSnapshot],
) -> list[Threat]:
    from .snapshot import compute_threats

    return compute_threats(graph, snapshot, snapshots)
