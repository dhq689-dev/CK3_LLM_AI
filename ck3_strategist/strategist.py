"""LLM strategist: turns a StrategicSummary into a 5-year intent.

This is the only layer that talks to an LLM. It consumes the JSON produced by
the parser and emits the intent contract:

    {"five_year_goal", "focus", "secondary_goal", "aggression_deviation", "moves"}

Targets use *stable refs* -- a title key (``k_france``) when the character holds
land, or ``char:<id>`` for the landless. Numeric character IDs are avoided
because they do not survive succession.

Aggression is a *deviation* from the deterministic trait-derived baseline
carried in the summary, not an absolute value; effective aggression is
``clamp(baseline + deviation)``. This stops LLMs clustering around 6-8.

The ``moves`` list is *constrained* to the per-ruler menu in the summary: any
move whose ref is not a menu option for its kind is dropped.

The LLM call is pluggable (any ``callable(prompt) -> str``), so it works with
a local model (Ollama, llama.cpp, ...) or a hosted API without changing the
rest of the pipeline.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field

_FOCUS_VALUES = ("Military", "Diplomacy", "Stewardship", "Intrigue", "Learning")
_MOVE_KINDS = ("war", "alliance", "peace")
_MOVE_LIST_KEY = {
    "war": "war_targets",
    "alliance": "alliance_candidates",
    "peace": "peace_options",
}
_MAX_DEVIATION = 3
_DEFAULT_BASELINE = 5


class IntentError(ValueError):
    """Raised when an LLM response cannot be parsed into a valid Intent."""


@dataclass
class Move:
    kind: str  # one of: war, alliance, peace
    ref: str  # a menu ref (title key, or ``char:<id>`` for the landless)
    reason: str = ""


@dataclass
class Intent:
    five_year_goal: str
    focus: str
    aggression: int
    aggression_deviation: int
    secondary_goal: str
    moves: list[Move] = field(default_factory=list)


def _render_menu(summary: dict) -> str:
    """Render the summary's ``moves`` block as prompt lines."""
    moves = summary.get("moves") or {}
    war = ", ".join(
        f"{t['ref']} (held by {t.get('holder')})"
        for t in (moves.get("war_targets") or [])
        if t.get("ref")
    ) or "none"
    alliance = ", ".join(
        f"{c['ref']} ({c.get('ruler')}, {c.get('reason')})"
        for c in (moves.get("alliance_candidates") or [])
        if c.get("ref")
    ) or "none"
    peace = ", ".join(
        f"{c['ref']} ({c.get('ruler')})"
        for c in (moves.get("peace_options") or [])
        if c.get("ref")
    ) or "none"
    return (
        f"- War targets: {war}\n"
        f"- Alliance candidates: {alliance}\n"
        f"- Peace options: {peace}"
    )


def build_prompt(summary: dict, retry_error: str | None = None) -> str:
    """Render a StrategicSummary into a prompt for the LLM.

    ``retry_error`` (if given) is appended so a retry can correct a previous
    malformed response.
    """
    traits = ", ".join(str(t) for t in (summary.get("traits") or [])) or "none"
    skills = ", ".join(
        f"{k} {v}" for k, v in (summary.get("skills") or {}).items()
    )
    threats = ", ".join(
        f"{t['ruler']} [id={t.get('id')}] (power ratio {t['power_ratio']})"
        for t in (summary.get("major_threats") or [])
    ) or "none"
    opportunities = ", ".join(summary.get("major_opportunities") or []) or "none"
    relationships = ", ".join(
        f"{r['ruler']} ({r['kind']})"
        for r in (summary.get("relationships") or [])
    ) or "none"
    baseline = summary.get("aggression_baseline")
    if not isinstance(baseline, int):
        baseline = _DEFAULT_BASELINE

    prompt = f"""You are the strategic advisor for a Crusader Kings III ruler.
Given the situation below, produce a coherent 5-year strategic plan that is
consistent with the ruler's personality and circumstances.

Ruler: {summary.get('ruler_name')}
Title: {summary.get('title')} ({summary.get('rank')})
Age: {summary.get('age')}
Traits: {traits}
Skills: {skills}
Realm size: {summary.get('realm_size')}
Military strength: {summary.get('military_strength')}
Economic strength: {summary.get('economic_strength')}
Succession: {summary.get('succession_stability')}
Active wars: {summary.get('active_wars')}
Threats: {threats}
Opportunities: {opportunities}
Relationships: {relationships}

Aggression baseline (derived from traits): {baseline} on a 0-10 scale.
Choose ``aggression_deviation`` from -{_MAX_DEVIATION} to {_MAX_DEVIATION} to
nudge away from that baseline; keep it near 0 unless circumstances justify it.

Candidate moves (choose refs ONLY from these lists):
{_render_menu(summary)}

You may propose up to two moves. Each picks a ``ref`` from the matching list
(war targets, alliance candidates, or peace options).

Respond with ONLY a JSON object in this exact format:
{{
  "five_year_goal": "<a concrete long-term ambition>",
  "focus": "<one of: Military, Diplomacy, Stewardship, Intrigue, Learning>",
  "secondary_goal": "<a supporting short-term goal>",
  "aggression_deviation": <integer -{_MAX_DEVIATION} to {_MAX_DEVIATION}>,
  "moves": [
    {{"kind": "<war|alliance|peace>",
      "ref": "<a ref from the lists above>", "reason": "<why>"}}
  ]
}}"""
    if retry_error:
        prompt += (
            f"\n\nYour previous response was invalid: {retry_error}\n"
            "Respond again with ONLY valid JSON matching the format above."
        )
    return prompt


