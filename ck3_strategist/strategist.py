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


@dataclass
class Intent:
    five_year_goal: str
    focus: str
    aggression: int
    secondary_goal: str


def build_prompt(summary: dict) -> str:
    """Render a StrategicSummary into a prompt for the LLM."""
    traits = ", ".join(summary.get("traits") or []) or "none"
    skills = ", ".join(
        f"{k} {v}" for k, v in (summary.get("skills") or {}).items()
    )
    threats = ", ".join(
        f"{t['ruler']} (power ratio {t['power_ratio']})"
        for t in (summary.get("major_threats") or [])
    ) or "none"
    opportunities = ", ".join(summary.get("major_opportunities") or []) or "none"

    return f"""You are the strategic advisor for a Crusader Kings III ruler.
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


def parse_intent(text: str) -> Intent:
    """Extract and validate the intent JSON from an LLM response."""
    # strip markdown code fences
    text = re.sub(r"```(?:json)?", "", text).strip()
    # find the outermost JSON object
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("no JSON object found in response")
    data = json.loads(text[start : end + 1])

    focus = str(data.get("focus", ""))
    aggression = data.get("aggression", 0)
    if not isinstance(aggression, int):
        aggression = int(aggression)
    aggression = max(0, min(10, aggression))

    return Intent(
        five_year_goal=str(data.get("five_year_goal", "")),
        focus=focus,
        aggression=aggression,
        secondary_goal=str(data.get("secondary_goal", "")),
    )


class Strategist:
    def __init__(self, llm_call: Callable[[str], str]):
        self._llm_call = llm_call

    def plan(self, summary: dict) -> Intent:
        prompt = build_prompt(summary)
        response = self._llm_call(prompt)
        return parse_intent(response)


def ollama_call(model: str = "llama3", host: str = "http://localhost:11434") -> Callable[[str], str]:
    """Return a callable that talks to a local Ollama server.

    Usage::

        strategist = Strategist(ollama_call("llama3"))
    """
    import urllib.request

    def call(prompt: str) -> str:
        payload = json.dumps(
            {"model": model, "prompt": prompt, "stream": False}
        ).encode("utf-8")
        req = urllib.request.Request(
            f"{host}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))["response"]

    return call
