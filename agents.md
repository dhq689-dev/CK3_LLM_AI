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

---

# Phase 2 Plan — Memory, Relationships, Negotiation

Phase 2 turns the raw memories (already extracted in Phase 1) into a
relationship layer: historical grudges, rivalries, friendships, and a
negotiation system. It must stay mod-, version-, and LLM-agnostic.

## Key insight

The save already encodes relationship *semantics* in the memory participant
keys. A memory is not just "something happened" — it is "I became rivals with
X", "I was imprisoned by Y", "I fought an offensive war against Z":

```text
became_rivals  -> participants={ rival=2300 }
offensive_war  -> participants={ other_party=2876 }
imprisoned     -> participants={ imprisoner=8549 }
became_friends -> participants={ new_relation=14857 }
```

So relationships are *derived*, not inferred — the game tells us the type and
direction directly. Verified against `gamestate_1.txt`: 154,142 memories with
semantic participant keys (`rival`, `enemy`, `ally`, `imprisoner`, `victim`,
`spouse`, `child`, `guardian`, `ward`, `other_party`, ...).

## Design principles

1. **Mod-agnostic** — never hardcode a closed set of memory types or
   participant keys. Relationship derivation uses a *configurable mapping*
   (a JSON data file), not `if type == "became_rivals"` in code. A mod adding
   a new memory type needs a new mapping entry, not a code change.
2. **Version-agnostic** — `character_memory_manager` with its `database={}`
   wrapper is verified stable across 1.17 and 1.19; the memory fields
   (`type`, `participants`, `creation_date`) are stable.
3. **LLM-agnostic** — two outputs, both plain JSON:
   - a **structured relationship graph** (for non-LLM logic: threat
     detection, stability),
   - a **raw memory summary** (for the LLM to interpret naturally).

## Data model

```python
@dataclass
class Memory:
    id: int
    type: str                      # "became_rivals", "offensive_war", ...
    participants: dict[str, list[int]]  # {"rival": [2300]}, {"witness": [10, 11]}, ...
    creation_date: str
    end_date: str                  # expiry; filtered against meta_date()

@dataclass
class Relationship:
    from_char: int
    to_char: int
    kind: str        # "rival", "war_enemy", "ally", "captor", "friend", ...
    date: str
    memory_type: str # the raw game memory type (mod-agnostic)
```

## Milestones

### Milestone 10 — Memory extractor

- Stream `character_memory_manager.database` (154k entries) into `Memory`
  objects.
- Link each memory to its owner via `Character.memories` (already extracted).

**Verify:** extract a known memory; assert type/participants/date match the raw
file.

### Milestone 11 — Relationship graph

- Build `Relationship` edges from memories + `family_data` (spouse/child are
  already relationships).
- Use a configurable `memory_type + participant_key -> kind` mapping (JSON in
  `reference_data/`).

**Verify:** for a known ruler, list their rivals, enemies, allies, and grudges;
eyeball that they are sensible.

### Milestone 12 — Relationship summary (LLM-facing)

- Add a `relationships` block to the `StrategicSummary` (or a sibling
  structure): grudges, rivalries, friendships, alliances, each with a date.
- Keep it under the token budget.

**Verify:** summaries include relationships; still <5k tokens.

### Milestone 13 — Negotiation system (sketch)

A negotiation is just an *intent* — the LLM decides who to ally with, marry,
or make peace with, informed by the relationship graph. It is not a new
subsystem; it is an extension of the existing intent contract.

Extended intent contract:

```json
{
  "five_year_goal": "Unify Britannia",
  "focus": "Military",
  "aggression": 8,
  "secondary_goal": "Secure succession",
  "negotiations": [
    {"target": "King of France", "type": "alliance", "reason": "shared rival"},
    {"target": "Duke of Aquitaine", "type": "marriage", "reason": "secure succession"}
  ]
}
```

Prompt additions: the relationship summary (Milestone 12) is fed to the LLM,
which is instructed to propose negotiations consistent with the ruler's
grudges, rivalries, and friendships.

Out of scope (deferred to Phase 3 / game integration):

- Multi-turn back-and-forth (offer / counter-offer / accept).
- Evaluating incoming offers.
- Actually executing a negotiation in CK3 (the project does not modify CK3).

**Verify (when implemented):** the LLM emits a `negotiations` list whose
targets are drawn from the relationship graph; valid JSON matching the
contract.

## Open design decision

Where does the memory-type -> relationship mapping live?

- **A) Configurable JSON file** (recommended) — fully mod-agnostic, but
  requires maintaining a mapping file.
- **B) Pass raw memories straight to the LLM** — zero mapping, maximally
  mod-agnostic, but the structured graph still needs *some* mapping.

Do **both**: the configurable mapping drives the structured graph, and the raw
memories are also passed to the LLM so it can interpret anything the mapping
does not cover.

---

# Phase 3 Plan — Injecting intent into CK3

