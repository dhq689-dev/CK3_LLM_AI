"""Significant-ruler detection (Tier 1 / Tier 2 / Tier 3).

Tier 1 (always LLM-controlled): emperors and kings.
Tier 2 (conditional LLM control): the top N dukes by realm strength.
Tier 3 (vanilla AI): everyone else.
"""

from __future__ import annotations

from .snapshot import RealmSnapshot

TIER_1 = 1
TIER_2 = 2
TIER_3 = 3


def classify_rulers(
    snapshots: list[RealmSnapshot], top_dukes: int = 100
) -> dict[int, int]:
    """Map ruler_id -> tier."""
    dukes = sorted(
        (s for s in snapshots if s.rank == "duke"),
        key=lambda s: s.realm_strength,
        reverse=True,
    )
    top_duke_ids = {s.ruler_id for s in dukes[:top_dukes]}

    tiers: dict[int, int] = {}
    for s in snapshots:
        if s.rank in ("king", "emperor"):
            tiers[s.ruler_id] = TIER_1
        elif s.rank == "duke" and s.ruler_id in top_duke_ids:
            tiers[s.ruler_id] = TIER_2
        else:
            tiers[s.ruler_id] = TIER_3
    return tiers


def significant_rulers(
    snapshots: list[RealmSnapshot], top_dukes: int = 100
) -> list[RealmSnapshot]:
    """Tier 1 + Tier 2 rulers (the ones the LLM will plan for)."""
    tiers = classify_rulers(snapshots, top_dukes)
    return [s for s in snapshots if tiers[s.ruler_id] in (TIER_1, TIER_2)]
