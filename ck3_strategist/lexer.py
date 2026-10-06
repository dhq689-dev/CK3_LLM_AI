"""Byte-safe tokenizer for the Paradox scripting grammar.

The CK3 save is not clean UTF-8, so callers should decode bytes with
``errors="replace"`` before tokenizing. This module operates on the decoded
string and yields a flat token stream.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

# Token kinds
LBRACE = "LBRACE"
RBRACE = "RBRACE"
EQUALS = "EQUALS"
STRING = "STRING"
BARE = "BARE"

# Characters that terminate a bare (unquoted) token.
_BARE_STOP = set("{} =\"\t\r\n")


@dataclass(frozen=True)
class Token:
    kind: str
    value: str
    pos: int


def tokenize(text: str) -> Iterator[Token]:
    """Yield tokens from ``text``.

    Whitespace is skipped. ``{``, ``}``, ``=`` are single-character tokens.
    ``"..."`` is a quoted string (no escape handling; the save does not use
    escaped quotes). Anything else is a bare token terminated by whitespace or
    one of ``{ } = "``.
    """
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c.isspace():
            i += 1
            continue
        if c == "{":
            yield Token(LBRACE, "{", i)
            i += 1
            continue
        if c == "}":
            yield Token(RBRACE, "}", i)
            i += 1
            continue
        if c == "=":
            yield Token(EQUALS, "=", i)
            i += 1
            continue
        if c == '"':
            j = i + 1
            while j < n and text[j] != '"':
                j += 1
            yield Token(STRING, text[i + 1 : j], i)
            i = j + 1
            continue
        # bare token
        j = i
        while j < n and text[j] not in _BARE_STOP:
            j += 1
        yield Token(BARE, text[i:j], i)
        i = j
