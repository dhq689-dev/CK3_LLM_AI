# CK3 LLM Strategist: Review Recommendations

Repository: https://github.com/dhq689-dev/CK3_LLM_AI
Reviewed at: commit `574fe75` ("Add memory extractor (Milestone 10)")
Method: cloned the repo, read all source, ran the tests (57 passing), probed suspected bugs with small scripts, and benchmarked snapshot building on synthetic data. I did **not** run anything against a real CK3 save.

---

## 1. Overall assessment

A well-structured Phase 1 with a clean layered design: lexer, parser, section indexer, extractors, world graph, snapshot, summary, and a pluggable LLM layer. The "parser → JSON → LLM" boundary is the right call and keeps everything before the LLM deterministic and testable. Code is readable, typed, and has per-module tests.

The main gaps are at the edges of the pipeline: nothing connects a real save to the strategist, the LLM layer is the least robust part, and several extraction and performance issues will show up on real saves. Phase 2 has started while these Phase 1 gaps are still open.

---

## 2. Prioritised action list

Each item is marked **[open]** (confirmed in the current code). Tick them off as you go.

### Priority 1: Make the pipeline usable end to end

- [ ] **Add a CLI / pipeline entry point.** There is no `argparse`, `__main__`, or orchestration code. Build a `cli.py` that extracts the gamestate, builds the graph, snapshots, summaries, runs the strategist, and writes JSON. Add an end-to-end test using your real save (or a trimmed version of it).
- [ ] **Handle ZIP saves.** The README says a `.ck3` save is a ZIP containing `gamestate`, but `SaveReader` only accepts a path to a plaintext file and no code uses `zipfile`. Extract to a temp file (or stream) as part of the CLI.

### Priority 2: Harden the LLM layer

This matters more with Milestone 13 (negotiations) about to depend on it.

- [ ] **Validate `focus`.** `_FOCUS_VALUES` is defined in `strategist.py` but never used, so `focus: "Conquest"` passes as valid. Reject or default invalid values.
- [ ] **Handle non-numeric `aggression`.** `aggression: "high"` raises a raw `ValueError` from `int()`. Raise a clean parse error or fall back to a clamped default.
- [ ] **Make `ollama_call` robust.** It has no timeout, no error handling, and no retry, so a hung local model blocks forever. Add a timeout and consider Ollama's `"format": "json"` option.
- [ ] **Add retry-on-bad-output.** On a parse or validation failure, retry with the error fed back into the prompt. Local models fail format constraints fairly often.
- [ ] **For `negotiations` (Milestone 13): use character IDs, not names.** Supply IDs in the prompt and require IDs back. Matching free text like "King of France" against the graph will be fragile, and ID validation gives you the check your Milestone 13 "Verify" step describes.

### Priority 3: Fix extraction robustness

- [ ] **Per-entry error handling in `memories()` (and ideally all streams).** `extract_memory` assumes `participants` is a dict. `participants={ 1 2 3 }` raises `AttributeError` and aborts the entire generator. Wrap per-entry extraction, skip bad entries, and count/log them.
- [ ] **Stop dropping repeated participant keys.** `participants={ witness=10 witness=11 victim=5 }` becomes `{'victim': 5}` because repeated keys become a list and the `isinstance(v, int)` filter discards it. Store `dict[str, list[int]]`, or at least keep the ints from lists.
- [ ] **Depth-gate entry matching in `stream_entries`.** The new `line.lstrip()` is needed to reach entries under `database={`, but matching is no longer depth-gated, so a numeric-keyed block nested in any non-entry sub-block could be yielded as an entry. In a synthetic test this returned a spurious `Title`. Whether real saves have such blocks is unverified, so treat it as a risk to check. Fix by passing an expected entry depth per section (e.g. 2 for `character_memory_manager`).
- [ ] **Avoid copying every line.** `lstrip()` copies each line of a ~170MB file. Use a regex such as `rb"\s*(\d+)=\s*\{"` instead.
- [ ] **Fix the parser's repeated-key ambiguity.** If a key repeats and its first value is itself a list, later values are appended into it: `a={ x={1 2} x={3 4} }` gives `x: [1, 2, [3, 4]]` instead of `[[1, 2], [3, 4]]`. Track whether a key has already been promoted to a multi-value list.
- [ ] **Decide on `#` comment support.** `a=1 # note` raises `ParseError`. Likely fine for raw saves, but needed if you ever parse game files from `common/`.

### Priority 4: Performance

