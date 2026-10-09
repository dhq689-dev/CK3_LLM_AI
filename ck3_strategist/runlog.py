"""Cycle logging for evaluation (Milestone 20).

One JSONL file per cycle records, per ruler, the prompt sent, the raw LLM
response(s), the parsed intent, the translated plan, and the run's seed/model.
That is everything needed to reproduce a run and to score plan adherence after
the game produces the next save.
"""

from __future__ import annotations

import json
from pathlib import Path


def cycle_filename(date: str) -> str:
    """``918.11.5`` -> ``cycle_918-11-5.jsonl``."""
    safe = str(date).replace(".", "-") or "unknown"
    return f"cycle_{safe}.jsonl"


def write_cycle(path: str | Path, date: str, entries: list[dict]) -> Path:
    """Append one JSON object per entry to a JSONL file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps({"date": date, **entry}, ensure_ascii=False) + "\n")
    return path


def load_cycle(path: str | Path) -> list[dict]:
    """Read a JSONL cycle log back into a list of entry dicts."""
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]
