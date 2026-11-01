"""Rebuilding tables without losing folders, lessons, or progress. See storage-and-api.md."""

import sqlite3

import pytest

from kedami_server import db, library, migrations

# The tables as they were before folders could nest, in the column order a long-lived database has:
# later columns come after the first ones because they were added with ALTER TABLE.
OLD_SCHEMA = """
CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE folders (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    created TEXT NOT NULL
);
CREATE TABLE lessons (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    subject TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('generating', 'ready', 'failed')),
    current_stage INTEGER,
    schema_version INTEGER NOT NULL,
    revision INTEGER NOT NULL DEFAULT 1,
    created TEXT NOT NULL,
    error TEXT,
    folder_id INTEGER REFERENCES folders (id) ON DELETE SET NULL,
    custom_title TEXT,
    reading_block TEXT,
    day_starts TEXT,
    active INTEGER NOT NULL DEFAULT 0,
    domain TEXT,
    chapter INTEGER
);
CREATE TABLE progress (
    lesson_id TEXT NOT NULL REFERENCES lessons (id) ON DELETE CASCADE,
    block_id TEXT NOT NULL,
    part_id TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL,
    last_response TEXT,
    attempts INTEGER NOT NULL DEFAULT 0,
    hints_used INTEGER NOT NULL DEFAULT 0,
    updated TEXT NOT NULL,
    PRIMARY KEY (lesson_id, block_id, part_id)
);
INSERT INTO folders VALUES (2, 'Physics', '2026-01-01'), (7, 'Calculus', '2026-01-02');
INSERT INTO lessons (id, title, subject, status, schema_version, created, folder_id, custom_title, active)
    VALUES ('in-folder', 'A', 'physics', 'ready', 1, '2026-01-03', 7, 'Mine', 1),
           ('at-home', 'B', 'math', 'failed', 1, '2026-01-04', NULL, NULL, 0);
INSERT INTO progress VALUES ('in-folder', 'ps1-1', 'a', 'correct', '8.66', 2, 1, '2026-01-05');
"""


@pytest.fixture
def old_database(tmp_path):
    conn = sqlite3.connect(tmp_path / "kedami.db")
    conn.executescript(OLD_SCHEMA)
    conn.close()
    return tmp_path


def rows(data_dir, query):
    with db.connect(data_dir) as conn:
        return [tuple(row) for row in conn.execute(query).fetchall()]


def test_existing_folders_stay_at_the_top_level_with_their_lessons_and_progress(old_database):
    db.init(old_database)
    assert rows(old_database, "SELECT id, name, parent_id, created FROM folders ORDER BY id") == [
        (2, "Physics", None, "2026-01-01"),
        (7, "Calculus", None, "2026-01-02"),
    ]
    assert rows(old_database, "SELECT id, folder_id, custom_title, active FROM lessons ORDER BY id") == [
        ("at-home", None, None, 0),
        ("in-folder", 7, "Mine", 1),
    ]
    assert rows(old_database, "SELECT lesson_id, part_id, last_response, attempts FROM progress") == [
        ("in-folder", "a", "8.66", 2)
    ]


def test_foreign_keys_still_hold_after_the_rebuild(old_database):
    db.init(old_database)
    assert rows(old_database, "PRAGMA foreign_key_check") == []
    with db.connect(old_database) as conn:
        library.delete_folder(conn, 7)
        assert conn.execute("SELECT folder_id FROM lessons WHERE id = 'in-folder'").fetchone()[0] is None


def test_names_are_unique_within_a_parent_after_the_rebuild(old_database):
    db.init(old_database)
    with db.connect(old_database) as conn:
        assert library.create_folder(conn, "Physics", parent_id=7).parent_id == 7
        with pytest.raises(library.FolderExists):
            library.create_folder(conn, "PHYSICS")
        with pytest.raises(library.FolderExists):
            library.create_folder(conn, "physics", parent_id=7)


def test_a_repeat_start_changes_nothing(old_database):
    db.init(old_database)
    with db.connect(old_database) as conn:
        library.create_folder(conn, "Week 1", parent_id=2)
    before = rows(old_database, "SELECT * FROM folders ORDER BY id")
    backup = (old_database / "kedami.db.before-subfolders").read_bytes()
    db.init(old_database)
    db.init(old_database)
    assert rows(old_database, "SELECT * FROM folders ORDER BY id") == before
    assert (old_database / "kedami.db.before-subfolders").read_bytes() == backup


def test_the_first_run_saves_a_copy_of_the_old_database(old_database):
    db.init(old_database)
    copy = sqlite3.connect(old_database / "kedami.db.before-subfolders")
    assert copy.execute("SELECT id, name FROM folders ORDER BY id").fetchall() == [(2, "Physics"), (7, "Calculus")]
    assert copy.execute("SELECT COUNT(*) FROM progress").fetchone()[0] == 1
    assert "parent_id" not in [row[1] for row in copy.execute("PRAGMA table_info(folders)")]
    copy.close()


def test_a_failed_rebuild_leaves_the_database_as_it_was(old_database, monkeypatch):
    def broken(conn):
        conn.execute("DROP TABLE folders")
        raise RuntimeError("disk full")

    monkeypatch.setattr(migrations, "MIGRATIONS", [("subfolders", migrations._folders_are_flat, broken)])
    with pytest.raises(RuntimeError):
        migrations.run(old_database / "kedami.db")
    conn = sqlite3.connect(old_database / "kedami.db")
    assert conn.execute("SELECT id, name FROM folders ORDER BY id").fetchall() == [(2, "Physics"), (7, "Calculus")]
    assert conn.execute("SELECT folder_id FROM lessons WHERE id = 'in-folder'").fetchone()[0] == 7
    conn.close()


def test_a_rebuild_that_loses_a_row_is_rolled_back(old_database, monkeypatch):
    def loses_a_row(conn):
        conn.execute("DELETE FROM folders WHERE id = 2")

    monkeypatch.setattr(migrations, "MIGRATIONS", [("subfolders", migrations._folders_are_flat, loses_a_row)])
    with pytest.raises(migrations.MigrationError):
        migrations.run(old_database / "kedami.db")
    conn = sqlite3.connect(old_database / "kedami.db")
    assert conn.execute("SELECT COUNT(*) FROM folders").fetchone()[0] == 2
    conn.close()


def test_a_new_database_needs_no_migration_and_saves_no_copy(tmp_path):
    db.init(tmp_path)
    assert [path.name for path in tmp_path.iterdir()] == ["kedami.db"]
    with db.connect(tmp_path) as conn:
        assert library.create_folder(conn, "Week 1").parent_id is None


def test_a_database_older_than_folders_still_starts(tmp_path):
    conn = sqlite3.connect(tmp_path / "kedami.db")
    conn.execute(
        "CREATE TABLE lessons (id TEXT PRIMARY KEY, title TEXT NOT NULL, subject TEXT NOT NULL, status TEXT NOT NULL,"
        " current_stage INTEGER, schema_version INTEGER NOT NULL, revision INTEGER NOT NULL DEFAULT 1,"
        " created TEXT NOT NULL)"
    )
    conn.execute("INSERT INTO lessons VALUES ('old', 'Old', 'math', 'ready', NULL, 1, 1, '2026-01-01')")
    conn.commit()
    conn.close()
    db.init(tmp_path)
    assert rows(tmp_path, "SELECT id, folder_id FROM lessons") == [("old", None)]
