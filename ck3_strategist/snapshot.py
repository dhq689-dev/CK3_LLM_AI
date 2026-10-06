"""RealmSnapshot: the bridge between WorldGraph and StrategicSummary.

Holds the per-ruler strategic state (primary title, rank, vassals, claims,
wars, succession, strength) and the derived values (strength bucketing,
succession stability, threats with power_ratio).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .graph import WorldGraph

_RANK_NAMES = {0: "baron", 1: "count", 2: "duke", 3: "king", 4: "emperor"}


def rank_name(rank: int) -> str:
    return _RANK_NAMES.get(rank, "unknown")


@dataclass
class RealmSnapshot:
    ruler_id: int
    ruler_name: str
    primary_title_id: int | None
    primary_title_key: str
    rank: str
    independent: bool
    vassal_ids: list[int] = field(default_factory=list)
    claim_ids: list[int] = field(default_factory=list)
    war_ids: list[int] = field(default_factory=list)
    succession: list[int] = field(default_factory=list)
    strength: int = 0
    realm_strength: int = 0
    gold: float = 0.0
    succession_stability: str = "unstable"
    strength_bucket: str = "average"
    economic_bucket: str = "average"


@dataclass
class Threat:
    ruler_id: int
    ruler_name: str
    power_ratio: float


def build_snapshot(graph: WorldGraph, char_id: int) -> RealmSnapshot | None:
    char = graph.get_ruler(char_id)
    if char is None:
        return None
    primary = graph.primary_title(char_id)
    if primary is None:
        return None

    vassals = graph.get_vassals(char_id)
    realm_strength = char.strength + sum(v.strength for v in vassals)

    war_ids = [
        w.id
        for w in graph.wars.values()
        if w.attacker == char_id or w.defender == char_id
    ]

    succession = char.succession
    stability = "stable" if succession else "unstable"

    return RealmSnapshot(
        ruler_id=char_id,
        ruler_name=char.name,
        primary_title_id=primary.id,
        primary_title_key=primary.key,
        rank=rank_name(primary.rank),
        independent=primary.de_facto_liege is None,
        vassal_ids=[v.id for v in vassals],
        claim_ids=char.claims,
        war_ids=war_ids,
        succession=succession,
        strength=char.strength,
        realm_strength=realm_strength,
        gold=char.gold,
        succession_stability=stability,
    )


def build_snapshots(graph: WorldGraph) -> list[RealmSnapshot]:
    """Build a snapshot for every character that holds a title."""
    snapshots = []
    for char_id in graph.characters:
        snap = build_snapshot(graph, char_id)
        if snap is not None:
            snapshots.append(snap)
    return snapshots


def _percentile(values: list[int], pct: float) -> int:
    if not values:
        return 0
    s = sorted(values)
    idx = int(len(s) * pct)
    return s[min(idx, len(s) - 1)]


def bucket_strength(snapshots: list[RealmSnapshot]) -> None:
    """Assign weak/average/strong buckets by realm-strength percentile."""
    strengths = [s.realm_strength for s in snapshots]
    low = _percentile(strengths, 0.33)
    high = _percentile(strengths, 0.66)
    for s in snapshots:
        if s.realm_strength <= low:
            s.strength_bucket = "weak"
        elif s.realm_strength >= high:
            s.strength_bucket = "strong"
        else:
            s.strength_bucket = "average"


def bucket_economic(snapshots: list[RealmSnapshot]) -> None:
    """Assign weak/average/strong buckets by gold percentile."""
    golds = [int(s.gold) for s in snapshots]
    low = _percentile(golds, 0.33)
    high = _percentile(golds, 0.66)
    for s in snapshots:
        if s.gold <= low:
            s.economic_bucket = "weak"
        elif s.gold >= high:
            s.economic_bucket = "strong"
        else:
            s.economic_bucket = "average"


def compute_threats(
    graph: WorldGraph,
    snapshot: RealmSnapshot,
    snapshots: list[RealmSnapshot],
) -> list[Threat]:
    """Rulers in an active war against this ruler, each with a power ratio."""
    by_id = {s.ruler_id: s for s in snapshots}
    own = snapshot.realm_strength or 1
    threats: list[Threat] = []
    for war_id in snapshot.war_ids:
        war = graph.wars.get(war_id)
        if war is None:
            continue
        opponent = war.defender if war.attacker == snapshot.ruler_id else war.attacker
        if opponent is None or opponent == snapshot.ruler_id:
            continue
        opp = by_id.get(opponent)
        if opp is None:
            continue
        threats.append(Threat(opponent, opp.ruler_name, opp.realm_strength / own))
    return threats
