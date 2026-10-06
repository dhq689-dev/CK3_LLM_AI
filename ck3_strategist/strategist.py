"""LLM strategist: turns a StrategicSummary into a 5-year intent.

This is the only layer that talks to an LLM. It consumes the JSON produced by
the parser and emits the intent contract:

    {"five_year_goal", "focus", "aggression", "secondary_goal"}

The LLM call is pluggable (any ``callable(prompt) -> str``), so it works with
a local model (Ollama, llama.cpp, ...) or a hosted API without changing the
rest of the pipeline.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Callable

_FOCUS_VALUES = ("Military", "Diplomacy", "Stewardship", "Intrigue", "Learning")


class IntentError(ValueError):
    """Raised when an LLM response cannot be parsed into a valid Intent."""


@dataclass
class Intent:
    five_year_goal: str
    focus: str
    aggression: int
    secondary_goal: str


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
        f"{t['ruler']} (power ratio {t['power_ratio']})"
        for t in (summary.get("major_threats") or [])
    ) or "none"
    opportunities = ", ".join(summary.get("major_opportunities") or []) or "none"

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

Respond with ONLY a JSON object in this exact format:
{{
  "five_year_goal": "<a concrete long-term ambition>",
  "focus": "<one of: Military, Diplomacy, Stewardship, Intrigue, Learning>",
  "aggression": <integer 0-10>,
  "secondary_goal": "<a supporting short-term goal>"
}}"""
    if retry_error:
        prompt += (
            f"\n\nYour previous response was invalid: {retry_error}\n"
            "Respond again with ONLY valid JSON matching the format above."
        )
    return prompt


def parse_intent(text: str) -> Intent:
    """Extract and validate the intent JSON from an LLM response.

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

    aggression = _coerce_aggression(data.get("aggression", 0))

    return Intent(
        five_year_goal=goal,
        focus=focus,
        aggression=aggression,
        secondary_goal=secondary,
    )


def _coerce_aggression(raw) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        try:
            value = int(float(raw))
        except (TypeError, ValueError):
            raise IntentError(
                f"invalid aggression {raw!r}; expected an integer 0-10"
            )
    return max(0, min(10, value))


class Strategist:
    def __init__(self, llm_call: Callable[[str], str], max_retries: int = 2):
        self._llm_call = llm_call
        self._max_retries = max_retries

    def plan(self, summary: dict) -> Intent:
        """Plan for one ruler, retrying with error feedback on bad output."""
        retry_error: str | None = None
        last_error: Exception | None = None
        for _ in range(self._max_retries + 1):
            prompt = build_prompt(summary, retry_error)
            response = self._llm_call(prompt)
            try:
                return parse_intent(response)
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
