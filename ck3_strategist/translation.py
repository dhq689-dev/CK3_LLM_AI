"""Translation layer: intent -> modifier tier + guarded hard actions.

This is the first half of the two-layer injection design (``docs/roadmap.md``
"Two-layer translation"). It does **not** write CK3 script -- that is
Milestone 18. It produces a structured :class:`Plan` the script generator can
render.

Two levers:

- **Soft steering** -- a single aggression modifier tier
  (``ck3llm_aggressive_1`` .. ``_5``), applied for a fixed number of years so
  plans expire on their own.
- **Hard actions** -- one or two discrete effects chosen from the intent's
  ``moves`` (war / alliance / peace). Every action carries its guard triggers so
  an illegal move *silently no-ops* in-game rather than erroring the log or
  corrupting the save (risk register #4, #7).

Targets are keyed on stable refs (a title key, or ``char:<id>`` for the
landless) and resolved to CK3 scopes here; numeric character IDs never appear
in the script unless the target is landless (risk register #12).

CK3 names (effects, triggers, modifier tiers) live in
``reference_data/translation.json`` so a mod/version change is a data edit.
They are **provisional** until a ``script_docs`` dump is captured (risk
register #10).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from string import Template

from .strategist import Intent, Move

_DEFAULT_TABLE = (
    Path(__file__).resolve().parent.parent / "reference_data" / "translation.json"
)


def load_translation_table(path: str | Path | None = None) -> dict:
    p = Path(path) if path is not None else _DEFAULT_TABLE
    with open(p, encoding="utf-8") as f:
        return json.load(f)


@dataclass
class GuardedAction:
    """A discrete effect plus the triggers that make it safe to attempt."""

    kind: str
    effect: str
    target_ref: str
    target_scope: str
    guards: list[str] = field(default_factory=list)
    params: dict = field(default_factory=dict)


@dataclass
class Plan:
    """The translated plan for one ruler in one cycle."""

    ruler_scope: str
    plan_id: str
    aggression: int
    modifier: str
    modifier_years: int
    actions: list[GuardedAction] = field(default_factory=list)


def ref_to_scope(ref: str, table: dict) -> str:
    """Resolve a stable ref to a CK3 scope expression.

    A title ref (``k_france``) becomes the title's holder; a landless ref
    (``char:<id>``) becomes the character scope.
    """
    scopes = table.get("scopes", {})
    prefix = str(table.get("character_ref_prefix", "char:"))
    if ref.startswith(prefix):
        cid = ref[len(prefix) :]
        return Template(scopes.get("character", "character:$id")).substitute(id=cid)
    return Template(scopes.get("title", "title:$ref.holder")).substitute(ref=ref)


def aggression_tier(aggression: int, table: dict) -> str:
    """Map an effective aggression (0-10) to a modifier tier name."""
    spec = table.get("aggression_tiers", {})
    prefix = str(spec.get("prefix", "ck3llm_aggressive_"))
    count = int(spec.get("count", 5))
    tier = 1
    for threshold in spec.get("thresholds") or []:
        if aggression > threshold:
            tier += 1
    return f"{prefix}{min(tier, count)}"


def _build_action(move: Move, table: dict) -> GuardedAction | None:
    spec = (table.get("actions") or {}).get(move.kind)
    if not spec:
        return None  # unknown move kind -> nothing to translate
    target = ref_to_scope(move.ref, table)
    guards = [
        Template(g).safe_substitute(target=target, ratio=spec.get("min_power_ratio"))
        for g in spec.get("guards", [])
    ]
    return GuardedAction(
        kind=move.kind,
        effect=str(spec.get("effect", "")),
        target_ref=move.ref,
        target_scope=target,
        guards=guards,
        params={str(spec.get("target_param", "target")): target},
    )


def translate(
    intent: Intent,
    summary: dict,
    current_date: str = "",
    table: dict | None = None,
) -> Plan:
    """Translate one ruler's intent into a :class:`Plan`.

    Hard actions are capped at ``hard_action_limit`` per cycle so rulers still
    feel like AI (design principle 6).
    """
    table = table if table is not None else load_translation_table()
    title_ref = str(summary.get("title") or "")
    ruler_scope = ref_to_scope(title_ref, table) if title_ref else ""

    tier_spec = table.get("aggression_tiers", {})
    years = int(tier_spec.get("years", table.get("default_modifier_years", 5)))
    limit = int(table.get("hard_action_limit", 2))

    actions: list[GuardedAction] = []
    for move in intent.moves:
        action = _build_action(move, table)
        if action is None:
            continue
        actions.append(action)
        if len(actions) >= limit:
            break

    plan_id = f"{title_ref}@{current_date}" if current_date else title_ref
    return Plan(
        ruler_scope=ruler_scope,
        plan_id=plan_id,
        aggression=intent.aggression,
        modifier=aggression_tier(intent.aggression, table),
        modifier_years=years,
        actions=actions,
    )
