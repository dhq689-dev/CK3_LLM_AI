"""Streaming extractors for characters and titles.

Reads the big sections one entry at a time (never the whole file) and produces
``Character`` / ``Title`` dataclasses, discarding everything not in the field
map.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Iterator

from .indexer import SectionIndex, _brace_delta
from .parser import parse

_ENTRY_RE = re.compile(rb"([A-Za-z0-9_]+)=\s*\{")


@dataclass
class Character:
    id: int
    name: str = ""
    birth: str = ""
    culture: int | None = None
    faith: int | None = None
    dynasty_house: int | None = None
    skills: list[int] = field(default_factory=list)
    traits: list[int] = field(default_factory=list)
    prestige: float = 0.0
    piety: float = 0.0
    gold: float = 0.0
    memories: list[int] = field(default_factory=list)
    primary_spouse: int | None = None
    spouses: list[int] = field(default_factory=list)
    children: list[int] = field(default_factory=list)
    claims: list[int] = field(default_factory=list)
    domain: list[int] = field(default_factory=list)
    strength: int = 0
    levy: int = 0
    power: int = 0
    succession: list[int] = field(default_factory=list)
    government: str | None = None
    realm_capital: int | None = None


@dataclass
class Title:
    id: int
    key: str = ""
    holder: int | None = None
    de_facto_liege: int | None = None
    de_jure_liege: int | None = None
    capital: int | None = None
    heir: list[int] = field(default_factory=list)
    history: dict = field(default_factory=dict)


def _as_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def extract_character(char_id: int, d: dict) -> Character:
    alive = d.get("alive_data") or {}
    landed = d.get("landed_data") or {}
    family = d.get("family_data") or {}

    prestige = (alive.get("prestige") or {}).get("currency", 0.0)
    piety = (alive.get("piety") or {}).get("currency", 0.0)

    claims = alive.get("claim") or []
    if isinstance(claims, dict):
        claims = [claims]
    claim_ids = [c["title"] for c in claims if isinstance(c, dict) and "title" in c]

    return Character(
        id=char_id,
        name=d.get("first_name", ""),
        birth=d.get("birth", ""),
        culture=d.get("culture"),
        faith=d.get("faith"),
        dynasty_house=d.get("dynasty_house"),
        skills=_as_list(d.get("skill")),
        traits=_as_list(d.get("traits")),
        prestige=prestige,
        piety=piety,
        gold=landed.get("balance", 0.0),
        memories=_as_list(alive.get("memories")),
        primary_spouse=family.get("primary_spouse"),
        spouses=_as_list(family.get("spouse")),
        children=_as_list(family.get("child")),
        claims=claim_ids,
        domain=_as_list(landed.get("domain")),
        strength=landed.get("strength", 0),
        levy=landed.get("levy", 0),
        power=landed.get("power", 0),
        succession=_as_list(landed.get("succession")),
        government=landed.get("government"),
        realm_capital=landed.get("realm_capital"),
    )


def extract_title(title_id: int, d: dict) -> Title:
    return Title(
        id=title_id,
        key=d.get("key", ""),
        holder=d.get("holder"),
        de_facto_liege=d.get("de_facto_liege"),
        de_jure_liege=d.get("de_jure_liege"),
        capital=d.get("capital"),
        heir=_as_list(d.get("heir")),
        history=d.get("history") or {},
    )


class SaveReader:
    """Random-access reader over a save, streaming one entry at a time."""

    def __init__(self, path: str):
        self.path = path
        self.index = SectionIndex.build(path)
        self.file_size = os.path.getsize(path)

    def stream_entries(self, section_name: str) -> Iterator[tuple[str, dict]]:
        """Yield ``(key, dict)`` for each entry in a top-level section.

        Entries are identified by a numeric key (character/title/memory IDs)
        at column 0. Sub-blocks such as ``dynamic_templates`` or the nested
        ``landed_titles`` wrapper are skipped.
        """
        section = self.index.get(section_name)
        if section is None:
            return
        start, end = self.index.byte_range(section_name, self.file_size)

        with open(self.path, "rb") as f:
            f.seek(start)
            header = f.readline()
            depth = _brace_delta(header)
            entry_key: str | None = None
            entry_depth: int | None = None
            entry_lines: list[bytes] = []

            for line in f:
                if f.tell() > end:
                    break
                if entry_key is None:
                    m = _ENTRY_RE.match(line)
                    if m and m.group(1).isdigit():
                        entry_key = m.group(1).decode("ascii", "replace")
                        entry_depth = depth
                        entry_lines = [line]
                    depth += _brace_delta(line)
                    if depth <= 0:
                        break
                else:
                    entry_lines.append(line)
                    depth += _brace_delta(line)
                    if depth == entry_depth:
                        text = b"".join(entry_lines).decode("utf-8", "replace")
                        yield entry_key, parse(text)[entry_key]
                        entry_key = None
                        entry_depth = None
                        entry_lines = []

    def characters(self) -> Iterator[Character]:
        for key, d in self.stream_entries("living"):
            yield extract_character(int(key), d)

    def titles(self) -> Iterator[Title]:
        for key, d in self.stream_entries("landed_titles"):
            yield extract_title(int(key), d)
