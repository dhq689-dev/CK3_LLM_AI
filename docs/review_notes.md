# REVIEW_NOTES.md

# Review of Updated CK3 LLM Strategist Specification

## Overall Assessment

The revised specification represents a major improvement over the original concept.

The project has evolved from:

```text
Interesting architectural idea
```

to:

```text
Executable engineering plan
```

Key strengths:

- Corrected several important assumptions discovered during save-file analysis.
- Clear separation between parser, world model, and LLM.
- Milestone-driven implementation plan.
- Explicit verification criteria.
- Scalable approach for processing large saves.
- LLM-independent parser layer.

Overall readiness is now very high.

---

# Major Improvements

## Correct Data Model

Several critical discoveries have been incorporated into the specification:

### Title Storage

Titles are not keyed by:

```text
c_swabia
d_swabia
k_france
```

Instead:

```text
0={
    key=d_swabia
}
```

The title ID is numeric and the title key is stored within the entry.

This correction prevents a major implementation mistake.

---

### Liege Relationships

The specification now correctly identifies:

```text
de_facto_liege
de_jure_liege
```

as title IDs rather than character IDs.

This is essential for constructing the realm hierarchy correctly.

---

### Claims

Claims are now correctly sourced from:

```text
alive_data.claim
```

rather than from title records.

This simplifies exploitation and expansion analysis.

---

### Military and Economic Data

The discovery that:

```text
landed_data
```

already contains metrics such as:

- strength
- levy
- power
- balance
- succession
- domain

means the parser can use CK3's own calculations rather than recreating them.

---

# Strong Architectural Decisions

## LLM-Agnostic Parser

One of the strongest principles in the design is:

```text
Parser → JSON → LLM
```

rather than:

```text
Parser → LLM
```

Everything before StrategicSummary should be:

- deterministic
- testable
- reproducible
- independent of AI models

This will greatly simplify debugging.

---

## Incremental Milestone Structure

The milestone plan is excellent.

Particularly valuable:

```text
Milestone 1
Parser

Milestone 2
Section Indexing

Milestone 3
Character & Title Extraction

Milestone 4
Reference Resolution

Milestone 5
WorldGraph

Milestone 6
Derived Values

Milestone 7
Ruler Selection

Milestone 8
Strategic Summaries

Milestone 9
LLM Integration
```

This minimises risk and allows validation at every stage.

---

## Streaming Architecture

The requirement:

```text
Never load the entire 170MB save into memory.
```

is an excellent design choice.

The save format is large enough that:

- mmap
- streaming
- indexed access

are preferable.

This keeps the parser scalable.

---

# Recommended Enhancements

## 1. Add Explicit Primary Title

Recommend adding:

```python
primary_title_id
primary_title_name
```

to the core ruler model.

This information will be required repeatedly by:

- StrategicSummary generation
- Realm reconstruction
- LLM prompting

and should not be recomputed constantly.

---

## 2. Add Prestige, Piety and Gold

Recommend extracting:

```python
prestige
piety
gold
```

if available.

CK3 rulers frequently make decisions around:

- legitimacy
- religious authority
- available resources

These values often drive strategy more strongly than skill scores.

---

## 3. Add Memory Extraction Earlier

Originally memories were considered a Phase 2 feature.

Recommendation:

```text
Extract memories during Phase 1
Use them later
```

Potential structure:

```python
class CharacterMemory:
    type: str
    participants: list[int]
    creation_date: date
```

This provides future support for:

- grudges
- rivalries
- historical motivations
- diplomacy systems

without revisiting parser architecture later.

---

## 4. Realm Power Comparison

Current threat analysis focuses on:

- claims
- wars
- hierarchy

It would be useful to incorporate:

```python
power_ratio
```

Example:

```json
{
  "threat": "Byzantine Empire",
  "power_ratio": 8.3
}
```

Relative power may be one of the most important strategic indicators.

---

## 5. Add RealmSnapshot Layer

Current architecture:

```text
WorldGraph
    ↓
StrategicSummary
```

Recommended:

```text
WorldGraph
    ↓
RealmSnapshot
    ↓
StrategicSummary
```

Suggested structure:

```python
class RealmSnapshot:
    primary_title
    rank
    vassals
    claims
    wars
    succession
    strength
```

This becomes the bridge between:

- raw game data
- AI-facing summaries

and will likely contain most of the game's strategic logic.

---

# Parser Considerations

Before implementing a custom recursive-descent parser:

```text
Milestone 1
```

it may be worth reviewing existing Paradox save parsers for:

- grammar references
- edge cases
- format quirks

The custom solution is still likely appropriate, but existing projects can reduce development time.

---

# Final Conclusion

The current specification is now very close to implementation-ready.

Strengths:

- Correct save-file understanding
- Robust data model
- Clean parser/AI separation
- Strong milestone structure
- Verification-driven development
- Scalable handling of large saves

The only major architectural addition recommended is:

```text
WorldGraph
    ↓
RealmSnapshot
    ↓
StrategicSummary
```

alongside optional extraction of:

- prestige
- piety
- gold
- memories

These enhancements would further strengthen the strategic reasoning layer without altering the overall architecture.

Current assessment:

```text
Original concept:        6/10 readiness
Current specification:  9/10 readiness
```

The project now has a realistic path from save file to AI-generated strategic plans.
