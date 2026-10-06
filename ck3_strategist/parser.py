"""Recursive-descent parser for the Paradox scripting grammar.

Produces a nested Python structure:

- block  ``{ key=value ... }``  -> ``dict``
- list   ``{ scalar scalar }``  -> ``list``
- list of blocks ``{ { ... } { ... } }`` -> ``list`` of ``dict``
- scalar -> ``int`` / ``float`` / ``bool`` / ``str`` (dates stay ``str``)

The empty ``{ }`` is ambiguous (empty block vs empty list); it is returned as
an empty ``dict``. Extraction code treats both uniformly.
"""

from __future__ import annotations

from typing import Any

from .lexer import BARE, EQUALS, LBRACE, RBRACE, STRING, Token, tokenize


class ParseError(Exception):
    def __init__(self, message: str, pos: int | None = None):
        super().__init__(message)
        self.pos = pos


def _coerce(value: str) -> Any:
    if value == "yes":
        return True
    if value == "no":
        return False
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value


class Parser:
    def __init__(self, text: str):
        self._tokens = list(tokenize(text))
        self._pos = 0

    def _peek(self, offset: int = 0) -> Token | None:
        idx = self._pos + offset
        if idx < len(self._tokens):
            return self._tokens[idx]
        return None

    def _next(self) -> Token | None:
        tok = self._peek()
        if tok is not None:
            self._pos += 1
        return tok

    def parse(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        # Optional SAV header line: a leading bare token not followed by "=".
        t0 = self._peek()
        t1 = self._peek(1)
        if t0 is not None and t0.kind == BARE and (t1 is None or t1.kind != EQUALS):
            self._next()
        while self._peek() is not None:
            key, value = self._parse_assignment()
            result[key] = value
        return result

    def _parse_assignment(self) -> tuple[str, Any]:
        key_tok = self._next()
        if key_tok is None:
            raise ParseError("unexpected end of input")
        eq = self._next()
        if eq is None or eq.kind != EQUALS:
            raise ParseError(
                f"expected '=' after '{key_tok.value}'", key_tok.pos
            )
        return key_tok.value, self._parse_value()

    def _parse_value(self) -> Any:
        tok = self._peek()
        if tok is None:
            raise ParseError("unexpected end of input")
        if tok.kind == LBRACE:
            return self._parse_brace()
        if tok.kind == STRING:
            self._next()
            return tok.value
        if tok.kind == BARE:
            self._next()
            return _coerce(tok.value)
        raise ParseError(f"unexpected token '{tok.value}'", tok.pos)

    def _parse_brace(self) -> Any:
        self._next()  # consume "{"
        nxt = self._peek()
        if nxt is None:
            raise ParseError("unterminated block")
        if nxt.kind == RBRACE:
            self._next()
            return {}
        if nxt.kind == LBRACE:
            # list of anonymous blocks
            items: list[Any] = []
            while self._peek() is not None and self._peek().kind == LBRACE:
                items.append(self._parse_brace())
            self._expect_rbrace()
            return items
        # block vs list: block if next token is followed by "="
        t1 = self._peek(1)
        if nxt.kind in (BARE, STRING) and t1 is not None and t1.kind == EQUALS:
            d: dict[str, Any] = {}
            while self._peek() is not None and self._peek().kind != RBRACE:
                k, v = self._parse_assignment()
                d[k] = v
            self._expect_rbrace()
            return d
        # list of scalars
        items = []
        while self._peek() is not None and self._peek().kind != RBRACE:
            items.append(self._parse_value())
        self._expect_rbrace()
        return items

    def _expect_rbrace(self) -> None:
        tok = self._next()
        if tok is None or tok.kind != RBRACE:
            raise ParseError("expected '}'", tok.pos if tok else None)


def parse(text: str) -> dict[str, Any]:
    """Parse a full document into a nested dict."""
    return Parser(text).parse()
