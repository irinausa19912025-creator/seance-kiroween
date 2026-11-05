"""Tokenizer, recursive-descent parser and validator for Seance predicates.

The expression language is intentionally small and closed. Only the primary
terms listed below, integer literals, declared parameter names, parenthesised
grouping, the six comparisons and the three boolean operators are allowed.
Anything else - an unknown identifier, a function call, a stray symbol - is
rejected with the offending text and its character position, so a skeleton
author never has to guess why a predicate was silently accepted as something
else.

Grammar, lowest precedence first:

    expr      := or_expr
    or_expr   := and_expr ("or" and_expr)*
    and_expr  := not_expr ("and" not_expr)*
    not_expr  := "not" not_expr | cmp_expr
    cmp_expr  := primary (cmp_op primary)?        # a single, non-chained comparison
    primary   := IDENT | INT | "(" expr ")"

Primary terms (the only identifiers that are not parameters):

    open, high, low, close      the current bar
    pool_high, pool_low         extreme of the previous N closed bars
    entry_high, entry_low       high and low of the bar that opened the pending
                                observation
    bars_since_entry            bars elapsed since that bar (integer)

A declared parameter name is also a valid primary. The parser does not know
which identifiers are parameters, so it builds the tree and a separate validate()
pass checks every identifier against the built-in terms plus the caller's
parameter set. Both failures raise SeanceParseError.
"""

from __future__ import annotations

import operator as _op
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Set, Union


# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #
class SeanceError(Exception):
    """Base class for Seance expression and model errors."""


class SeanceParseError(SeanceError):
    """A predicate string is not a valid Seance expression.

    Carries the offending text and its 0-based character position when known, so
    every rejection points at the exact thing that was not allowed.
    """

    def __init__(self, message: str, text: str = None, pos: int = None):
        self.text = text
        self.pos = pos
        loc = ""
        if text is not None:
            loc = f": {text!r}"
        if pos is not None:
            loc += f" at position {pos}"
        super().__init__(message + loc)


# --------------------------------------------------------------------------- #
# AST
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Lit:
    """An integer literal."""

    value: int
    pos: int


@dataclass(frozen=True)
class Var:
    """An identifier: a built-in primary term or a declared parameter name."""

    name: str
    pos: int


@dataclass(frozen=True)
class Cmp:
    """A single comparison ``left op right``; op is one of < <= > >= == !=."""

    op: str
    left: Expr
    right: Expr


@dataclass(frozen=True)
class Not:
    operand: Expr


@dataclass(frozen=True)
class And:
    left: Expr
    right: Expr


@dataclass(frozen=True)
class Or:
    left: Expr
    right: Expr


Expr = Union[Lit, Var, Cmp, Not, And, Or]


# The only identifiers that are meaningful without being a declared parameter.
BUILTINS: frozenset = frozenset({
    "open", "high", "low", "close",
    "pool_high", "pool_low",
    "entry_high", "entry_low",
    "bars_since_entry",
})


# --------------------------------------------------------------------------- #
# Tokenizer
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Token:
    kind: str
    text: str
    pos: int


_TWO_CHAR = {"<=": "LE", ">=": "GE", "==": "EQ", "!=": "NE"}
_ONE_CHAR = {"<": "LT", ">": "GT", "(": "LPAREN", ")": "RPAREN"}
_KEYWORDS = {"and": "AND", "or": "OR", "not": "NOT"}


def tokenize(s: str) -> List[Token]:
    """Turn a predicate string into a token list terminated by EOF.

    Raises SeanceParseError on any character that is not whitespace, an
    identifier/number character, or one of the allowed operators.
    """
    tokens: List[Token] = []
    i, n = 0, len(s)
    while i < n:
        c = s[i]
        if c in " \t\r\n":
            i += 1
            continue
        if c.isalpha() or c == "_":
            start = i
            while i < n and (s[i].isalnum() or s[i] == "_"):
                i += 1
            word = s[start:i]
            kind = _KEYWORDS.get(word.lower())
            tokens.append(Token(kind if kind is not None else "IDENT", word, start))
            continue
        if c.isdigit():
            start = i
            while i < n and s[i].isdigit():
                i += 1
            tokens.append(Token("INT", s[start:i], start))
            continue
        two = s[i:i + 2]
        if two in _TWO_CHAR:
            tokens.append(Token(_TWO_CHAR[two], two, i))
            i += 2
            continue
        if c in _ONE_CHAR:
            tokens.append(Token(_ONE_CHAR[c], c, i))
            i += 1
            continue
        raise SeanceParseError("unexpected symbol", c, i)
    tokens.append(Token("EOF", "", n))
    return tokens


# --------------------------------------------------------------------------- #
# Parser
# --------------------------------------------------------------------------- #
_CMP_OPS = {"LT", "LE", "GT", "GE", "EQ", "NE"}