Phase 3 turns the LLM's intent into actual CK3 AI behaviour. It is the hardest
part of the project: the LLM brain exists, but nothing yet *applies* its plan
to the game.

## The core constraint

CK3 takes no outside input while running. It cannot read files at runtime. So a
plan must be **baked into script** and delivered either at load time (a
generated mod) or through the console. This makes the loop **turn-based**:
save → parse → plan → write → restart → load.

## Design principles

1. **Soft steering + hard actions.** Soft modifiers nudge the AI; hard actions
   make specific decisions happen. Neither alone is sufficient.
2. **Key plans on titles, not character IDs.** `title:k_france.holder`
   survives succession; character IDs do not. Use character IDs only as a
   fallback for landless targets.
3. **Constrained choices.** Precompute a per-ruler *legal-move menu* and make
   the LLM choose from it (schema-validated). Never let it invent targets.
4. **Close the loop through the save.** Injected effects set variables (plan
   ID, start date); the next parse reads them back so the LLM has memory of its
   own plans and their outcomes.
5. **Limit hard actions per cycle** (one or two per ruler) so rulers still feel
   like AI and behaviour cannot run away.
6. **Mod/version/LLM agnostic.** Modifier names come from a `script_docs` dump
   (a data file, like `reference_data/`); the LLM stays a pluggable callable.

## Two-layer translation

**Soft steering** (continuous, unreliable alone):

- Character modifiers carrying AI personality dials (`ai_boldness`,
  `ai_energy`, `ai_greed`, `ai_vengefulness`, ...) and war dials
  (`ai_war_chance`, `ai_war_cooldown`, ...).
- Pre-define tiers (`ck3llm_aggressive_1` .. `_5`) in a hand-written static mod;
  Python emits only the tier. Apply with `years = 5` so plans self-expire.

**Hard actions** (discrete, deterministic — the game's own effects):

- `start_war`, `add_opinion` (custom modifier), `add_hook`, `create_alliance`,
  `add_truce`, `set_designated_heir`, `add_pressed_claim`.
- Each guarded by in-game triggers so illegal moves silently no-op.

## Delivery routes

| Route | Restart? | Robustness | Notes |
|---|---|---|---|
| Generated mod file | Yes | High | Cleanest. Static `on_action` calls a Python-written scripted effect. |
| Console `effect`/`run` | No | Medium | Near-live; non-Ironman only; **verify `run <file>` behaviour**. |
| Edit gamestate + rezip | Reload | Low | Format-fragile; avoid unless the others fail. |

Recommended: **generated mod first** (deterministic, debuggable), console later
if a live loop is wanted.

## Cadence

- Plans are stamped with a **plan ID + start date** as character variables.
- Recompute roughly **every 5 in-game years**, gated on the plan start date
  (not on the autosave interval), so cadence is self-correcting.
- A **save watcher** can trigger on any save (manual or auto). Application
  still needs a reload on the generated-mod route.

## Feedback loop

The injected effect writes `ck3llm_plan_id` and a start date. The next parse
reads them, so the briefing can say "you have been pursuing this plan since
year X" — giving the LLM memory of its own intent and its results.

## Milestones

- **Milestone 14 — Legal-move menu builder.** Per ruler, compute valid war
  targets (claims/CBs), plausible allies, peace options, and truces.
- **Milestone 15 — Intent contract revision.** Emit title keys (landless
  fallback) and constrained choices drawn from the menu.
- **Milestone 16 — Translation layer.** Intent → modifier tier + guarded hard
  actions, targeting `script_docs`-verified names.
- **Milestone 17 — Static mod + generated script.** Hand-written modifier
  definitions + `on_action`; Python writes the per-cycle `scripted_effect`.
- **Milestone 18 — Feedback loop.** Read plan variables back into the briefing.
- **Milestone 19 — Cadence & save watcher.** 5-year gating and save detection.

## Open items to verify (before building on them)

- **Ironman saves** — confirm they are unparseable (this is a foundational
  constraint; if only checksummed, there may be a path).
- **Modifier names** — run `script_docs` once and target real names for the
  game version.
- **Console `run <file>`** — confirm it reads from a user `run/` folder.
- **`?=` safe-scope and `yearly_global_pulse`** — smoke-test with `debug_log`
  before generating hundreds of effects.
- **Autosave interval options** — whether CK3 can be set to a 5-year autosave.

## Timing (per cycle, measured + estimated)

- Pipeline (unzip, index, graph, reference, relationships, summaries): ~45–50 s.
- LLM for ~105 Tier-1 rulers: ~5–15 min (the bottleneck).
- CK3 load: ~1–2 min.

**Total: ~7–18 minutes**, dominated by the LLM. Fine for a turn-based loop,
not real-time. Optimisations: skip unchanged realms, batch/parallelise LLM
calls, use a smaller model.

## Honest scope statement

This is a **turn-based** integration: the game is paused, a cycle is run, and
the save is reloaded. It does not run live inside a session.