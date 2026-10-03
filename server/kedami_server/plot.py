"""Point sampling and expression trees for plot blocks, so the renderer never parses SymPy."""

import math

import sympy

from .lesson import PlotBlock
from .mathparse import parse_math

SAMPLES = 201


def sample_points(block: PlotBlock) -> list[dict]:
    """Sample each function across the x domain, with parameters at their defaults.

    A y value is None where the function is undefined or not a finite real number.
    """
    x = sympy.Symbol("x")
    defaults = {sympy.Symbol(p.name): p.default for p in block.parameters}
    allowed = {"x", *(p.name for p in block.parameters)}
    start, end = block.x_domain
    xs = [start + (end - start) * i / (SAMPLES - 1) for i in range(SAMPLES)]

    series = []
    for function in block.functions:
        parsed = parse_math(function.expression, allowed)
        evaluate = sympy.lambdify(x, parsed.subs(defaults), modules="math")
        series.append(
            {
                "label": function.label,
                "points": [[xi, _safe(evaluate, xi)] for xi in xs],
                "tree": expression_tree(parsed),
            }
        )
    return series


TREE_FUNCTIONS = {
    sympy.sin: "sin",
    sympy.cos: "cos",
    sympy.tan: "tan",
    sympy.asin: "asin",
    sympy.acos: "acos",
    sympy.atan: "atan",
    sympy.sinh: "sinh",
    sympy.cosh: "cosh",
    sympy.tanh: "tanh",
    sympy.exp: "exp",
    sympy.log: "log",
    sympy.Abs: "abs",
}


def expression_tree(expr: sympy.Expr) -> dict:
    """A JSON form of an expression that the renderer evaluates with plain arithmetic.

    Nodes: {"num": float | None}, {"sym": name}, {"add": [...]}, {"mul": [...]},
    {"pow": [base, exponent]}, {"fn": name, "arg": node}. A None number is not real.
    """
    if not expr.free_symbols:
        value = complex(expr.evalf())
        return {"num": value.real if value.imag == 0 and math.isfinite(value.real) else None}
    if isinstance(expr, sympy.Symbol):
        return {"sym": expr.name}
    if isinstance(expr, sympy.Add):
        return {"add": [expression_tree(arg) for arg in expr.args]}
    if isinstance(expr, sympy.Mul):
        return {"mul": [expression_tree(arg) for arg in expr.args]}
    if isinstance(expr, sympy.Pow):
        return {"pow": [expression_tree(arg) for arg in expr.args]}
    if expr.func in TREE_FUNCTIONS and len(expr.args) == 1:
        return {"fn": TREE_FUNCTIONS[expr.func], "arg": expression_tree(expr.args[0])}
    raise ValueError(f"cannot express {expr.func.__name__} for the renderer")


def _safe(evaluate, xi: float) -> float | None:
    try:
        value = evaluate(xi)
    except (ValueError, ZeroDivisionError, OverflowError, TypeError):
        return None
    if isinstance(value, complex) or not math.isfinite(value):
        return None
    return float(value)
