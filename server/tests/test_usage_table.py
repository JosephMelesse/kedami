import io
import re

import pytest

from kedami_server import usage_table
from kedami_server.usage import Recording, Tokens, Totals
from kedami_server.usage_table import HEADING, RunTable, lines


class Terminal(io.StringIO):
    def isatty(self):
        return True


def screen(written: str) -> list[str]:
    """What a terminal shows after the text: cursor up, erase line, and text written over a row."""
    rows, at = [""], 0
    for part in re.split(r"(\x1b\[\d+A|\x1b\[2K|\r|\n)", written):
        if up := re.fullmatch(r"\x1b\[(\d+)A", part):
            at = max(0, at - int(up[1]))
        elif part == "\x1b[2K":
            rows[at] = ""
        elif part == "\n":
            at += 1
            if at == len(rows):
                rows.append("")
        elif part and part != "\r":
            rows[at] = part + rows[at][len(part):]
    assert "\x1b" not in "".join(rows)
    return rows[:-1]


def spent(**stages):
    recording = Recording(None, "lesson", "ingest")
    recording.stages = {name: Totals(calls, ms, Tokens(), cost, 0) for name, (calls, ms, cost) in stages.items()}
    return recording


@pytest.fixture(autouse=True)
def no_live_table():
    yield
    usage_table._live = None


def test_the_table_has_a_row_per_pipeline_stage_and_a_total():
    stages = spent(ingest=(2, 5_000, 0.0123), extract=(1, 25_000, 0.08), plan=(1, 9_000, 0.05), generate=(55, 568_000, 1.10)).stages
    assert lines(HEADING, stages) == [
        "generating lesson...",
        "  Stage      Calls   Model time      Cost",
        "  ingest         2           5s     $0.01",
        "  extract        1          25s     $0.08",
        "  plan           1           9s     $0.05",
        "  generate      55       9m 28s     $1.10",
        "  total         59      10m 07s     $1.24",
    ]


def test_a_stage_not_reached_yet_shows_zeros_and_an_unpriced_call_is_flagged():
    stages = {"plan": Totals(3, 4_000, Tokens(), 0.5, 2)}
    table = lines(HEADING, stages)
    assert table[2] == "  ingest         0           0s     $0.00"
    assert table[4] == "  plan           3           4s     $0.50  (2 with no listed price)"
    assert table[6] == "  total          3           4s     $0.50  (2 with no listed price)"


def test_a_live_table_is_redrawn_in_place():
    terminal = Terminal()
    table = RunTable(terminal)
    table.start()
    assert screen(terminal.getvalue()) == lines(HEADING, {})
    table.update(spent(extract=(1, 25_000, 0.08)))
    last = spent(extract=(1, 25_000, 0.08), plan=(1, 9_000, 0.05))
    table.update(last)
    assert screen(terminal.getvalue()) == lines(HEADING, last.stages)
    # The closing heading is shorter than the one it replaces, and leaves nothing behind.
    table.finish("lesson ready in 34s", last.stages)
    assert screen(terminal.getvalue()) == lines("lesson ready in 34s", last.stages)


def test_output_that_is_not_a_terminal_gets_the_table_once_at_the_end():
    stream = io.StringIO()
    table = RunTable(stream)
    table.start()
    table.update(spent(extract=(1, 25_000, 0.08)))
    assert stream.getvalue() == ""
    final = spent(extract=(2, 30_000, 0.10)).stages
    table.finish("lesson failed in 31s", final)
    assert stream.getvalue() == "\n".join(lines("lesson failed in 31s", final)) + "\n"


def test_a_run_that_starts_while_another_is_live_prints_once_and_leaves_the_live_one_intact():
    terminal = Terminal()
    first, second = RunTable(terminal), RunTable(terminal)
    first.start()
    second.start()
    second.update(spent(extract=(9, 9_000, 9.0)))
    assert screen(terminal.getvalue()) == lines(HEADING, {})

    done = spent(extract=(1, 1_000, 0.01)).stages
    second.finish("lesson ready in 1s", done)
    later = spent(plan=(4, 2_000, 0.02))
    first.update(later)
    first.update(later)
    # The first table can no longer reach its old copy, so it continues in a new one below.
    assert screen(terminal.getvalue()) == (
        lines(HEADING, {}) + lines("lesson ready in 1s", done) + lines(HEADING, later.stages)
    )
    first.finish("lesson ready in 2s", later.stages)
    assert screen(terminal.getvalue())[-7:] == lines("lesson ready in 2s", later.stages)


def test_the_terminal_is_free_for_the_next_run_once_one_ends():
    terminal = Terminal()
    first = RunTable(terminal)
    first.start()
    first.finish("lesson ready in 1s", {})
    second = RunTable(terminal)
    second.start()
    second.update(spent(ingest=(1, 1_000, 0.01)))
    assert screen(terminal.getvalue()) == lines("lesson ready in 1s", {}) + lines(HEADING, spent(ingest=(1, 1_000, 0.01)).stages)


def test_a_closed_terminal_does_not_fail_the_run():
    terminal = Terminal()
    table = RunTable(terminal)
    table.start()
    terminal.close()
    table.update(spent(ingest=(1, 1_000, 0.01)))
    table.finish("lesson ready in 1s", {})
    assert usage_table._live is None
