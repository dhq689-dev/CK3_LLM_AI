"""Section indexer for the CK3 save.

Scans the file once, streaming, and records the byte offset and line number of
every top-level ``key={`` section. A section is "top-level" only when it sits
at brace depth 0 — the save puts some entries (e.g. title IDs in
``landed_titles``) at column 0 too, so column position alone is not enough.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Matches a section header: ``name={`` at the start of a line.
_SECTION_RE = re.compile(rb"([A-Za-z0-9_]+)=\s*\{")


@dataclass(frozen=True)
class Section:
    name: str
    line: int
    byte_offset: int


class SectionIndex:
    def __init__(self, sections: list[Section]):
        self._by_name = {s.name: s for s in sections}
        self._ordered = sorted(sections, key=lambda s: s.byte_offset)

    @classmethod
    def build(cls, path: str) -> SectionIndex:
        sections: list[Section] = []
        depth = 0
        with open(path, "rb") as f:
            offset = 0
            for line_no, line in enumerate(f, start=1):
                if depth == 0 and line and line[0] in _FIRST_BYTE_OK:
                    m = _SECTION_RE.match(line)
                    if m:
                        name = m.group(1).decode("ascii", "replace")
                        sections.append(Section(name, line_no, offset))
                depth += _brace_delta(line)
                offset += len(line)
        return cls(sections)

    def get(self, name: str) -> Section | None:
        return self._by_name.get(name)

    def __contains__(self, name: str) -> bool:
        return name in self._by_name

    def byte_range(self, name: str, file_size: int) -> tuple[int, int]:
        """Return the (start, end) byte range of a section.

        ``end`` is the byte offset of the next top-level section, or
        ``file_size`` for the last section.
        """
        s = self._by_name[name]
        start = s.byte_offset
        end = file_size
        for other in self._ordered:
            if other.byte_offset > start:
                end = other.byte_offset
                break
        return start, end


def _brace_delta(line: bytes) -> int:
    """Net ``{`` minus ``}`` on a line, ignoring braces inside quotes."""
    delta = 0
    in_quote = False
    for b in line:
        if b == 0x22:  # '"'
            in_quote = not in_quote
        elif not in_quote:
            if b == 0x7B:  # '{'
                delta += 1
            elif b == 0x7D:  # '}'
                delta -= 1
    return delta


# Bytes that may begin a top-level section name (fast pre-filter).
_FIRST_BYTE_OK = frozenset(
    b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_"
)
