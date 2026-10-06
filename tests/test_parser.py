"""Tests for the lexer and recursive-descent parser."""

from ck3_strategist.lexer import tokenize
from ck3_strategist.parser import parse


def test_scalars():
    assert parse("a=1") == {"a": 1}
    assert parse("a=2.5") == {"a": 2.5}
    assert parse("a=yes") == {"a": True}
    assert parse("a=no") == {"a": False}
    assert parse("a=hello") == {"a": "hello"}
    assert parse("a=918.11.5") == {"a": "918.11.5"}  # date stays str


def test_quoted_string():
    assert parse('a="hello world"') == {"a": "hello world"}
    assert parse('a="has { braces } and = equals"') == {
        "a": "has { braces } and = equals"
    }


def test_list():
    assert parse("a={ 1 2 3 }") == {"a": [1, 2, 3]}
    assert parse("a={ 63 59 55 3 }") == {"a": [63, 59, 55, 3]}


def test_block():
    assert parse("a={ x=1 y=2 }") == {"a": {"x": 1, "y": 2}}


def test_empty_brace():
    assert parse("a={ }") == {"a": {}}


def test_nested_anonymous_blocks():
    text = "claim={ { title=3238 } { title=8207 } }"
    assert parse(text) == {"claim": [{"title": 3238}, {"title": 8207}]}


def test_nested_blocks():
    text = "a={ b={ c=1 } d={ 2 3 } }"
    assert parse(text) == {"a": {"b": {"c": 1}, "d": [2, 3]}}


def test_multiple_assignments():
    text = "x=1\ny=2\nz={ a=3 }"
    assert parse(text) == {"x": 1, "y": 2, "z": {"a": 3}}


def test_optional_sav_header():
    text = "SAV010256987c3c00007f84\nmeta_data={ version=15 }"
    assert parse(text) == {"meta_data": {"version": 15}}


def test_no_header():
    text = "meta_data={ version=15 }"
    assert parse(text) == {"meta_data": {"version": 15}}


def test_tokenize_basic():
    toks = list(tokenize('a={ 1 "two" }'))
    kinds = [t.kind for t in toks]
    assert kinds == ["BARE", "EQUALS", "LBRACE", "BARE", "STRING", "RBRACE"]
