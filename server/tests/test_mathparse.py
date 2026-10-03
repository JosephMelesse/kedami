import pytest
import sympy

from kedami_server.mathparse import MAX_DEPTH, MAX_LENGTH, MathParseError, parse_math

x, y, g, theta, v0 = sympy.symbols("x y g theta v0")


@pytest.mark.parametrize(
    "text, expected",
    [
        ("1 + 2*3", sympy.Integer(7)),
        ("x**2 + 1", x**2 + 1),
        ("x^2", x**2),
        ("2**3**2", sympy.Integer(512)),
        ("-x**2", -(x**2)),
        ("x**-1", 1 / x),
        ("(x + 1)*(x - 1)", (x + 1) * (x - 1)),
        ("x/2/y", x / 2 / y),
        ("sin(pi/2)", sympy.Integer(1)),
        ("log(E)", sympy.Integer(1)),
        ("log(8, 2)", sympy.Integer(3)),
        ("ln(x)", sympy.log(x)),
        ("abs(x) + Abs(y)", sympy.Abs(x) + sympy.Abs(y)),
        ("v0**2*sin(theta)**2/(2*g)", v0**2 * sympy.sin(theta) ** 2 / (2 * g)),
        ("1.5e3", sympy.Float(1500)),
        (".5", sympy.Float(0.5)),
    ],
)
def test_parses(text, expected):
    assert sympy.simplify(parse_math(text) - expected) == 0


@pytest.mark.parametrize(
    "text",
    [
        "__import__('os').system('ls')",
        "x.__class__",
        "lambda: 1",
        "[x]",
        "'x'",
        "x = 1",
        "x; y",
        "eval('1')",
        "exec(x)",
        "sympify(x)",
        "Symbol(x)",
        "2x",
        "x y",
        "sin x",
        "sin",
        "sin(x, y)",
        "log(x, y, g)",
        "x +",
        "(x",
        "x)",
        "",
        "_x",
        "x!",
        "x % 2",
    ],
)
def test_rejects(text):
    with pytest.raises(MathParseError):
        parse_math(text)


def test_allowed_symbols():
    assert parse_math("a*x", {"x", "a"}) == sympy.Symbol("a") * x
    with pytest.raises(MathParseError, match="'b'"):
        parse_math("b*x", {"x", "a"})


def test_constants_and_functions_are_always_allowed():
    parse_math("sin(pi*x) + E", {"x"})


def test_length_limit():
    parse_math("x" + "+x" * ((MAX_LENGTH - 1) // 2))
    with pytest.raises(MathParseError, match="longer"):
        parse_math("x" * (MAX_LENGTH + 1))


def test_depth_limit():
    with pytest.raises(MathParseError, match="nested"):
        parse_math("(" * (MAX_DEPTH + 1) + "x" + ")" * (MAX_DEPTH + 1))
    with pytest.raises(MathParseError, match="nested"):
        parse_math("-" * (MAX_DEPTH + 1) + "x")


@pytest.mark.parametrize("text", ["9**9**9", "10**100000", "(10**100)**1000"])
def test_huge_powers_rejected(text):
    with pytest.raises(MathParseError, match="too large"):
        parse_math(text)


def test_symbolic_large_power_is_allowed():
    assert parse_math("x**1000") == x**1000
