"""Restricted parser for math strings in SymPy syntax.

Builds SymPy objects directly from a token stream. Nothing is ever passed to
`eval`, `sympify`, or `parse_expr`, so a string can only produce numbers,
whitelisted constants and functions, symbols, and arithmetic.

Grammar:
    sum     := product (("+" | "-") product)*
    product := unary (("*" | "/") unary)*
    unary   := ("+" | "-") unary | power
    power   := atom (("**" | "^") unary)?
    atom    := NUMBER | NAME | NAME "(" sum ("," sum)* ")" | "(" sum ")"
"""

import re
from collections.abc import Collection
from dataclasses import dataclass

import sympy

MAX_LENGTH = 500
MAX_DEPTH = 50
MAX_POWER_DIGITS = 10_000

FUNCTIONS = {
    "sin": (sympy.sin, 1),
    "cos": (sympy.cos, 1),
    "tan": (sympy.tan, 1),
    "asin": (sympy.asin, 1),
    "acos": (sympy.acos, 1),
    "atan": (sympy.atan, 1),
    "sinh": (sympy.sinh, 1),
    "cosh": (sympy.cosh, 1),
    "tanh": (sympy.tanh, 1),
    "exp": (sympy.exp, 1),
    "log": (sympy.log, (1, 2)),
    "ln": (sympy.log, 1),
    "sqrt": (sympy.sqrt, 1),
    "Abs": (sympy.Abs, 1),
    "abs": (sympy.Abs, 1),
}

CONSTANTS = {
    "pi": sympy.pi,
    "E": sympy.E,
}


class MathParseError(ValueError):
    pass


@dataclass
class _Token:
    kind: str  # "num", "name", "op", "end"
    text: str
    pos: int


_TOKEN = re.compile(
    r"\s*(?:"
    r"(?P<num>(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)"
    r"|(?P<name>[A-Za-z][A-Za-z0-9_]*)"
    r"|(?P<op>\*\*|[-+*/^(),])"
    r")"
)


def _tokenize(text: str) -> list[_Token]:
    tokens = []
    pos = 0
    while pos < len(text):
        if text[pos:].strip() == "":
            break
        match = _TOKEN.match(text, pos)
        if not match or match.lastgroup is None:
            raise MathParseError(f"unexpected character at position {pos}")
        tokens.append(_Token(match.lastgroup, match.group(match.lastgroup), match.start(match.lastgroup)))
        pos = match.end()
    tokens.append(_Token("end", "", len(text)))
    return tokens


class _Parser:
    def __init__(self, tokens: list[_Token], allowed_symbols: Collection[str] | None):
        self.tokens = tokens
        self.index = 0
        self.depth = 0
        self.allowed_symbols = allowed_symbols

    def peek(self) -> _Token:
        return self.tokens[self.index]

    def take(self) -> _Token:
        token = self.tokens[self.index]
        self.index += 1
        return token

    def expect(self, text: str) -> None:
        token = self.take()
        if token.text != text:
            raise MathParseError(f"expected {text!r} at position {token.pos}")

    def at_op(self, *ops: str) -> bool:
        token = self.peek()
        return token.kind == "op" and token.text in ops

    def enter(self) -> None:
        self.depth += 1
        if self.depth > MAX_DEPTH:
            raise MathParseError("expression is nested too deeply")

    def parse(self) -> sympy.Expr:
        expr = self.sum()
        token = self.peek()
        if token.kind != "end":
            raise MathParseError(f"unexpected {token.text!r} at position {token.pos}")
        return expr

    def sum(self) -> sympy.Expr:
        left = self.product()
        while self.at_op("+", "-"):
            op = self.take().text
            right = self.product()
            left = left + right if op == "+" else left - right
        return left

    def product(self) -> sympy.Expr:
        left = self.unary()
        while self.at_op("*", "/"):
            op = self.take().text
            right = self.unary()
            left = left * right if op == "*" else left / right
        return left

    def unary(self) -> sympy.Expr:
        self.enter()
        try:
            if self.at_op("+", "-"):
                op = self.take().text
                operand = self.unary()
                return operand if op == "+" else -operand
            return self.power()
        finally:
            self.depth -= 1

    def power(self) -> sympy.Expr:
        base = self.atom()
        if self.at_op("**", "^"):
            self.take()
            exponent = self.unary()
            _check_power_size(base, exponent)
            return base**exponent
        return base

    def atom(self) -> sympy.Expr:
        token = self.take()
        if token.kind == "num":
            if re.fullmatch(r"\d+", token.text):
                return sympy.Integer(token.text)
            return sympy.Float(token.text)
        if token.kind == "name":
            if self.at_op("("):
                return self.call(token)
            return self.name(token)
        if token.text == "(":
            self.enter()
            try:
                inner = self.sum()
            finally:
                self.depth -= 1
            self.expect(")")
            return inner
        where = "end of input" if token.kind == "end" else f"{token.text!r} at position {token.pos}"
        raise MathParseError(f"unexpected {where}")

    def call(self, token: _Token) -> sympy.Expr:
        if token.text not in FUNCTIONS:
            raise MathParseError(f"unknown function {token.text!r}")
        func, arity = FUNCTIONS[token.text]
        self.expect("(")
        args = [self.sum()]
        while self.at_op(","):
            self.take()
            args.append(self.sum())
        self.expect(")")
        allowed = arity if isinstance(arity, tuple) else (arity,)
        if len(args) not in allowed:
            raise MathParseError(f"{token.text} takes {' or '.join(map(str, allowed))} argument(s)")
        return func(*args)

    def name(self, token: _Token) -> sympy.Expr:
        if token.text in CONSTANTS:
            return CONSTANTS[token.text]
        if token.text in FUNCTIONS:
            raise MathParseError(f"function {token.text!r} needs arguments")
        if self.allowed_symbols is not None and token.text not in self.allowed_symbols:
            raise MathParseError(f"unknown name {token.text!r}")
        return sympy.Symbol(token.text)


def _check_power_size(base: sympy.Expr, exponent: sympy.Expr) -> None:
    """Reject exact numeric powers whose result would have an enormous number of digits."""
    if not (base.is_Rational and exponent.is_Number):
        return
    base_digits = len(str(abs(base.p))) + len(str(base.q))
    if abs(exponent) * base_digits > MAX_POWER_DIGITS:
        raise MathParseError("number is too large")


def parse_math(text: str, allowed_symbols: Collection[str] | None = None) -> sympy.Expr:
    """Parse a SymPy-syntax math string.

    If `allowed_symbols` is given, any free name outside it is rejected.
    """
    if len(text) > MAX_LENGTH:
        raise MathParseError(f"expression is longer than {MAX_LENGTH} characters")
    return _Parser(_tokenize(text), allowed_symbols).parse()
