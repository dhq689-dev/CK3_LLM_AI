# AGENTS.md

# CK3 LLM Strategist Project

## Objective

Replace parts of Crusader Kings III's high-level strategic AI with an LLM-driven planning layer.

The goal is NOT to replace CK3's mechanics, tactical AI, military pathfinding, economy simulation, or event system.

The goal IS to create rulers that:

- Form long-term plans
- Pursue coherent ambitions
- Behave consistently with their personality
- React to changing geopolitical conditions
- Produce emergent narratives

The LLM acts as the ruler.

CK3 remains the executor.

---

# Architecture

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

The `RealmSnapshot` layer bridges raw game data and the AI-facing summary. It
holds the per-ruler strategic state (primary title, rank, vassals, claims,
wars, succession, strength) and is where most of the game's strategic logic
lives.

---

# What We Learned From Save Analysis

The .ck3 save is a ZIP archive containing:

```text
gamestate
```

The extracted gamestate is plaintext.

Important top-level sections discovered:

```text
landed_titles = line ~302,142
dynasties     = line ~759,366
living        = line ~1,042,346
wars          = line ~7,206,474
```

The game state can therefore be parsed directly with Python.

No proprietary API appears necessary.

Key format corrections (verified against `sample_savedata/gamestate_1.txt`):

- Titles are keyed by **numeric IDs** (`0`, `1`, `2`...), not `c_`/`d_`/`k_`
  keys. The human key is a `key=` field inside the entry.
- `de_facto_liege` / `de_jure_liege` are **title IDs**, not character IDs.
- `holder` is a **character ID**.
- Military/economic strength **is** in the save: `landed_data` inside each
  character (`strength`, `levy`, `power`, `balance`, `domain`, `succession`).
- Claims live in `alive_data.claim`, not a top-level `claim={}`.
- `family_data` holds `primary_spouse` / `spouse` / `child` as character IDs.

The authoritative parser spec is `parser_implementation.md`.

Verified against two saves (`gamestate_1` = 1.19.0.6, `gamestate_2` = 1.17.0.1):
the extraction fields above are stable across versions. Known drift points
(title display-name location, optional `SAV` header line, some top-level
sections) are documented in `parser_implementation.md` §0.

---

# Phase 1 MVP Goal

Generate strategic plans for major AI rulers.

No game integration required initially.

Input:

```text
gamestate
```

Output:

```json
{
  "goal": "Expand into Antioch",

  "focus": "Diplomacy",

  "aggression": 6,

  "secondary_goal": "Secure succession"
}
```

---

# Rulers To Analyse

Do NOT run LLMs for all characters.

Use a tiered system.

## Tier 1

Always LLM-controlled:

- Emperors
- Kings

Expected count:

20-60

---

## Tier 2

Conditional LLM control:

- Powerful dukes
- Important republics
- Major clan rulers

Expected count:

50-150

---

## Tier 3

Vanilla AI:

- Counts
- Barons
- Courtiers
- Knights

No LLM planning.

---

# Data To Extract

## Character Data

Location:

```text
living={}
```

Required fields:

```json
{
  "id": "...",
  "name": "...",
  "birth": "...",

  "culture": "...",
  "faith": "...",

  "dynasty_house": "...",

  "skills": [],
  "traits": [],

  "prestige": 0,
  "piety": 0,
  "gold": 0
}
```

Example discovered:

```text
first_name=
birth=
culture=
faith=
dynasty_house=
skill=
traits=
alive_data={
    prestige={ currency=... }
    piety={ currency=... }
}
landed_data={
    balance=...
}
```

Note: `prestige` and `piety` live in `alive_data` (as `currency`); `gold` is
`landed_data.balance`. These drive strategy more strongly than skill scores
and should be extracted in Phase 1.

---

## Family Data

Required fields:

```json
{
  "primary_spouse": "...",
  "spouses": [],
  "children": []
}
```

Extract from:

```text
family_data={}
```

Purpose:

- Succession planning
- Marriage strategy
- Dynasty expansion
- Stability analysis

---

## Memories

Extract in Phase 1, use later.

Location:

```text
character_memory_manager={}
```

Each character's `alive_data.memories` holds a list of memory IDs; the detail
lives in `character_memory_manager`:

```text
16778116={
    type=became_friends
    participants={
        new_relation=43344
    }
    creation_date=883.9.1
    end_date=1013.9.1
}
```

Produce:

