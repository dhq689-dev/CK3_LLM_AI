# Parser Implementation Plan

## 0. Corrections to the original spec (from real save analysis)

The original data model was directionally right but several assumptions were
wrong against the actual `gamestate_1.txt`. These are fixed here.

| Spec assumption | Reality |
|---|---|
| Titles keyed by `c_colmar`, `d_swabia` | Titles keyed by **numeric IDs** (`0`, `1`, `2`...). The human key is a `key=` field *inside* the entry (`key=d_laamp_RICE_gung_ye`). |
| `de_facto_liege` / `de_jure_liege` are character IDs | They are **title IDs** (small ints), pointing at the liege *title*, not the liege *character*. |
| `holder` is a title key | `holder` is a **character ID** (large int). |
| Military/economic strength "not in save" | It **is** in the save: `landed_data` block inside each character entry (`strength`, `levy`, `power`, `balance`, `domain`, `succession`). |
| `heir={}` | `heir={ 16796577 }` — a list of character IDs (succession order). |
| `claim={}` | Claims live in `alive_data` as `claim={ { title=3238 } }`. |
| `family_data={}` | Contains `primary_spouse=`, `spouse=`, `child={ ... }` (all character IDs). |

### Actual section line offsets (gamestate_1.txt, 11.4M lines)

```
landed_titles={   line   302,142
dynasties={       line   759,366
living={          line 1,042,346
wars={            line 7,206,474
character_memory_manager={  line 8,549,187
```

Note: `living` and `characters` are adjacent; `wars` is far later than the
spec's guess. The `Section Indexer` must locate these at runtime, not hardcode.

**Column-0 quirk:** title entries (`0={`, `1={`...) and character entries
(`16801936={`...) sit at column 0, *not* indented, inside their parent
sections. The indexer therefore cannot rely on column position alone — it must
track brace depth and only record a `key={` as top-level when depth is 0.
`houses` is *not* top-level (it is nested inside `dynasties`).

### Version-proofing (verified against 1.17.0.1 and 1.19.0.6)

The fields we extract are stable across versions:

- Title keying (numeric ID + `key=`), `de_facto_liege`/`de_jure_liege` as
  title IDs, `holder` as char ID.
- `landed_data` (`strength`, `levy`, `power`, `balance`, `domain`,
  `succession`, `government`).
- `alive_data.claim` nested `{ title=... }` (1.17 adds optional `pressed=yes`).
- `family_data` (`primary_spouse`/`spouse`/`child`; 1.17 adds optional
  `former_spouses`).
- `skill` (6 values), `traits`, `prestige`/`piety` in `alive_data`,
  `memories` list, `character_memory_manager` with `database={}` wrapper.

Known drift points (do NOT rely on these):

- **Title display name** — 1.17 stores `name=`/`article=` at title top-level;
  1.19 nests them in `title_name_data={}`. Source display names from
  `reference_data/`, not the save.
- **Optional `SAV` header line** — 1.19 starts with `SAV0102...`; 1.17 starts
  directly with `meta_data={`. The parser must tolerate an optional first line.
- **Top-level sections appear/disappear** — `title_history`, `activities`,
  `combat`, `province_manager`, `player_heir`, `held_titles` are absent in
  1.17. None are used in MVP, but this confirms the "never hardcode a closed
  set of keys" rule.

---

## 1. Grammar (Paradox scripting syntax)

The file is a sequence of top-level `key=value` or `key={...}` assignments.
Values are one of: scalar, quoted string, list, or block.

```ebnf
document   := { assignment } ;
assignment := key "=" value ;
key        := identifier ;            (* [A-Za-z0-9_]+ *)
value      := scalar | string | list | block ;
scalar     := number | identifier | date | bool ;
string     := '"' { any } '"' ;
list       := "{" { scalar } "}" ;   (* space-separated scalars *)
block      := "{" { assignment } "}" ;
date       := number "." number "." number ;   (* e.g. 918.11.5 *)
bool       := "yes" | "no" ;
```

### Lexer rules (the parts that actually bite)

1. **Whitespace is insignificant** except as a scalar separator inside lists.
2. **`{` and `}` delimit blocks and lists.** There is no distinction between
   them syntactically — you decide by context (a block has `key=value` inside;
   a list has bare scalars).
3. **Quoted strings** may contain `{`, `}`, `=`, spaces, and non-UTF8 bytes
   (the file is not clean UTF-8 — see the `V�?l��` mojibake in `meta_player_name`).
   Read as bytes and decode with `errors="replace"`.
4. **Lists can be empty** (`treasury={ }`) or contain a single scalar
   (`heir={ 16796577 }`).
