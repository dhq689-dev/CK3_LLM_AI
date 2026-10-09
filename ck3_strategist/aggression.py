"""Trait-derived aggression baseline.

LLMs cluster (most rulers come back "aggression 6-8"). To counter that and keep
rulers personality-consistent, we compute a **deterministic** baseline from the
ruler's traits; the LLM then only chooses *targets* and *deviations* from it.

The mapping lives in ``reference_data/aggression_traits.json`` so it stays
mod-agnostic (a mod adding traits just adds entries).
"""

from __future__ import annotations

import json
from pathlib import Path

_DEFAULT_MAPPING = (
    Path(__file__).resolve().parent.parent
    / "reference_data"
    / "aggression_traits.json"
)


def load_aggression_map(path: str | Path | None = None) -> dict:
    p = Path(path) if path is not None else _DEFAULT_MAPPING
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def baseline_aggression(traits: list[str], mapping: dict) -> int:
    """Aggression 0-10 from traits (base + per-trait deltas, clamped)."""
    score = mapping.get("base", 5)
    deltas = mapping.get("deltas", {})
    score += sum(deltas.get(t, 0) for t in traits)
    return max(0, min(10, score))
