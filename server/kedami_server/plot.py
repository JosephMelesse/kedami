"""Point sampling for plot blocks, so the renderer never parses SymPy."""

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
        expr = parse_math(function.expression, allowed).subs(defaults)
        evaluate = sympy.lambdify(x, expr, modules="math")
        series.append({"label": function.label, "points": [[xi, _safe(evaluate, xi)] for xi in xs]})
    return series


def _safe(evaluate, xi: float) -> float | None:
    try:
        value = evaluate(xi)
    except (ValueError, ZeroDivisionError, OverflowError, TypeError):
        return None
    if isinstance(value, complex) or not math.isfinite(value):
        return None
    return float(value)
