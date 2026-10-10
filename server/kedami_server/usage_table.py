"""A run's usage in the server's terminal: a heading and a table, redrawn in place as calls finish.

See architecture/system.md, Usage log.
"""

import sys
import threading
from typing import TextIO

from . import usage
from .usage import Recording, Totals

HEADING = "generating lesson..."
PIPELINE_STAGES = usage.STAGES[:4]

_lock = threading.Lock()
# The table being redrawn in place. A terminal has one cursor, so a run that starts while
# another is live prints its table once, when it ends.
_live: "RunTable | None" = None


def lines(heading: str, stages: dict[str, Totals]) -> list[str]:
    rows = [(stage, stages.get(stage, Totals())) for stage in PIPELINE_STAGES]
    rows.append(("total", sum(stages.values(), Totals())))
    return [heading, _row("Stage", "Calls", "Model time", "Cost")] + [
        _row(name, str(totals.calls), usage.duration(totals.latency_ms / 1000), f"${totals.cost:,.2f}")
        + (f"  ({totals.unpriced} with no listed price)" if totals.unpriced else "")
        for name, totals in rows
    ]


def _row(stage: str, calls: str, time: str, cost: str) -> str:
    return f"  {stage:<9}{calls:>7}{time:>13}{cost:>10}"


class RunTable:
    def __init__(self, stream: TextIO | None = None):
        self.stream = stream or sys.stderr
        # How many lines of this table sit just above the cursor.
        self.drawn = 0

    def start(self) -> None:
        global _live
        with _lock:
            if _live is None and self._is_terminal():
                _live = self
                self._write(lines(HEADING, {}))

    def update(self, recording: Recording) -> None:
        with _lock:
            if _live is self:
                self._write(lines(HEADING, recording.stages))

    def finish(self, heading: str, stages: dict[str, Totals]) -> None:
        global _live
        with _lock:
            if _live is self:
                _live = None
            elif _live is not None:
                # This table lands below the live one, which then continues in a new copy.
                _live.drawn = 0
            self._write(lines(heading, stages))

    def _is_terminal(self) -> bool:
        try:
            return self.stream.isatty()
        except ValueError:
            return False

    def _write(self, rows: list[str]) -> None:
        up, erase = (f"\x1b[{self.drawn}A\r", "\x1b[2K") if self.drawn else ("", "")
        try:
            self.stream.write(up + "".join(f"{erase}{row}\n" for row in rows))
            self.stream.flush()
        except (OSError, ValueError):
            # A closed terminal must not fail the run.
            pass
        self.drawn = len(rows)