class _Parser:
    def __init__(self, tokens: List[Token], source: str):
        self.tokens = tokens
        self.source = source
        self.i = 0

    def _peek(self) -> Token:
        return self.tokens[self.i]

    def _next(self) -> Token:
        tok = self.tokens[self.i]
        self.i += 1
        return tok

    def parse(self) -> Expr:
        node = self._or()
        tok = self._peek()
        if tok.kind != "EOF":
            raise SeanceParseError("unexpected trailing input", tok.text, tok.pos)
        return node

    def _or(self) -> Expr:
        node = self._and()
        while self._peek().kind == "OR":
            self._next()
            node = Or(node, self._and())
        return node

    def _and(self) -> Expr:
        node = self._not()
        while self._peek().kind == "AND":
            self._next()
            node = And(node, self._not())
        return node

    def _not(self) -> Expr:
        if self._peek().kind == "NOT":
            self._next()
            return Not(self._not())
        return self._cmp()

    def _cmp(self) -> Expr:
        left = self._primary()
        tok = self._peek()
        if tok.kind in _CMP_OPS:
            self._next()
            right = self._primary()
            return Cmp(tok.text, left, right)
        return left

    def _primary(self) -> Expr:
        tok = self._peek()
        if tok.kind == "INT":
            self._next()
            return Lit(int(tok.text), tok.pos)
        if tok.kind == "IDENT":
            self._next()
            # An identifier immediately followed by "(" is a function call,
            # which is not part of this language. Reject it explicitly rather
            # than letting it parse as a Var followed by a stray group.
            if self._peek().kind == "LPAREN":
                raise SeanceParseError("function calls are not allowed", tok.text, tok.pos)
            return Var(tok.text, tok.pos)
        if tok.kind == "LPAREN":
            self._next()
            node = self._or()
            close = self._peek()
            if close.kind != "RPAREN":
                raise SeanceParseError("expected ')'", close.text, close.pos)
            self._next()
            return node
        raise SeanceParseError("expected an identifier, integer or '('", tok.text, tok.pos)


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def parse(s: str) -> Expr:
    """Parse a predicate string into an AST.

    Raises SeanceParseError on any syntax error, naming the offending text and
    its position. Does not check whether identifiers are known - use validate()
    for that.
    """
    return _Parser(tokenize(s), s).parse()


def validate(node: Expr, params: Iterable[str]) -> None:
    """Confirm every identifier in the tree is a built-in primary or a parameter.

    Raises SeanceParseError naming any unknown identifier and its position.
    """
    _validate(node, BUILTINS | set(params))


def _validate(node: Expr, allowed: Set[str]) -> None:
    if isinstance(node, Lit):
        return
    if isinstance(node, Var):
        if node.name not in allowed:
            raise SeanceParseError("unknown identifier", node.name, node.pos)
        return
    if isinstance(node, Cmp):
        _validate(node.left, allowed)
        _validate(node.right, allowed)
        return
    if isinstance(node, Not):
        _validate(node.operand, allowed)
        return
    if isinstance(node, (And, Or)):
        _validate(node.left, allowed)
        _validate(node.right, allowed)
        return
    raise SeanceParseError(f"internal error: unknown AST node {node!r}")


def compile_expr(s: str, params: Iterable[str]) -> Expr:
    """Parse and validate a predicate in one step."""
    node = parse(s)
    validate(node, params)
    return node


_CMP_FUNCS = {
    "<": _op.lt, "<=": _op.le, ">": _op.gt, ">=": _op.ge,
    "==": _op.eq, "!=": _op.ne,
}


def eval_expr(node: Expr, ctx: Dict[str, Any]) -> Any:
    """Evaluate a parsed expression against a name->value context.

    ``ctx`` must supply a value for every Var the tree references. Comparisons
    and boolean operators return bool; identifiers and literals return their
    values. Handy for exercising the parser without generating code.
    """
    if isinstance(node, Lit):
        return node.value
    if isinstance(node, Var):
        if node.name not in ctx:
            raise SeanceError(f"no value provided for identifier {node.name!r}")
        return ctx[node.name]
    if isinstance(node, Cmp):
        return _CMP_FUNCS[node.op](eval_expr(node.left, ctx), eval_expr(node.right, ctx))
    if isinstance(node, Not):
        return not eval_expr(node.operand, ctx)
    if isinstance(node, And):
        return bool(eval_expr(node.left, ctx)) and bool(eval_expr(node.right, ctx))
    if isinstance(node, Or):
        return bool(eval_expr(node.left, ctx)) or bool(eval_expr(node.right, ctx))
    raise SeanceError(f"internal error: cannot evaluate {node!r}")


__all__ = [
    "SeanceError", "SeanceParseError",
    "Lit", "Var", "Cmp", "Not", "And", "Or", "Expr",
    "BUILTINS",
    "tokenize", "parse", "validate", "compile_expr", "eval_expr",
]
