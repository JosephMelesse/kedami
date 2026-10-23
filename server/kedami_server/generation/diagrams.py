"""Checks the text layout of a model-written diagram.

The model places text by coordinate without seeing it drawn, so labels can run into boxes,
into each other, or past the edge of the viewBox. Diagram text is monospace, so its size
follows from its length and can be checked against the shapes around it.
"""

import math
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass

ADVANCE = 0.6  # A monospace character's width, as a fraction of the font size.
ASCENT = 0.75
DESCENT = 0.25
SLACK = 1.0  # Overlaps up to this far, in viewBox units, are allowed.

INHERITED = ("font-family", "font-size", "text-anchor", "dominant-baseline")
NOT_DRAWN = {"defs", "marker", "symbol", "clipPath", "mask", "pattern"}
ANCHORS = {"start": 0.0, "middle": 0.5, "end": 1.0}
NUMBER = re.compile(r"\s*(-?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)(?:px)?\s*")


class Unmeasurable(ValueError):
    pass


@dataclass(frozen=True)
class Box:
    left: float
    top: float
    right: float
    bottom: float

    def shrunk(self) -> "Box":
        return Box(self.left + SLACK, self.top + SLACK, self.right - SLACK, self.bottom - SLACK)

    def overlaps(self, other: "Box") -> bool:
        return self.left < other.right and other.left < self.right and self.top < other.bottom and other.top < self.bottom

    def inside(self, other: "Box") -> bool:
        return (
            self.left >= other.left and self.right <= other.right and self.top >= other.top and self.bottom <= other.bottom
        )


@dataclass(frozen=True)
class Text:
    content: str
    size: float
    box: Box


@dataclass(frozen=True)
class Rect:
    box: Box

    def crossed_by(self, box: Box) -> bool:
        return box.overlaps(self.box) and not box.inside(self.box)

    def __str__(self) -> str:
        return f"rect at ({_num(self.box.left)}, {_num(self.box.top)})"


@dataclass(frozen=True)
class Ellipse:
    name: str
    cx: float
    cy: float
    rx: float
    ry: float

    def crossed_by(self, box: Box) -> bool:
        # In units of the radii the ellipse is a unit circle and the box stays a box.
        left, right = (box.left - self.cx) / self.rx, (box.right - self.cx) / self.rx
        top, bottom = (box.top - self.cy) / self.ry, (box.bottom - self.cy) / self.ry
        nearest = math.hypot(min(max(0.0, left), right), min(max(0.0, top), bottom))
        farthest = math.hypot(max(abs(left), abs(right)), max(abs(top), abs(bottom)))
        return nearest < 1 < farthest

    def __str__(self) -> str:
        return f"{self.name} at ({_num(self.cx)}, {_num(self.cy)})"


def layout_problems(svg: str) -> list[str]:
    """Every layout problem in the diagram, in words the model can act on. Empty when there are none."""
    if "<!DOCTYPE" in svg or "<!ENTITY" in svg:
        return ["remove the DOCTYPE"]
    try:
        root = ET.fromstring(svg)
    except ET.ParseError as error:
        return [f"the SVG is not well-formed XML ({error})"]
    if _tag(root) != "svg":
        return ["the root element must be svg"]
    view = _view_box(root.get("viewBox"))
    if view is None:
        return ["the root svg needs a viewBox of four numbers with a positive width and height"]
    if root.get("font-family") != "monospace" or _number(root.get("font-size")) is None:
        return ['the root svg must set font-family="monospace" and a numeric font-size']

    texts: list[Text] = []
    shapes: list[Rect | Ellipse] = []
    problems: list[str] = []
    _collect(root, {}, False, texts, shapes, problems)
    for text in texts:
        box = text.box.shrunk()
        if not box.inside(view):
            problems.append(
                f'text "{text.content}" runs past the viewBox: at font-size {_num(text.size)} it spans '
                f"x {_num(text.box.left)} to {_num(text.box.right)} and y {_num(text.box.top)} to {_num(text.box.bottom)}"
            )
        problems += [f'text "{text.content}" crosses the edge of the {shape}' for shape in shapes if shape.crossed_by(box)]
    for i, first in enumerate(texts):
        for second in texts[i + 1 :]:
            if first.box.shrunk().overlaps(second.box.shrunk()):
                problems.append(f'text "{first.content}" overlaps text "{second.content}"')
    return list(dict.fromkeys(problems))


