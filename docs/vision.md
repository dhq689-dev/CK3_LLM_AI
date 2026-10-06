# Vision — CK3 LLM Strategist

## Objective

Replace parts of Crusader Kings III's high-level strategic AI with an
LLM-driven planning layer.

The goal is NOT to replace CK3's mechanics, tactical AI, military pathfinding,
economy simulation, or event system.

The goal IS to create rulers that:

- Form long-term plans
- Pursue coherent ambitions
- Behave consistently with their personality
- React to changing geopolitical conditions
- Produce emergent narratives

The LLM acts as the ruler. CK3 remains the executor.

---

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

The `RealmSnapshot` layer bridges raw game data and the AI-facing summary. It
holds the per-ruler strategic state (primary title, rank, vassals, claims,
wars, succession, strength) and is where most of the game's strategic logic
lives.

**Status of the last two boxes:** the repository currently stops at
"LLM Strategist → 5-Year Strategic Plan". The **AI Weight/Modifier System** and
**CK3 Executes Decisions** stages are *not implemented* — see the Phase 3 plan
in `roadmap.md`.

---

## What We Learned From Save Analysis

The .ck3 save is a ZIP archive containing a plaintext `gamestate` in Paradox's
scripting syntax. No proprietary API appears necessary.

Important top-level sections discovered in `gamestate_1.txt`:

```text
landed_titles = line ~302,142
dynasties     = line ~759,366
living        = line ~1,042,346
wars          = line ~7,206,474
```

Key format corrections (verified against `sample_savedata/gamestate_1.txt`):

- Titles are keyed by **numeric IDs** (`0`, `1`, `2`...), not `c_`/`d_`/`k_`
  keys. The human key is a `key=` field inside the entry.
- `de_facto_liege` / `de_jure_liege` are **title IDs**, not character IDs.
- `holder` is a **character ID**.
- Military/economic strength **is** in the save: `landed_data` inside each
  character (`strength`, `levy`, `power`, `balance`, `domain`, `succession`).
- Claims live in `alive_data.claim`, not a top-level `claim={}`.
- `family_data` holds `primary_spouse` / `spouse` / `child` as character IDs.

The authoritative parser spec is `../parser_implementation.md`.

Verified against two saves (`gamestate_1` = 1.19.0.6, `gamestate_2` = 1.17.0.1):
the extraction fields above are stable across versions. Known drift points
(title display-name location, optional `SAV` header line, some top-level
sections) are documented in `../parser_implementation.md` §0.

**Ironman saves are out of scope** — they are not plaintext, so the parser only
works on non-Ironman games. (See `risk_register.md`.)

---

## Phase 1 MVP Goal

Generate strategic plans for major AI rulers. No game integration required.

Input: `gamestate`. Output (intent):

```json
{
  "goal": "Expand into Antioch",
  "focus": "Diplomacy",
  "aggression": 6,
  "secondary_goal": "Secure succession"
}
```

---

## Rulers To Analyse

Do NOT run LLMs for all characters. Use a tiered system.

- **Tier 1** (always LLM-controlled): emperors, kings. Expected 20–60.
- **Tier 2** (conditional): powerful dukes, important republics, major clan
  rulers. Expected 50–150.
- **Tier 3** (vanilla AI): counts, barons, courtiers, knights.

---

## Data To Extract

### Character Data (`living={}`)

```json
{
  "id": "...", "name": "...", "birth": "...",
  "culture": "...", "faith": "...", "dynasty_house": "...",
  "skills": [], "traits": [],
  "prestige": 0, "piety": 0, "gold": 0
}
```

`prestige` and `piety` live in `alive_data` (as `currency`); `gold` is
`landed_data.balance`. These drive strategy more strongly than skill scores.

### Family Data (`family_data={}`)

```json
{ "primary_spouse": "...", "spouses": [], "children": [] }
```

Purpose: succession planning, marriage strategy, dynasty expansion, stability.

### Memories (`character_memory_manager={}`)

Each character's `alive_data.memories` holds a list of memory IDs; the detail
lives in `character_memory_manager`:

```text
16778116={
    type=became_friends
    participants={ new_relation=43344 }
    creation_date=883.9.1
    end_date=1013.9.1
}
```

Purpose (Phase 2+): historical grudges, rivalries, relationships, diplomacy.

### Titles (`landed_titles={}`)

```json
{ "id": 0, "key": "d_swabia", "holder": 12345,
  "de_facto_liege": 678, "de_jure_liege": 678,
  "capital": 1234, "heirs": [] }
```

Titles are keyed by numeric ID; `key=` holds the human key. Claims are NOT
stored here — they live in the character's `alive_data.claim`.

### Realm Structure (derived)

```json
{ "realm_size": "...", "counties": 0, "duchies": 0, "kingdoms": 0,
  "rank": "count/duke/king/emperor", "independent": true }
```

### Political Hierarchy (derived)

Use `de_facto_liege` + `holder` to reconstruct Empire → Kingdom → Duchy →
County. Purpose: find vassals, lieges, neighbours, and realm power.

### Claims (`alive_data.claim`)

```text
alive_data={ claim={ { title=3238 } } }
```

Purpose: expansion opportunities, strategic objectives, border conflict.

### Succession (`heir={}` + `family_data={}`)

```json
{ "succession_stability": "...", "heir_count": 0, "primary_heir": "..." }
```

### Dynasties (`dynasties={}`)

```json
{ "dynasty_name": "...", "prestige": "...", "renown": "..." }
```

(Optional in MVP.)

### Wars (`wars={}`)

```json
{ "war_type": "...", "attacker": "...", "defender": "...",
  "war_score": "...", "date_started": "..." }
```

Purpose: threat assessment, opportunity detection, strategic planning.

---

## Data NOT Sent To The LLM

Ignore: DNA, portrait data, hair, facial genes, clothing, graphics metadata,
coat of arms, visual customisation. These are irrelevant for strategy.

---

## Intermediate Representation

The parser does NOT pass raw save data to the model. Instead it generates a
strategic briefing:

```json
{
  "name": "King of England",
  "primary_title": "Kingdom of England",
  "traits": ["ambitious", "wrathful"],
  "realm": { "size": "large", "military_power": "strong", "economic_power": "average" },
  "succession": { "stable": true },
  "threats": [ { "ruler": "Scotland", "power_ratio": 1.4 } ],
  "opportunities": ["Claim on Wales"]
}
```

---

## LLM Output Format

The LLM does NOT issue actions. It issues intent:

```json
{
  "five_year_goal": "Unify Britannia",
  "focus": "Military",
  "aggression": 8,
  "secondary_goal": "Secure succession"
}
```

---

## Future Work (beyond Phase 3)

- AI diplomacy chat
- Player conversations with rulers
- Multi-agent courts
- Council simulations

---

## Current Conclusion

The save format is fully capable of supporting an LLM strategist layer. The
most important extraction targets are:

1. Characters
2. Titles
3. Claims
4. Heirs
5. Dynasties
6. Wars
7. Liege/Vassal hierarchy

These are sufficient to build a ruler-centric strategic planner without
modifying CK3 itself.
