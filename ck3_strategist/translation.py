"""Translation layer: intent -> aggression tier + standing-order data.

This is the first half of the two-layer injection design (``docs/roadmap.md``
"Two-layer translation"). It does **not** write CK3 script; it produces a
structured :class:`Plan` the script generator renders.

Two levers:

- **Soft steering** -- a single aggression modifier tier
  (``ck3llm_aggressive_1`` .. ``_5``), applied for a fixed number of years so
  plans expire on their own.
- **Standing orders** -- each hard order (war / alliance) becomes a *variable*
  the ruler carries (``ck3llm_war_target`` / ``ck3llm_ally_target``). The
  generated file only sets that data; a static, hand-tested scripted effect
  (``ck3llm_execute_orders``) re-checks readiness every yearly pulse and acts
  (CG3). Keeping the action logic out of the generated file shrinks the blast
  radius and keeps the order alive for the plan's whole term instead of firing
  once.

Targets are keyed on stable refs (a title key, or ``char:<id>`` for the
landless) and resolved to CK3 scopes here.

CK3 names (effects, triggers, modifier tiers) live in
``reference_data/translation.json``; ``validate.py`` checks them against a
``script_docs`` dump.
"""

from __future__ import annotations

import json
import zlib
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
class Order:
    """A standing order: a target the ruler should keep pursuing."""

    kind: str
    var_name: str
    target_ref: str
    target_scope: str


@dataclass
class Plan:
    """The translated plan for one ruler in one cycle."""

    ruler_scope: str
    plan_id: int
    aggression: int
    modifier: str
    modifier_years: int
    plan_date: str = ""
    goal: str = ""
    focus: str = ""
    secondary_goal: str = ""
    orders: list[Order] = field(default_factory=list)
    clear_orders: list[str] = field(default_factory=list)
    clear_modifiers: list[str] = field(default_factory=list)


def make_plan_id(ruler_ref: str, current_date: str = "") -> int:
    """A stable numeric plan id (CK3 variables hold ints, not strings)."""
    raw = f"{ruler_ref}@{current_date}".encode()
    return zlib.crc32(raw) & 0xFFFFFFFF


def ref_to_scope(ref: str, table: dict, template_key: str = "title") -> str:
    """Resolve a stable ref to a CK3 scope expression.

    A title ref (``k_france``) resolves via the ``template_key`` scope template
    (default: the title's holder). A landless ref (``char:<id>``) becomes the
    character scope.
    """
    scopes = table.get("scopes", {})
    prefix = str(table.get("character_ref_prefix", "char:"))
    if ref.startswith(prefix):
        cid = ref[len(prefix) :]
        return Template(scopes.get("character", "character:$id")).substitute(id=cid)
    template = scopes.get(template_key) or scopes.get("title", "title:$ref.holder")
    return Template(template).substitute(ref=ref)


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


def all_tier_names(table: dict) -> list[str]:
    """Every aggression tier name, so the generator can clear stale ones.

    Tiers are distinct modifier keys, so without an explicit removal an old tier
    stays active alongside the new one and they partly cancel (review v4 §3).
    """
    spec = table.get("aggression_tiers", {})
    prefix = str(spec.get("prefix", "ck3llm_aggressive_"))
    count = int(spec.get("count", 5))
    return [f"{prefix}{i}" for i in range(1, count + 1)]


def all_order_vars(table: dict) -> list[str]:
    """Every standing-order variable, so the generator can clear stale ones."""
    return [
        str(spec["var"])
        for spec in (table.get("orders") or {}).values()
        if spec.get("var")
    ]


def _build_order(move: Move, table: dict) -> Order | None:
    spec = (table.get("orders") or {}).get(move.kind)
    if not spec:
        return None  # unknown move kind -> no standing order
    target = ref_to_scope(move.ref, table, spec.get("scope", "title"))
    return Order(
        kind=move.kind,
        var_name=str(spec.get("var", "")),
        target_ref=move.ref,
        target_scope=target,
    )


def translate(
    intent: Intent,
    summary: dict,
    current_date: str = "",
    table: dict | None = None,
) -> Plan:
    """Translate one ruler's intent into a :class:`Plan`.

    Standing orders are capped at ``hard_action_limit`` per cycle so rulers
    still feel like AI (design principle 6).
    """
    table = table if table is not None else load_translation_table()
    title_ref = str(summary.get("title") or "")
    ruler_scope = ref_to_scope(title_ref, table) if title_ref else ""

    tier_spec = table.get("aggression_tiers", {})
    years = int(tier_spec.get("years", table.get("default_modifier_years", 5)))
    limit = int(table.get("hard_action_limit", 2))

    orders: list[Order] = []
    for move in intent.moves:
        order = _build_order(move, table)
        if order is None:
            continue
        orders.append(order)
        if len(orders) >= limit:
            break

    plan_id = make_plan_id(title_ref, current_date)
    return Plan(
        ruler_scope=ruler_scope,
        plan_id=plan_id,
        aggression=intent.aggression,
        modifier=aggression_tier(intent.aggression, table),
        modifier_years=years,
        plan_date=current_date,
        goal=intent.five_year_goal,
        focus=intent.focus,
        secondary_goal=intent.secondary_goal,
        orders=orders,
        clear_orders=all_order_vars(table),
        clear_modifiers=all_tier_names(table),
    )


def translate_all(
    summaries: list[dict],
    intents: list[Intent],
    current_date: str = "",
    table: dict | None = None,
) -> list[Plan]:
    """Translate a cycle's summaries/intents (parallel lists) into plans."""
    table = table if table is not None else load_translation_table()
    return [
        translate(intent, summary, current_date, table)
        for summary, intent in zip(summaries, intents, strict=False)
    ]
