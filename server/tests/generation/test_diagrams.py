import pytest

from kedami_server.generation.diagrams import layout_problems

ROOT = '<svg viewBox="0 0 200 100" xmlns="http://www.w3.org/2000/svg" font-family="monospace" font-size="10">'


def svg(*elements, root=ROOT):
    return root + "".join(elements) + "</svg>"


def text(content, x, y, **attributes):
    extra = "".join(f' {name.replace("_", "-")}="{value}"' for name, value in attributes.items())
    return f'<text x="{x}" y="{y}"{extra} fill="currentColor">{content}</text>'


# A generated diagram whose labels ran into the boxes beside them.
MOVSX = (
    '<svg viewBox="0 0 320 130" xmlns="http://www.w3.org/2000/svg" font-family="monospace" font-size="12">'
    '<text x="10" y="68" fill="currentColor">MOVZX to 16 bits:</text>'
    '<rect x="100" y="54" width="100" height="22" fill="none" stroke="currentColor" stroke-dasharray="4"/>'
    '<text x="118" y="70" fill="currentColor">0000 0000</text>'
    '<rect x="200" y="54" width="100" height="22" fill="none" stroke="currentColor"/>'
    '<text x="218" y="70" fill="currentColor">1001 1100</text>'
    "</svg>"
)


def test_labels_running_into_boxes_are_caught():
    assert layout_problems(MOVSX) == [
        'text "MOVZX to 16 bits:" crosses the edge of the rect at (100, 54)',
        'text "MOVZX to 16 bits:" overlaps text "0000 0000"',
    ]


def test_the_same_diagram_with_room_for_its_labels_passes():
    fixed = MOVSX.replace("320", "360").replace('x="100"', 'x="140"').replace('x="118"', 'x="158"')
    fixed = fixed.replace('x="200"', 'x="240"').replace('x="218"', 'x="258"')
    assert layout_problems(fixed) == []


# Each character is 6 wide at font-size 10, so 10 characters take 60.


@pytest.mark.parametrize(
    "element, fits",
    [
        (text("x" * 33, 0, 20), True),  # 198 wide in a 200 wide viewBox
        (text("x" * 34, 0, 20), False),
        (text("x" * 10, 30, 20, text_anchor="middle"), True),  # spans 0 to 60
        (text("x" * 10, 25, 20, text_anchor="middle"), False),
        (text("x" * 10, 200, 20, text_anchor="end"), True),
        (text("x" * 10, 205, 20, text_anchor="end"), False),
        (text("top", 0, 7.5), True),  # ascent 7.5 reaches the top edge
        (text("top", 0, 5), False),
        (text("bottom", 0, 97.5), True),  # descent 2.5 reaches the bottom edge
        (text("bottom", 0, 100), False),
        (text("middle", 0, 5, dominant_baseline="middle"), True),
    ],
)
def test_text_must_stay_inside_the_view_box(element, fits):
    problems = layout_problems(svg(element))
    assert (problems == []) == fits
    assert fits or "runs past the viewBox" in problems[0]


def test_slack_of_one_unit_is_allowed():
    assert layout_problems(svg(text("x" * 33, 2.5, 20))) == []  # half a unit past the edge
    assert layout_problems(svg(text("x" * 33, 3.5, 20))) != []


def test_lines_set_one_font_size_apart_do_not_overlap():
    assert layout_problems(svg(text("first", 10, 20), text("second", 10, 30))) == []
    assert layout_problems(svg(text("first", 10, 20), text("second", 10, 27))) == [
        'text "first" overlaps text "second"'
    ]


def test_text_side_by_side_overlaps_only_when_it_reaches_the_next():
    assert layout_problems(svg(text("abcde", 10, 20), text("fgh", 40, 20))) == []
    assert layout_problems(svg(text("abcde", 10, 20), text("fgh", 36, 20))) == ['text "abcde" overlaps text "fgh"']


@pytest.mark.parametrize(
    "shape, x, y, crosses",
    [
        ('<rect x="10" y="10" width="80" height="20"/>', 20, 25, False),  # inside
        ('<rect x="10" y="10" width="80" height="20"/>', 100, 25, False),  # beside
        ('<rect x="10" y="10" width="80" height="20"/>', 70, 25, True),  # runs out the right side
        ('<rect x="10" y="10" width="80" height="20"/>', 20, 15, True),  # pokes out the top
        ('<circle cx="50" cy="50" r="30"/>', 35, 53, False),
        ('<circle cx="50" cy="50" r="30"/>', 35, 85, True),
        ('<circle cx="50" cy="50" r="30"/>', 35, 95, False),
        ('<ellipse cx="100" cy="50" rx="60" ry="20"/>', 85, 53, False),
        ('<ellipse cx="100" cy="50" rx="60" ry="20"/>', 85, 72, True),
    ],
)
def test_text_must_not_cross_a_shape_edge(shape, x, y, crosses):
    problems = layout_problems(svg(shape, text("label", x, y)))
    assert (problems != []) == crosses
    assert not crosses or "crosses the edge" in problems[0]