5. **Nested anonymous blocks** appear as `{ { ... } { ... } }` (e.g.
   `variables={ data={ { flag=... } { flag=... } } }`). The parser must handle
   a block whose first token is `{`.
6. **Dates** are `Y.M.D` with no leading zeros (`918.11.5`). Store as string;
   convert to a comparable integer `Y*10000 + M*100 + D` when needed.

### Recommended parser approach

A **single-pass recursive-descent parser** over a token stream, with a
**line-offset index** for random access into the four big sections. Do NOT
build a full AST of the whole 11M-line file — that will exhaust memory.

Before writing the parser, skim existing Paradox save parsers (the community's
CK3/EU4 parsers) for grammar references and edge cases. The custom parser is
still expected, but this reduces re-discovering quirks.

Two modes:

- **Streaming mode** for `living` and `landed_titles`: parse one top-level
  entry at a time, extract only the fields you need, discard the rest.
- **Indexed mode** for `wars` and `dynasties`: seek to the section, parse.

---

## 2. Extraction targets (concrete field map)

### Character (`living={ charid={ ... } }`)

| Field | Save key | Type | Notes |
|---|---|---|---|
| id | block key | int | e.g. `16801936` |
| name | `first_name` | str | |
| birth | `birth` | date | |
| culture | `culture` | int | ID → lookup table |
| faith | `faith` | int | ID → lookup table |
| dynasty_house | `dynasty_house` | int | ID → house |
| skills | `skill={ d m s i l p }` | list[6] | diplomacy, martial, stewardship, intrigue, learning, prowess |
| traits | `traits={ ... }` | list[int] | ID → lookup table |
| prestige | `alive_data.prestige.currency` | float | |
| piety | `alive_data.piety.currency` | float | |
| gold | `landed_data.balance` | float | |
| memories | `alive_data.memories` | list[int] | memory IDs → `character_memory_manager` |
| primary_spouse | `family_data.primary_spouse` | int | |
| spouses | `family_data.spouse` | list[int] | |
| children | `family_data.child` | list[int] | |
| claims | `alive_data.claim` | list[{title}] | `claim={ { title=3238 } }` |
| domain | `landed_data.domain` | list[int] | title IDs held directly |
| strength | `landed_data.strength` | int | military strength |
| levy | `landed_data.levy` | int | |
| power | `landed_data.power` | int | |
| balance | `landed_data.balance` | float | gold |
| succession | `landed_data.succession` | list[int] | heir order |
| government | `landed_data.government` | str | |
| realm_capital | `landed_data.realm_capital` | int | province ID |

### Title (`landed_titles={ titleid={ ... } }`)

| Field | Save key | Type |
|---|---|---|
| id | block key | int |
| key | `key` | str (e.g. `d_swabia`) |
| holder | `holder` | int (char ID) |
| de_facto_liege | `de_facto_liege` | int (title ID) |
| de_jure_liege | `de_jure_liege` | int (title ID) |
| capital | `capital` | int (province ID) |
| heir | `heir` | list[int] |
| history | `history` | map[date → charid] |

Note: display name is NOT reliably in the save (moves between `name=` and
`title_name_data.name` across versions). Resolve `key` → display name via
`reference_data/` instead.

### War (`wars={ active_wars={ warid={ ... } } }`)

| Field | Save key | Type |
|---|---|---|
| id | block key | int |
| war_type | `casus_belli.type` | str |
| attacker | `casus_belli.attacker` | int (char ID) |
| defender | `casus_belli.defender` | int (char ID) |
| targeted_titles | `casus_belli.targeted_titles` | list[int] |
| start_date | `start_date` | date |
| participants | `attacker/defender.participants` | list[{character, date}] |

### Dynasty (`dynasties={ dynid={ ... } }`)

| Field | Save key | Type |
|---|---|---|
| id | block key | int |
| name | `name` | str (localization key) |
| prestige | `prestige` | int (may be absent) |
| renown | `renown` | int (may be absent) |

### Memory (`character_memory_manager={ memid={ ... } }`)

| Field | Save key | Type |
|---|---|---|
| id | block key | int |
| type | `type` | str (e.g. `became_friends`) |
| participants | `participants` | map[str → int] (e.g. `new_relation=43344`) |
| creation_date | `creation_date` | date |
| end_date | `end_date` | date |

Extracted in Phase 1, consumed in Phase 2+ (grudges, rivalries, diplomacy).

---

## 3. Derived-value logic (the under-specified parts)

### 3.0 RealmSnapshot (the bridge layer)

Between `WorldGraph` and `StrategicSummary`, build a per-ruler
`RealmSnapshot` holding the strategic state that the summary builder consumes:

