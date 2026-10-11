"""Print the run log as Markdown: a row per run, then each run in full.

Run as `python -m kedami_server.run_report DATA_DIR`. See architecture/system.md, Run log.
"""

import sys
from datetime import UTC, datetime
from pathlib import Path

from . import run_log, usage

# Kinds of token, as a record's usage and prices name them, costliest first in a typical run.
KINDS = (("Output", "output"), ("Cache write", "cache_write"), ("Input", "input"), ("Cache read", "cache_read"))
MEASURES = ("calls", "latency_ms", "cost", "unpriced")


def report(data_dir: Path) -> str:
    runs = run_log.read(data_dir)
    if not runs:
        return "No runs recorded."
    summary = _table(
        ["#", "Started", "Lesson", "From stage", "Outcome", "Calls", "Wall time", "Cost"],
        [
            [
                number,
                _when(run),
                _title(run),
                run["start_stage"],
                run["outcome"],
                _sum(run["usage"])["calls"],
                usage.duration(run["wall_ms"] / 1000),
                _cost(_sum(run["usage"])),
            ]
            for number, run in enumerate(runs, start=1)
        ],
    )
    return "\n\n".join(["# Run log", summary, *(_run(number, run) for number, run in enumerate(runs, start=1))])


def _run(number: int, run: dict) -> str:
    lesson, material, total = run["lesson"], run["material"], _sum(run["usage"])
    outcome = "ready" if run["outcome"] == "ready" else f"failed in {run['failed_stage']}"
    files = ", ".join(f"{f['filename']} ({f['role'].replace('_', ' ')})" for f in material["files"])
    facts = [
        f"Outcome: {outcome}, {'rerun' if run['rerun'] else 'run'} from stage {run['start_stage']}",
        f"Code: {_code(run)}",
        f"Lesson: {lesson['subject']}, {lesson['id']}",
        f"Material: {files or 'none'}",
    ]
    if material["pages_kept"] is not None:
        facts.append(
            f"Read: {_n(material['pages_kept'], 'page')} kept as text, {material['pages_transcribed']} transcribed, "
            f"{material['normalized_chars']:,} characters of normalized text"
        )
    if lesson["sections"] is not None:
        facts.append(
            f"Made: {_n(lesson['sections'], 'section')}, {_n(lesson['blocks'], 'block')}, "
            f"{_n(lesson['problems'], 'problem')} ({_n(lesson['parts'], 'part')}), "
            f"{lesson['verified']} of {lesson['verifiable']} answers verified"
        )
    facts.append(
        f"Took: {_n(total['calls'], 'call')}, {usage.duration(run['wall_ms'] / 1000)} wall time, "
        f"{usage.duration(total['latency_ms'] / 1000)} model time, {_cost(total)}"
    )
    parts = [f"## {number}. {_title(run)} ({_when(run)})", "\n".join(f"- {fact}" for fact in facts)]
    if run["error"]:
        # An indented block, so whatever the message holds shows as written.
        parts += ["Why it failed:", "\n".join(f"    {line}" for line in run["error"].splitlines())]
    if run["usage"]:
        parts += [_by(run, "Stage", ("stage",)), _by(run, "Role", ("role", "model")), _by_kind(run)]
    return "\n\n".join(parts)


def _by(run: dict, heading: str, keys: tuple[str, ...]) -> str:
    """Usage added up by stage, or by role and model, in the order first seen."""
    total = _sum(run["usage"])
    found: dict[tuple, list[dict]] = {}
    for group in run["usage"]:
        found.setdefault(tuple(group[key] for key in keys), []).append(group)
    rows = []
    for names, groups in found.items():
        part = _sum(groups)
        time = usage.duration(part["latency_ms"] / 1000)
        rows.append([*names, part["calls"], time, _cost(part), _share(part["cost"], total["cost"])])
    header = [heading, "Model"] if len(keys) == 2 else [heading]
    return _table([*header, "Calls", "Model time", "Cost", "Share"], rows)


def _by_kind(run: dict) -> str:
    """Tokens of each kind, costed at the prices recorded with the run."""
    total = _sum(run["usage"])
    rows = []
    for name, kind in KINDS:
        tokens = sum(group[f"{kind}_tokens"] for group in run["usage"])
        cost = sum(
            group[f"{kind}_tokens"] * run["prices"][group["model"]][kind] / 1_000_000
            for group in run["usage"]
            if group["model"] in run["prices"]
        )
        rows.append([name, f"{tokens:,}", f"${cost:,.3f}", _share(cost, total["cost"])])
    return _table(["Kind", "Tokens", "Cost", "Share"], rows)


def _sum(groups: list[dict]) -> dict:
    return {measure: sum(group[measure] for group in groups) for measure in MEASURES}


def _cost(total: dict) -> str:
    cost = f"${total['cost']:,.3f}"
    return f"{cost} plus {total['unpriced']} with no listed price" if total["unpriced"] else cost


def _n(count: int, noun: str) -> str:
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


def _share(part: float, whole: float) -> str:
    return f"{part / whole:.1%}" if whole else ""


def _code(run: dict) -> str:
    if run["commit"] is None:
        return "not recorded"
    return f"commit {run['commit']}" + (", with uncommitted changes" if run["dirty"] else "")


def _title(run: dict) -> str:
    return run["lesson"]["title"] or run["lesson"]["id"]


def _when(run: dict) -> str:
    return datetime.fromisoformat(run["started"]).astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")


def _table(header: list[str], rows: list[list]) -> str:
    lines = [header, ["---"] * len(header), *rows]
    return "\n".join("| " + " | ".join(_cell(value) for value in line) + " |" for line in lines)


def _cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m kedami_server.run_report DATA_DIR")
    data_dir = Path(sys.argv[1])
    if not data_dir.is_dir():
        raise SystemExit(f"no data folder at {data_dir}")
    print(report(data_dir))


if __name__ == "__main__":
    main()
