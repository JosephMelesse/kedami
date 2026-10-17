"""Import the Spider exercise bank for SQL lessons into the data folder.

Run as `python -m kedami_server.import_spider DATA_DIR SPIDER_DATA_DIR`, with the folder from the Spider release
(the one holding train_spider.json). Writes `sql/databases/` and `sql/exercises.jsonl`, replacing any earlier
import. Every reference query runs here under the same rules as the student's. See architecture/sql-lessons.md,
Exercise bank.
"""

import hashlib
import json
import re
import shutil
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from .queries import QueryError, features, is_ordered, rollback_journal, run

BANK = "sql"
MAX_DATABASE = 5_000_000
MAX_ROWS = 200

# The splits whose databases and questions Spider's authors made. train_others.json comes from other datasets
# with their own terms, so it is left out.
SPLITS = (("train_spider.json", "database"), ("dev.json", "database"), ("test.json", "test_database"))


@dataclass
class Summary:
    kept: int
    databases: int
    dropped: Counter

    def __str__(self) -> str:
        lines = [f"kept {self.kept:,} exercises on {self.databases} databases, dropped {sum(self.dropped.values()):,}"]
        lines += [f"  {count:,}: {reason}" for reason, count in self.dropped.most_common()]
        return "\n".join(lines)


def import_bank(data_dir: Path, spider_dir: Path) -> Summary:
    exercises: dict[str, dict] = {}
    images: dict[str, bytes] = {}
    sources: dict[str, Path] = {}
    dropped: Counter = Counter()
    for questions, database_dir in SPLITS:
        path = spider_dir / questions
        if not path.is_file():
            continue
        for example in json.loads(path.read_text(encoding="utf-8")):
            db_id, query, question = example.get("db_id"), example.get("query"), example.get("question")
            if not all(isinstance(v, str) and v.strip() for v in (db_id, query, question)) or "/" in db_id:
                dropped["it isn't a complete exercise"] += 1
                continue
            source = spider_dir / database_dir / db_id / f"{db_id}.sqlite"
            if not source.is_file():
                dropped["its database is missing"] += 1
                continue
            if source.stat().st_size > MAX_DATABASE:
                dropped[f"its database is over {MAX_DATABASE // 1_000_000} MB"] += 1
                continue
            if sources.setdefault(db_id, source) != source:
                dropped["its database's name is used by another"] += 1
                continue
            normalized = re.sub(r"\s+", " ", query.strip().rstrip(";").strip()).lower()
            exercise_id = f"{db_id}-{hashlib.sha1(normalized.encode()).hexdigest()[:10]}"
            if exercise_id in exercises:
                dropped["it repeats another question's query"] += 1
                continue
            image = images.get(db_id) or images.setdefault(db_id, rollback_journal(source.read_bytes()))
            try:
                result = run(image, query)
            except QueryError:
                dropped["its query doesn't run here"] += 1
                continue
            if not result.rows:
                dropped["its query returns no rows"] += 1
                continue
            if result.truncated or len(result.rows) > MAX_ROWS:
                dropped[f"its query returns over {MAX_ROWS} rows"] += 1
                continue
            exercises[exercise_id] = {
                "id": exercise_id,
                "database": db_id,
                "question": " ".join(question.split()),
                "query": query.strip(),
                "ordered": is_ordered(query),
                "features": sorted(features(query)),
            }
    used = {e["database"] for e in exercises.values()}
    _write(data_dir, [exercises[i] for i in sorted(exercises)], {db: images[db] for db in sorted(used)})
    return Summary(len(exercises), len(used), dropped)


def _write(data_dir: Path, exercises: list[dict], databases: dict[str, bytes]) -> None:
    # Built beside the bank and swapped in, so a failed import leaves the earlier one whole.
    target = data_dir / BANK
    partial = data_dir / f"{BANK}.partial"
    shutil.rmtree(partial, ignore_errors=True)
    (partial / "databases").mkdir(parents=True)
    for db_id, image in databases.items():
        (partial / "databases" / f"{db_id}.sqlite").write_bytes(image)
    with (partial / "exercises.jsonl").open("w", encoding="utf-8") as out:
        for exercise in exercises:
            out.write(json.dumps(exercise) + "\n")
    old = data_dir / f"{BANK}.old"
    shutil.rmtree(old, ignore_errors=True)
    if target.exists():
        target.rename(old)
    partial.rename(target)
    shutil.rmtree(old, ignore_errors=True)


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: python -m kedami_server.import_spider DATA_DIR SPIDER_DATA_DIR")
    data_dir, spider_dir = Path(sys.argv[1]), Path(sys.argv[2])
    if not data_dir.is_dir():
        raise SystemExit(f"no data folder at {data_dir}")
    if not (spider_dir / "train_spider.json").is_file():
        raise SystemExit(f"no train_spider.json in {spider_dir}; pass the spider_data folder from the release")
    print(import_bank(data_dir, spider_dir))


if __name__ == "__main__":
    main()