```python
class RealmSnapshot:
    primary_title_id: int
    primary_title_name: str
    rank: str            # count/duke/king/emperor
    independent: bool
    vassals: list[int]
    claims: list[int]
    wars: list[int]
    succession: list[int]
    strength: int
    power_ratio: float   # vs strongest neighbour/threat
```

This is where most of the game's strategic logic lives; `StrategicSummary` is
a thin projection of it into the LLM-facing JSON.

### 3.1 Realm reconstruction

For each significant ruler, walk the title graph:

1. Find the ruler's **primary title** = highest-rank title they hold
   (`holder == charid`), preferring `e_` > `k_` > `d_` > `c_`.
2. **Realm titles** = all titles whose `de_facto_liege` chain terminates at the
   ruler's primary title (transitive closure over `de_facto_liege`).
3. **Vassals** = distinct `holder` character IDs of realm titles (excluding the
   ruler).
4. **Independent** = primary title has no `de_facto_liege`.

Rank is derived from the primary title's `key` prefix (`c_`/`d_`/`k_`/`e_`).

### 3.2 Military strength

Do NOT invent a formula. Use the save's own `landed_data.strength` (or
`power`) for the ruler, and sum `strength` over vassals for realm strength.
Bucket into `weak`/`average`/`strong` by percentile across all Tier-1 rulers
(relative, not absolute — a "strong" duke in 918 is not a "strong" emperor).

### 3.3 Economic strength

Use `landed_data.balance` (gold) plus realm size. Bucket similarly. This is
coarse but sufficient for MVP; refine later with development/holdings.

### 3.4 Neighbours

There is **no adjacency data in the save**. Two options:

- **MVP (recommended):** derive "neighbours" as *realm-level* adjacency —
  rulers whose realm titles share a `de_jure_liege` boundary, or who border via
  county `de_jure` structure. Approximate: any independent ruler whose realm
  is within the same de-jure kingdom/empire, plus any ruler with an active war
  or claim against you.
- **Later:** load a static province-adjacency table (from the game's map data)
  and map `capital`/`domain` province IDs to it.

For Phase 1, "threats" and "opportunities" can be built from **claims + active
wars + shared de-jure liege** without true geographic adjacency. Each threat
carries a `power_ratio` (threat realm strength / own realm strength) — relative
power is one of the most important strategic indicators for the LLM.

### 3.5 Succession stability

From `landed_data.succession` (heir order) and `family_data.child`:
- `stable` = primary heir exists and is an adult of the same dynasty.
- `unstable` = no heir, or heir is a child / different dynasty / female under
  male-preference law.

---

## 4. Reference data (missing from spec, required)

The save stores numeric IDs for traits, skills, culture, faith, houses. You
need static lookup tables to map them to human-readable names. Sources:

- Trait IDs → names: from the game's `common/traits` definitions (or a
  community dump).
- Culture/faith IDs → names: from `common/culture` / `common/religion`.
- Title keys → display names: from `common/landed_titles` localization.

Ship these as JSON files in `reference_data/`. Without them, the LLM sees
`traits=[63 59 55 3]` instead of `[ambitious, wrathful, ...]`, which defeats
the purpose.

---

## 5. Implementation order (concrete milestones)

1. **Lexer + recursive-descent parser** (streaming, byte-safe). Unit-test
   against a small hand-written fixture first, then the real file.
2. **Section indexer** — locate `landed_titles`, `dynasties`, `living`, `wars`,
   `character_memory_manager` by scanning for `^key={` at column 0.
3. **Character + Title extractors** — streaming, field-map only, including
   prestige/piety/gold and raw memory IDs.
4. **Reference-data loader** — trait/culture/faith/title-name tables.
5. **WorldGraph** — `get_ruler`, `get_vassals`, `get_liege`, `get_realm_titles`.
6. **RealmSnapshot + derived values** — realm reconstruction, strength
   bucketing, succession, threats with `power_ratio` (section 3).
7. **Significant-ruler detection** (Tier 1/2 rules).
8. **StrategicSummary builder** → JSON, assert `<5k tokens`.
9. **LLM strategist** (separate layer, consumes summaries only).

---

## 6. Risks to watch

- **Memory:** 11.4M lines / 170MB. Never `read()` the whole file into a Python
  string for parsing; stream line-by-line or mmap. The `Section Indexer` is
  mandatory.
- **Encoding:** file is not clean UTF-8. Decode bytes with `errors="replace"`.
- **Modded content:** this save has RICE/EP3 mods (`d_laamp_RICE_*`,
  `ep3_laamp_*`). The parser must tolerate unknown keys and unknown title
  prefixes — never hardcode a closed set of keys.
- **`de_facto_liege` vs `de_jure_liege`:** use `de_facto` for realm
  reconstruction (actual politics), `de_jure` only for claims/expansion logic.