- [ ] **Index titles by holder.** `WorldGraph.primary_title()` scans every title on every call, and `build_snapshots` calls it (directly and via `get_vassals` / `get_realm_titles`) for every living character. Benchmarked on synthetic data: 2,000 characters × 2,000 titles took 0.37s; 4,000 × 4,000 took 1.22s (~3.3× for 2× the size, i.e. quadratic). Extrapolated, a real save would take tens of seconds to minutes. Build a `holder_id → [titles]` index once in `WorldGraph.__init__`.
- [ ] **Avoid whole-section reads for big sections.** `dynamic_templates()` and `dynasties()` use `read_section`, which loads and tokenizes an entire section into memory. This contradicts the "never load the whole save" principle for `landed_titles` and `dynasties`.
- [ ] **Consider a lazy tokenizer.** `list(tokenize(...))` materialises all tokens. Fine per entry, a weak point for large sections.

### Priority 5: Correctness of summaries

- [ ] **Fix the `None` trait crash.** `ReferenceData.trait_name()` returns `None` for unknown IDs; `build_summary` puts that in the traits list and `", ".join(...)` in `build_prompt` raises `TypeError`. Filter out `None` or fall back to `f"trait_{id}"`. Mods and DLC make unknown IDs plausible.
- [ ] **Replace the `assert` token-budget check.** `build_summaries` uses `assert`, which disappears under `python -O` and aborts the whole batch when one ruler exceeds the budget. Truncate lower-priority fields (e.g. cap opportunities) and log instead. This matters more once Milestone 12 adds a relationships block.
- [ ] **Review weak derived values.**
  - `succession_stability` is just `"stable" if succession else "unstable"`.
  - `compute_age` subtracts years only, so it can be off by one.
  - `Dynasty.renown` is hardcoded to `0.0`.
  - Threats come only from active wars where the ruler is the war leader.
  - Percentile bucketing sends ties (e.g. many rulers with 0 gold) all to "weak".

  Fine as Phase 1 placeholders, but rename or document them so the LLM isn't told something misleading.

---

## 3. Phase 2 (memory / relationships / negotiation) recommendations

The `agents.md` design is sound: relationship direction is read from participant keys, a configurable mapping file drives the structured graph, and raw memories are also passed to the LLM. Additional suggestions:

- [ ] **Add memory ownership.** Milestone 10 says "link each memory to its owner", but `Memory` has no owner field and nothing links it. Build a `memory_owner: dict[int, int]` from `Character.memories`. Milestone 11 needs this because `participants={ rival=2300 }` means nothing without knowing whose memory it is.
- [ ] **Respect `end_date`.** It is extracted but unused. Filter relationships by `end_date` against `meta_date()` so the LLM isn't given expired grudges.
- [ ] **Sync the docs.** The `Memory` dataclass in `agents.md` omits `end_date`, which the code has.
- [ ] **Milestone 11 (relationship graph).** Write the mapping JSON and the builder with tests that include unknown memory types. A mod-added type should degrade to "ignored by the graph, still visible in the raw memories".
- [ ] **Missing piece to schedule.** The README diagram ends at "AI Weight/Modifier System → CK3 Executes Decisions", but there is no mod/script side in the repo. It is the hardest part of the project and deserves its own milestone and an honest status line.

---

## 4. Documentation and repository hygiene

- [ ] Move `review_notes.md` to `docs/` or remove it. It is an AI-written review scoring the spec "9/10 readiness", which reads oddly to outsiders.
- [ ] Consider renaming `agents.md`; the name suggests it configures coding agents rather than documenting the project vision.
- [ ] Add a short example of the `StrategicSummary` JSON and the intent output to the README. It is the heart of the idea.
- [ ] Add a license, a repo description, and topics.
- [ ] Add CI running `pytest`, plus ruff and mypy (the `.gitignore` already anticipates them).

---

## 5. Suggested order of work

1. CLI and ZIP handling, plus an end-to-end run on a real save.
2. Index titles by holder (removes the quadratic behaviour).
3. Harden `parse_intent` and `ollama_call` (validation, timeout, retry).
4. Extraction robustness fixes (per-entry error handling, repeated keys, depth-gated matching), each with a regression test.
5. Fix the `None`-trait crash and the `assert` budget check.
6. Then continue Phase 2: memory ownership, relationship mapping and graph, relationship summary, negotiations with ID-based targets.

---

## 6. Caveats

- All findings come from reading the code and running small probes; nothing was verified against a real save.
- The performance figures are extrapolations from synthetic data and will differ on real saves, but the quadratic scaling is clear from the code.
- The `stream_entries` depth issue is a risk identified with a synthetic case, not a confirmed regression on real data.