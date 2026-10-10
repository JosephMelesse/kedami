"""Print what each lesson's model calls took: its total, then each stage.

Run as `python -m kedami_server.usage_report DATA_DIR`. See architecture/system.md, Usage log.
"""

import sys
from pathlib import Path

from . import db, usage


def report(data_dir: Path) -> str:
    lines: list[str] = []
    with db.connect(data_dir) as conn:
        lessons = conn.execute(
            "SELECT id, COALESCE(custom_title, title) AS title FROM lessons ORDER BY created"
        ).fetchall()
        for lesson in lessons:
            stages = usage.by_stage(conn, lesson["id"])
            if not stages:
                continue
            lines.append(f"{lesson['title']} ({lesson['id']})")
            lines.append(f"  total: {usage.describe(sum(stages.values(), usage.Totals()))}")
            lines += [f"  {stage}: {usage.describe(totals)}" for stage, totals in stages.items()]
            lines.append("")
    return "\n".join(lines).rstrip() or "No model calls recorded."


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m kedami_server.usage_report DATA_DIR")
    data_dir = Path(sys.argv[1])
    if not db.db_path(data_dir).exists():
        raise SystemExit(f"no database in {data_dir}")
    # A database last opened by an older server has no usage table yet.
    db.init(data_dir)
    print(report(data_dir))


if __name__ == "__main__":
    main()
