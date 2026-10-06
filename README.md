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
(`five_year_goal`, `focus`, `aggression`, `secondary_goal`), never raw actions.

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

Phase 2 (memory, relationships, negotiation) is in progress:

- [x] Milestone 10 — Memory extractor
- [ ] Milestone 11 — Relationship graph
- [ ] Milestone 12 — Relationship summary (LLM-facing)
- [ ] Milestone 13 — Negotiation system (sketch)

## Setup

```bash
pip install -e ".[dev]"
pytest
```

## Project layout

```text
ck3_strategist/   # the parser package
  lexer.py        # byte-safe tokenizer
  parser.py       # recursive-descent parser
  indexer.py      # top-level section indexer
  extract.py      # character/title/dynasty/war extractors
  reference.py    # ID→name lookup tables (from the save)
  graph.py        # WorldGraph (liege/vassal hierarchy)
  snapshot.py     # RealmSnapshot + derived values
  tiers.py        # significant-ruler detection
  summary.py      # StrategicSummary builder
  strategist.py   # LLM strategist (intent contract)
reference_data/   # reserved for static lookup tables
tests/            # unit tests + hand-written fixture
sample_savedata/  # real saves (gitignored, large)
```

## Documentation

- `agents.md` — project vision, data model, and implementation plan.
- `parser_implementation.md` — authoritative parser spec (grammar, field map,
  derived-value logic, version-proofing).
- `review_notes.md` — design review and recommendations.