def parse_intent(
    text: str,
    baseline: int = _DEFAULT_BASELINE,
    valid_refs: dict[str, set[str]] | None = None,
) -> Intent:
    """Extract and validate the intent JSON from an LLM response.

    ``baseline`` is the trait-derived aggression the LLM deviates from.
    ``valid_refs`` (if given) maps move kind -> allowed refs; moves using a ref
    that is not a menu option for their kind are dropped.

    Raises :class:`IntentError` on any parse or validation failure.
    """
    # strip markdown code fences
    text = re.sub(r"```(?:json)?", "", text).strip()
    # find the outermost JSON object
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise IntentError("no JSON object found in response")
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError as e:
        raise IntentError(f"invalid JSON: {e}") from e
    if not isinstance(data, dict):
        raise IntentError("response JSON is not an object")

    goal = str(data.get("five_year_goal", "")).strip()
    secondary = str(data.get("secondary_goal", "")).strip()
    if not goal:
        raise IntentError("'five_year_goal' is missing or empty")
    if not secondary:
        raise IntentError("'secondary_goal' is missing or empty")

    focus_raw = str(data.get("focus", "")).strip()
    focus = next(
        (v for v in _FOCUS_VALUES if v.lower() == focus_raw.lower()), None
    )
    if focus is None:
        raise IntentError(
            f"invalid focus {focus_raw!r}; expected one of {', '.join(_FOCUS_VALUES)}"
        )

    if not isinstance(baseline, int):
        baseline = _DEFAULT_BASELINE
    deviation = _coerce_deviation(data.get("aggression_deviation", 0))
    aggression = max(0, min(10, baseline + deviation))
    moves = _parse_moves(data.get("moves"), valid_refs)

    return Intent(
        five_year_goal=goal,
        focus=focus,
        aggression=aggression,
        aggression_deviation=deviation,
        secondary_goal=secondary,
        moves=moves,
    )


def _parse_moves(
    raw, valid_refs: dict[str, set[str]] | None
) -> list[Move]:
    """Parse the optional ``moves`` list, dropping unknown/mismatched refs."""
    if not isinstance(raw, list):
        return []
    out: list[Move] = []
    seen: set[tuple[str, str]] = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("kind", "")).strip().lower()
        if kind not in _MOVE_KINDS:
            continue  # unknown move kind -> drop
        ref = str(item.get("ref", "")).strip()
        if not ref:
            continue
        if valid_refs is not None and ref not in valid_refs.get(kind, set()):
            continue  # not a menu option for this kind -> drop
        if (kind, ref) in seen:
            continue
        seen.add((kind, ref))
        out.append(
            Move(
                kind=kind,
                ref=ref,
                reason=str(item.get("reason", "")).strip(),
            )
        )
    return out


def _coerce_deviation(raw) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        try:
            value = int(float(raw))
        except (TypeError, ValueError):
            raise IntentError(
                f"invalid aggression_deviation {raw!r}; expected an integer "
                f"-{_MAX_DEVIATION} to {_MAX_DEVIATION}"
            ) from None
    return max(-_MAX_DEVIATION, min(_MAX_DEVIATION, value))


def _menu_refs(summary: dict) -> dict[str, set[str]] | None:
    """Allowed refs per move kind, or ``None`` when the summary has no menu."""
    moves = summary.get("moves")
    if not moves:
        return None
    refs: dict[str, set[str]] = {}
    for kind, key in _MOVE_LIST_KEY.items():
        refs[kind] = {
            item["ref"]
            for item in (moves.get(key) or [])
            if isinstance(item, dict) and item.get("ref")
        }
    return refs


class Strategist:
    def __init__(self, llm_call: Callable[[str], str], max_retries: int = 2):
        self._llm_call = llm_call
        self._max_retries = max_retries

    def plan(self, summary: dict) -> Intent:
        """Plan for one ruler, retrying with error feedback on bad output."""
        baseline = summary.get("aggression_baseline")
        if not isinstance(baseline, int):
            baseline = _DEFAULT_BASELINE
        valid_refs = _menu_refs(summary)
        retry_error: str | None = None
        last_error: Exception | None = None
        for _ in range(self._max_retries + 1):
            prompt = build_prompt(summary, retry_error)
            response = self._llm_call(prompt)
            try:
                return parse_intent(response, baseline, valid_refs)
            except IntentError as e:
                last_error = e
                retry_error = str(e)
        raise IntentError(
            f"LLM failed to produce valid intent after "
            f"{self._max_retries + 1} attempts: {last_error}"
        )


def ollama_call(
    model: str = "llama3",
    host: str = "http://localhost:11434",
    timeout: float = 120.0,
) -> Callable[[str], str]:
    """Return a callable that talks to a local Ollama server.

    Requests JSON output (Ollama's ``format: "json"``), applies a timeout, and
    raises a clear error on transport failure.

    Usage::

        strategist = Strategist(ollama_call("llama3"))
    """
    import urllib.error
    import urllib.request

    def call(prompt: str) -> str:
        payload = json.dumps(
            {
                "model": model,
                "prompt": prompt,
                "stream": False,
                "format": "json",
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            f"{host}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as e:
            raise RuntimeError(f"Ollama request to {host} failed: {e}") from e
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Ollama returned invalid JSON: {e}") from e
        return body.get("response", "")

    return call
