# Reference data

ID→name lookup tables for traits, cultures, faiths, and dynasty houses.

These mappings are **extracted from the save itself** at runtime (see
`ck3_strategist/reference.py`), not shipped as static files:

- `traits_lookup`            → trait ID → key
- `culture_manager.cultures` → culture ID → `culture_template`
- `religion.faiths`          → faith ID → `faith_type`
- `dynasties.dynasty_house`  → house ID → `name`

This keeps the parser self-contained and version-proof (the mappings live in
the save, so they never drift from the game data).

This directory is reserved for any future static tables (e.g. title-key →
display-name localization) that cannot be sourced from the save.