```json
{
  "type": "became_friends",
  "participants": [],
  "creation_date": "..."
}
```

Purpose (Phase 2+):

- Historical grudges
- Rivalries
- Character relationships
- Diplomacy systems

Extracting the raw structure now avoids revisiting the parser later.

---

## Titles

Location:

```text
landed_titles={}
```

Required fields:

```json
{
  "id": 0,
  "key": "d_swabia",

  "holder": 12345,

  "de_facto_liege": 678,
  "de_jure_liege": 678,

  "capital": 1234,

  "heirs": []
}
```

Example discovered:

```text
0={
    key=d_swabia
    holder=12345
    de_facto_liege=678
    de_jure_liege=678
    capital=1234
    heir={ 16796577 }
}
```

Note: titles are keyed by numeric ID; `key=` holds the human key. Claims are
NOT stored here — they live in the character's `alive_data.claim`.

---

## Realm Structure

Derived from title data.

Calculate:

```json
{
  "realm_size": "...",

  "counties": 0,
  "duchies": 0,
  "kingdoms": 0,

  "rank": "count/duke/king/emperor",

  "independent": true
}
```

---

## Political Hierarchy

Use:

```text
de_facto_liege
holder
```

To reconstruct:

```text
Empire
  ↓
Kingdom
  ↓
Duchy
  ↓
County
```

Purpose:

- Find vassals
- Find lieges
- Find neighbouring rulers
- Determine realm power

---

## Claims

Extract from the character's `alive_data`:

```text
alive_data={
    claim={ { title=3238 } }
}
```

Purpose:

- Expansion opportunities
- Strategic objectives
- Border conflict likelihood

Produce:

```json
{
  "available_expansion_targets": []
}
```

---

## Succession

Extract:

```text
heir={}
family_data={}
```

Generate:

```json
{
  "succession_stability": "...",
  "heir_count": 0,
  "primary_heir": "..."
}
```

---

## Dynasties

Location:

```text
dynasties={}
```

Required:

```json
{
  "dynasty_name": "...",
  "prestige": "...",
  "renown": "..."
}
```

(Optional in MVP)

---

## Wars

Location:

```text
wars={}
```

Required:

```json
{
  "war_type": "...",

  "attacker": "...",

  "defender": "...",

  "war_score": "...",

  "date_started": "..."
}
```

Purpose:

- Threat assessment
- Opportunity detection
- Strategic planning

---

# Data NOT Sent To LLM

Ignore:

- DNA
- Portrait data
- Hair
- Facial genes
- Clothing
- Graphics metadata
- Coat of arms
- Visual customisation

These are irrelevant for strategy.

---

# Intermediate Representation

The parser should NOT pass raw save data to the model.

Instead generate a strategic briefing.

Example:

```json
{
  "name": "King of England",

  "primary_title": "Kingdom of England",

  "traits": [
    "ambitious",
    "wrathful"
  ],

  "realm": {
    "size": "large",
    "military_power": "strong",
    "economic_power": "average"
  },

  "succession": {
    "stable": true
  },

  "threats": [
    {
      "ruler": "Scotland",
      "power_ratio": 1.4
    }
  ],

  "opportunities": [
    "Claim on Wales"
  ]
}
```

---

# LLM Output Format

The LLM does NOT issue actions.

The LLM issues intent.

```json
{
  "five_year_goal":
    "Unify Britannia",

  "focus":
    "Military",

  "aggression":
    8,

  "secondary_goal":
    "Secure succession"
}
```

---

# Future Work

Phase 2:

- Memory system (raw memories already extracted in Phase 1)
- Historical grudges
- Character relationships
- Negotiation system

Phase 3:

- AI diplomacy chat
- Player conversations with rulers
- Multi-agent courts
- Council simulations

---

# Current Conclusion

The save format is fully capable of supporting an LLM strategist layer.

The most important extraction targets are:

1. Characters
2. Titles
3. Claims
4. Heirs
5. Dynasties
6. Wars
7. Liege/Vassal hierarchy

These are sufficient to build a ruler-centric strategic planner without modifying CK3 itself.

---

# Implementation Plan

Ordered milestones for Phase 1. Each milestone has a concrete deliverable and
a verification step. No milestone depends on the LLM layer — the parser is
built and verified standalone first.

## Milestone 0 — Project scaffolding

- Set up a Python package (`ck3_strategist/`) with a `pyproject.toml`.
- Add `reference_data/` directory for static lookup tables.
- Add a small hand-written fixture file (a few characters + titles + one war)
  for fast unit tests, so we never test against the 170MB save during dev.