def _collect(
    element: ET.Element,
    inherited: dict[str, str],
    transformed: bool,
    texts: list[Text],
    shapes: list[Rect | Ellipse],
    problems: list[str],
) -> None:
    tag = _tag(element)
    if tag in NOT_DRAWN:
        return
    family = element.get("font-family")
    if family is not None and family != "monospace":
        problems.append(f'only font-family="monospace" is allowed; found "{family}"')
    attributes = inherited | {name: element.get(name) for name in INHERITED if element.get(name) is not None}
    transformed = transformed or element.get("transform") is not None or element.get("style") is not None
    if tag == "text":
        try:
            text = _measure(element, attributes, transformed)
        except Unmeasurable as error:
            problems.append(f'text "{_content(element)}" {error}')
            return
        if text is not None:
            texts.append(text)
        return
    if not transformed and (shape := _shape(element, tag)) is not None:
        shapes.append(shape)
    for child in element:
        _collect(child, attributes, transformed, texts, shapes, problems)


def _measure(element: ET.Element, attributes: dict[str, str], transformed: bool) -> Text | None:
    if len(element):
        raise Unmeasurable("must hold plain text, without tspan or other child elements")
    content = _content(element)
    if not content:
        return None
    if transformed:
        raise Unmeasurable("can't be under a transform or a style attribute; place it with x and y")
    x, y = _number(element.get("x", "0")), _number(element.get("y", "0"))
    if x is None or y is None:
        raise Unmeasurable("needs x and y as single numbers")
    size = _number(attributes["font-size"])
    if size is None or size <= 0:
        raise Unmeasurable("needs a font-size that is a positive number")
    anchor = attributes.get("text-anchor", "start")
    if anchor not in ANCHORS:
        raise Unmeasurable(f'has text-anchor "{anchor}"; use start, middle, or end')
    baseline = attributes.get("dominant-baseline", "auto")
    if baseline in ("auto", "alphabetic"):
        top, bottom = y - ASCENT * size, y + DESCENT * size
    elif baseline in ("middle", "central"):
        top, bottom = y - size / 2, y + size / 2
    else:
        raise Unmeasurable(f'has dominant-baseline "{baseline}"; leave it out or use middle')
    width = len(content) * ADVANCE * size
    left = x - ANCHORS[anchor] * width
    return Text(content, size, Box(left, top, left + width, bottom))


def _shape(element: ET.Element, tag: str) -> Rect | Ellipse | None:
    """The shape's outline, or None for an element that isn't checked or whose size isn't a plain number."""
    if tag == "rect":
        x, y, width, height = _numbers(element, "x", "y", "width", "height")
        if None in (x, y, width, height) or width <= 0 or height <= 0:
            return None
        return Rect(Box(x, y, x + width, y + height))
    if tag == "circle":
        cx, cy, r = _numbers(element, "cx", "cy", "r")
        if None in (cx, cy, r) or r <= 0:
            return None
        return Ellipse("circle", cx, cy, r, r)
    if tag == "ellipse":
        cx, cy, rx, ry = _numbers(element, "cx", "cy", "rx", "ry")
        if None in (cx, cy, rx, ry) or rx <= 0 or ry <= 0:
            return None
        return Ellipse("ellipse", cx, cy, rx, ry)
    return None


def _numbers(element: ET.Element, *names: str) -> list[float | None]:
    # Positions default to 0; sizes have no default.
    return [_number(element.get(name, "0" if name in ("x", "y", "cx", "cy") else None)) for name in names]


def _view_box(value: str | None) -> Box | None:
    parts = (value or "").replace(",", " ").split()
    numbers = [_number(part) for part in parts]
    if len(numbers) != 4 or None in numbers or numbers[2] <= 0 or numbers[3] <= 0:
        return None
    x, y, width, height = numbers
    return Box(x, y, x + width, y + height)


def _number(value: str | None) -> float | None:
    match = NUMBER.fullmatch(value) if value is not None else None
    return float(match.group(1)) if match else None


def _content(element: ET.Element) -> str:
    # SVG collapses runs of whitespace and trims the ends.
    return " ".join("".join(element.itertext()).split())


def _tag(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def _num(value: float) -> str:
    return f"{value:.1f}".removesuffix(".0")