def test_lines_paths_and_polygons_are_not_checked():
    shapes = '<line x1="0" y1="20" x2="200" y2="20"/><path d="M0 0 L200 100"/><polygon points="0,0 200,0 100,100"/>'
    assert layout_problems(svg(shapes, text("on an arrow", 10, 22))) == []


def test_shapes_and_text_that_are_not_drawn_are_ignored():
    defs = '<defs><marker id="m"><rect x="0" y="0" width="300" height="300"/><text x="-50">hidden</text></marker></defs>'
    assert layout_problems(svg(defs, text("shown", 10, 20))) == []


def test_a_shape_sized_in_percent_is_not_checked():
    assert layout_problems(svg('<rect x="0" y="0" width="100%" height="10"/>', text("label", 10, 12))) == []


def test_font_size_and_anchor_are_inherited():
    group = '<g font-size="20" text-anchor="end">' + text("x" * 5, 200, 20) + text("y" * 5, 100, 50) + "</g>"
    assert layout_problems(svg(group)) == []
    assert "at font-size 20" in layout_problems(svg(group.replace('"200"', '"40"')))[0]


def test_whitespace_is_collapsed_and_entities_count_once():
    assert layout_problems(svg(text("  a &amp;\n   b  ", 170, 20))) == []  # "a & b" is 30 wide
    assert layout_problems(svg(text("a &amp; b!", 170, 20))) != []


def test_text_without_content_is_skipped():
    assert layout_problems(svg(text("   ", 500, 500))) == []


@pytest.mark.parametrize(
    "diagram, message",
    [
        ("<svg", "not well-formed XML"),
        ('<?xml version="1.0"?><!DOCTYPE svg [<!ENTITY a "aaaa">]><svg/>', "remove the DOCTYPE"),
        ("<g/>", "root element must be svg"),
        (svg(root='<svg font-family="monospace" font-size="10">'), "needs a viewBox"),
        (svg(root='<svg viewBox="0 0 0 100" font-family="monospace" font-size="10">'), "needs a viewBox"),
        (svg(root='<svg viewBox="0 0 200 100" font-size="10">'), 'must set font-family="monospace"'),
        (svg(root='<svg viewBox="0 0 200 100" font-family="sans-serif" font-size="10">'), "font-family"),
        (svg(root='<svg viewBox="0 0 200 100" font-family="monospace">'), "numeric font-size"),
        (svg(root='<svg viewBox="0 0 200 100" font-family="monospace" font-size="1em">'), "numeric font-size"),
    ],
)
def test_malformed_diagrams_are_rejected(diagram, message):
    [problem] = layout_problems(diagram)
    assert message in problem


@pytest.mark.parametrize(
    "element, message",
    [
        ('<text x="10" y="20">a<tspan>b</tspan></text>', "without tspan"),
        ('<g transform="translate(10 0)"><text x="10" y="20">a</text></g>', "under a transform"),
        ('<text x="10" y="20" transform="rotate(90)">a</text>', "under a transform"),
        ('<text x="10" y="20" style="font-size: 40px">a</text>', "style attribute"),
        ('<text x="10 16" y="20">ab</text>', "single numbers"),
        ('<text x="10%" y="20">a</text>', "single numbers"),
        ('<text x="10" y="20" font-size="large">a</text>', "positive number"),
        ('<text x="10" y="20" text-anchor="inherit">a</text>', "use start, middle, or end"),
        ('<text x="10" y="20" dominant-baseline="hanging">a</text>', "leave it out or use middle"),
        ('<text x="10" y="20" font-family="serif">a</text>', 'found "serif"'),
    ],
)
def test_text_that_cannot_be_measured_is_rejected(element, message):
    problems = layout_problems(svg(element))
    assert any(message in problem for problem in problems), problems


def test_every_problem_is_reported_once():
    problems = layout_problems(svg(text("wide " * 10, 0, 20), text("wide " * 10, 0, 20)))
    assert problems == [
        'text "wide wide wide wide wide wide wide wide wide wide" runs past the viewBox: at font-size 10 it spans '
        "x 0 to 294 and y 12.5 to 22.5",
        'text "wide wide wide wide wide wide wide wide wide wide" overlaps text "wide wide wide wide wide wide wide '
        'wide wide wide"',
    ]