**Verify:** `pytest` runs and passes a trivial smoke test.

## Milestone 1 — Lexer + parser

- Implement a byte-safe tokenizer and recursive-descent parser for the Paradox
  scripting grammar (see `parser_implementation.md` §1).
- Support scalars, quoted strings, lists, blocks, dates, and nested anonymous
  blocks.
- Decode with `errors="replace"` (file is not clean UTF-8).
- Before writing the parser, skim existing Paradox save parsers (e.g. the
  community's CK3/EU4 parsers) for grammar references and edge cases; the
  custom parser is still expected, but this reduces re-discovering quirks.

**Verify:** parse the hand-written fixture into a nested dict; unit tests cover
each value type and the `{ { ... } }` nested-block case.

## Milestone 2 — Section indexer

- Scan the file for top-level `^key={` at column 0 and record byte/line offsets
  for `landed_titles`, `dynasties`, `living`, `wars`.
- Provide random-access seek into each section without loading the whole file.

**Verify:** against `gamestate_1.txt`, report offsets matching the known
values (landed_titles ~302,142; dynasties ~759,366; living ~1,042,346;
wars ~7,206,474).

## Milestone 3 — Character + Title extractors

- Stream-parse `living` and `landed_titles` one entry at a time.
- Extract only the field map in `parser_implementation.md` §2; discard the rest.
- Produce `Character` and `Title` dataclasses.
- Include `prestige`/`piety` (from `alive_data`) and `gold` (from
  `landed_data.balance`), plus raw `memories` IDs and the
  `character_memory_manager` detail entries.

**Verify:** extract a known character (e.g. `16801936`) and a known title
(e.g. `0` = `d_laamp_RICE_gung_ye`) and assert the fields match the raw file.

## Milestone 4 — Reference data loader

- Load trait/culture/faith/house/title-name ID→name tables from
  `reference_data/`.
- Resolve numeric IDs to human-readable names in the extracted objects.

**Verify:** `traits={ 63 59 55 3 }` resolves to named traits; a title key
resolves to a display name.

## Milestone 5 — WorldGraph

- Build `characters`, `titles`, `dynasties`, `wars` maps.
- Implement `get_ruler`, `get_vassals`, `get_liege`, `get_realm_titles`.

**Verify:** for a known king, `get_vassals` returns the expected set and
`get_realm_titles` reconstructs the realm via `de_facto_liege` closure.

## Milestone 6 — RealmSnapshot + derived values

- Build the `RealmSnapshot` layer (the bridge between `WorldGraph` and
  `StrategicSummary`), holding per-ruler primary title, rank, vassals, claims,
  wars, succession, and strength.
- Realm reconstruction (primary title, rank, independent flag).
- Military/economic strength bucketing from `landed_data` (percentile-based).
- Succession stability from `landed_data.succession` + `family_data`.
- Threats/opportunities from claims + active wars + shared de-jure liege
  (no geographic adjacency in MVP), each threat carrying a `power_ratio`.

**Verify:** produce a `RealmSnapshot` for a sample ruler and eyeball that
strength/succession/threats are sensible.

## Milestone 7 — Significant-ruler detection

- Implement Tier 1 (emperors, kings) and Tier 2 (top dukes) rules.

**Verify:** count matches the expected 20-60 Tier 1 rulers; spot-check a few.

## Milestone 8 — StrategicSummary builder + JSON output

- Emit the `StrategicSummary` JSON (the only structure sent to the LLM).
- Assert each summary is under 5k tokens.

**Verify:** dump summaries for all Tier 1 rulers to `output/`; confirm size
budget and spot-check content.

## Milestone 9 — LLM strategist (separate layer)

- Consume `StrategicSummary` JSON, emit the intent contract
  (`five_year_goal`, `focus`, `aggression`, `secondary_goal`).
- No game integration.

**Verify:** run against a local LLM on a handful of rulers; confirm valid JSON
output matching the contract.

---

## Cross-cutting rules

- Never `read()` the whole 170MB file into memory; stream or mmap.
- Never hardcode a closed set of keys — the save is modded (RICE/EP3) and
  contains unknown keys and title prefixes.
- Use `de_facto_liege` for politics, `de_jure_liege` only for claims/expansion.
- The parser must remain LLM-agnostic; the LLM layer consumes JSON only.