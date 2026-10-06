# CK3 LLM Strategist

Replace parts of Crusader Kings III's high-level strategic AI with an
LLM-driven planning layer.

The goal is **not** to replace CK3's mechanics, tactical AI, military
pathfinding, economy simulation, or event system. The goal is to create rulers
that form long-term plans, pursue coherent ambitions, behave consistently with
their personality, and react to changing geopolitical conditions — producing
emergent narratives.

The LLM acts as the ruler. CK3 remains the executor.

## Architecture

```text
CK3 Save
    ↓
Save Parser
    ↓
World Graph Builder
    ↓
Realm Snapshot Builder
    ↓
Strategic Summary Builder
    ↓
LLM Strategist
    ↓
5-Year Strategic Plan
    ↓
AI Weight/Modifier System
    ↓
CK3 Executes Decisions
```

The parser is LLM-agnostic: it converts a save into a `StrategicSummary` JSON,
which is the only structure sent to the LLM. The LLM issues *intent*
(`five_year_goal`, `focus`, `aggression`, `secondary_goal`, `negotiations`),
never raw actions.

> **Status of the last two boxes:** the repository currently stops at
> "LLM Strategist → 5-Year Strategic Plan". The **AI Weight/Modifier System**
> and **CK3 Executes Decisions** stages are *not implemented* — applying the
> intent back into CK3 is the hardest part of the project and is still to do.

## Example

A `StrategicSummary` for one ruler (abridged):

```json
{
  "ruler_name": "Shiyan",
  "title": "k_lingxi",
  "rank": "king",
  "age": 51,
  "traits": ["content", "vengeful", "chaste", "education_diplomacy_3"],
  "skills": {"diplomacy": 6, "martial": 3, "intrigue": 7, "learning": 7},
  "realm_size": "large",
  "military_strength": "strong",
  "economic_strength": "strong",
  "succession_stability": "stable",
  "major_threats": [{"ruler": "Xingfang", "power_ratio": 0.71}],
  "active_wars": 1
}
```

The LLM turns that into an *intent*:

```json
{
  "five_year_goal": "Unify the Lingxi basin",
  "focus": "Military",
  "aggression": 7,
  "secondary_goal": "Neutralise Xingfang before expanding",
  "negotiations": [
    {"target_id": 16813541, "type": "alliance", "reason": "shared rival"}
  ]
}
```

## How it works

A `.ck3` save is a ZIP archive containing a plaintext `gamestate` file in
Paradox's scripting syntax. The parser:

1. Indexes the top-level sections (`landed_titles`, `dynasties`, `living`,
   `wars`, `character_memory_manager`) for random access.
2. Stream-parses characters and titles into domain objects.
3. Reconstructs the political hierarchy (liege/vassal) via `de_facto_liege`.
4. Builds a per-ruler `RealmSnapshot` (primary title, rank, vassals, claims,
   wars, succession, strength).
5. Emits a `StrategicSummary` for each significant ruler (Tier 1: emperors and
   kings; Tier 2: powerful dukes).

## Status

Phase 1 is complete. All milestones done:

- [x] Milestone 0 — Project scaffolding
- [x] Milestone 1 — Lexer + recursive-descent parser
- [x] Milestone 2 — Section indexer
- [x] Milestone 3 — Character + Title extractors
- [x] Milestone 4 — Reference data loader
- [x] Milestone 5 — WorldGraph
- [x] Milestone 6 — RealmSnapshot + derived values
- [x] Milestone 7 — Significant-ruler detection
- [x] Milestone 8 — StrategicSummary builder + JSON output
- [x] Milestone 9 — LLM strategist

Phase 2 (memory, relationships, negotiation) is complete:

- [x] Milestone 10 — Memory extractor
- [x] Milestone 11 — Relationship graph
- [x] Milestone 12 — Relationship summary (LLM-facing)
- [x] Milestone 13 — Negotiation intents (sketch)

Phase 3 (injecting intent into CK3) is **planned, not started** — see the
Phase 3 Plan in `agents.md`. It covers soft steering (AI personality
modifiers) + hard actions (the game's own effects), delivered via a generated
mod, keyed on titles, with a save-based feedback loop.

## Setup

```bash
pip install -e ".[dev]"
pytest
```

## Usage

```bash
# plaintext gamestate, or a .ck3 save (ZIP; gamestate is extracted automatically)
python -m ck3_strategist path/to/gamestate_1.txt --output output --tier 1

# also run the LLM strategist against a local Ollama model
python -m ck3_strategist path/to/save.ck3 --llm ollama --model llama3
```

Options:

- `--tier 1` (default) — kings and emperors only.
- `--tier 2` — also the top dukes.
- `--llm none` (default) / `--llm ollama`.
- `--output DIR` — where `summaries.json` (and `intents.json`) are written.

## Project layout

```text
ck3_strategist/   # the parser package
  lexer.py        # byte-safe tokenizer
  parser.py       # recursive-descent parser
  indexer.py      # top-level section indexer
  extract.py      # character/title/dynasty/war/memory extractors
  reference.py    # ID→name lookup tables (from the save)
  graph.py        # WorldGraph (liege/vassal hierarchy)
  snapshot.py     # RealmSnapshot + derived values
  tiers.py        # significant-ruler detection
  summary.py      # StrategicSummary builder
  relationships.py # relationship graph (from memories)
  strategist.py   # LLM strategist (intent contract)
  cli.py          # command-line entry point
reference_data/   # static lookup tables (relationships.json)
tests/            # unit tests + hand-written fixture
sample_savedata/  # real saves (gitignored, large)
```

## Documentation

- `agents.md` — project vision, data model, and implementation plan.
- `parser_implementation.md` — authoritative parser spec (grammar, field map,
  derived-value logic, version-proofing).
- `docs/review_notes.md` / `docs/review_notes_v2.md` — design reviews and
  recommendations.

## Development

```bash
ruff check .   # lint
mypy           # type-check
pytest         # test
```
