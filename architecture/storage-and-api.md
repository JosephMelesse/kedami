# Storage and API

## Files

Everything lives in one app data folder, which main passes to the server at launch.

| Item | Location |
|---|---|
| Original files | `materials/{lesson_id}/` |
| Stage outputs | `work/{lesson_id}/`: `pages.json` (routes and text per page), `normalized/`, `extraction.json`, `plan.json`, `outline.json`, `section-{n}.json`, `verification-{n}.json` |
| Lessons | `lessons/{lesson_id}.json` |
| Music player tracks | `music/`, written and read only by Electron main |
| LeetCode tests | `leetcode.jsonl`: the imported dataset (see `code-problems.md`). Written only by the import command; a lesson copies what it needs into its lesson JSON |
| SQL exercise bank | `sql/databases/` and `sql/exercises.jsonl`: the imported Spider bank (see `sql-lessons.md`). Written only by the import command |
| Run log | `runs.jsonl`: one line per pipeline run (see Run log in `system.md`). Deleting a lesson or the database keeps it |
| Index and progress | SQLite database |

## Tables

| Table | Key fields |
|---|---|
| `lessons` | id, title, custom title, subject, domain, chapter (a SQL chapter lesson's), status, current stage, schema version, revision, created, error, folder id, reading block, day starts, active |
| `folders` | id, name (unique, ignoring case), created |
| `settings` | key, value (for example, that the sample lesson was added on the first start) |
| `materials` | id, lesson id, filename, role, force transcription |
| `progress` | lesson id, block id, part id, status, last response, attempts, hints used, updated |
| `simulations` | lesson id, block id, regenerated code, flagged, error, updated |
| `solutions` | lesson id, block id, part id, solution JSON, matches stored answer, updated |
| `test_flags` | lesson id, block id, part id, test (arguments and expected value), created |
| `model_calls` | id, lesson id, stage, role, model, started, latency in ms, input tokens, output tokens, cache write tokens, cache read tokens, cost in USD |

- Lesson status is one of: generating, ready, failed. Only a ready lesson has lesson JSON to serve.
- A lesson's title is the plan's until the student renames it. The custom title is kept in the index and served in place of the lesson JSON's title, which is never edited, and a rerun keeps it.
- Material role is problem set or reference. A SQL lesson's course database is kept beside its materials, not as one (see Course databases in `sql-lessons.md`).
- Progress status is one of: not started, in progress, correct, marked done.
- Progress is stored apart from the lesson JSON and keyed by block and part ID. A checkpoint has no part and is stored with an empty part ID. For a code part, the last response is the saved code.
- The reading block is the ID of the block the student was last reading (see Reading position in `ui.md`). A rerun keeps it, and deleting the lesson removes it.
- Day starts are the IDs of the blocks that begin day 2 onward, in lesson order (see Finish lines in `ui.md`). Splitting again replaces them, a rerun drops any whose block is gone, and deleting the lesson removes them.
- Active marks a lesson the student is working through (see Active lessons in `ui.md`). New lessons start inactive, a rerun keeps it, and deleting the lesson removes it.
- `model_calls` is the usage log: one row per model call that got a reply (see Usage log in `system.md`). Cost is empty when a model has no listed price. Rows are only added, never changed, and a rerun keeps them.
- The database is `kedami.db` in the app data folder.

## API

All routes require the session token.

| Method | Path | Purpose |
|---|---|---|
| POST | `/lessons` | Multipart upload: `subject`, `domain` for computer science, `chapter` for a SQL chapter lesson, optional `folder`, and per file `files`, `roles`, `force`; starts the pipeline |
| GET | `/sql/chapters` | The SQL chapters, each with how many problems it can recommend |
| POST | `/sql/recommend` | Recommend problems for a SQL chapter: a chapter, a number, and how many times Recommend again was pressed |
| POST | `/sql/database` | Check an uploaded course database without keeping it; returns its tables with their row counts, or why it was refused |
| GET | `/leetcode/search?q=` | Up to 8 imported LeetCode problems matching a number or words, each with number, slug, title, and difficulty |
| DELETE | `/lessons/{id}` | Delete a lesson that isn't generating: its JSON, files, stage outputs, progress, simulations, solutions, test flags, and usage log |
| POST | `/lessons/{id}/rename` | Rename a lesson |
| POST | `/lessons/{id}/active` | Mark a ready lesson active or not |
| POST | `/lessons/{id}/move` | Move a lesson to a folder, or home with `null` |
| GET | `/folders` | Folders with their lesson counts |
| POST | `/folders` | Create a folder |
| POST | `/folders/{id}/rename` | Rename a folder |
| DELETE | `/folders/{id}` | Delete a folder; its lessons move home |
| GET | `/lessons` | List lessons with status, progress, and whether each is active |
| GET | `/lessons/{id}` | Lesson JSON plus generation status, current stage, error, materials, the stages a rerun can start from, the reading block, and the day starts |
| POST | `/lessons/{id}/reading-position` | Record the block being read; it must be a block in the lesson |
| POST | `/lessons/{id}/days` | Replace the day starts; each must be a block in the lesson other than the first, in lesson order, with no repeats. An empty list removes them |
| POST | `/lessons/{id}/rerun` | Rerun from a given stage, with force transcription per material ID |
| GET | `/lessons/{id}/blocks/{block_id}/points` | Sampled points for a static plot |
| POST | `/lessons/{id}/blocks/{block_id}/check` | Check a response for a part; records progress and returns the new state. For a query, also the reason it is wrong and the student's result |
| POST | `/lessons/{id}/blocks/{block_id}/code` | Save a code part's code, or a query part's or checkpoint's query, as it is typed; returns the new state |
| POST | `/lessons/{id}/blocks/{block_id}/submit` | Record a code part's Submit: the code and whether every unflagged test passed; returns the new state |
| POST | `/lessons/{id}/blocks/{block_id}/flags` | Flag or unflag a code part's test, or clear its flags |
| GET | `/lessons/{id}/blocks/{block_id}/tables` | The tables of a query part's or checkpoint's database: columns, the first 20 rows, and the row count |
| POST | `/lessons/{id}/blocks/{block_id}/run-query` | Run a query part's or checkpoint's query against its database without checking it; returns columns, at most 100 rows, the row count, and any error |
| POST | `/lessons/{id}/blocks/{block_id}/hint` | Record hints revealed for a part or checkpoint; returns the new state |
| POST | `/lessons/{id}/blocks/{block_id}/mark-done` | Mark a part done, or undo it |
| GET | `/lessons/{id}/blocks/{block_id}/simulation` | A simulation's current code (regenerated, or from the lesson JSON) and whether it is flagged |
| POST | `/lessons/{id}/blocks/{block_id}/simulation-status` | Record whether a simulation loaded; a failure flags it |
| POST | `/lessons/{id}/blocks/{block_id}/regenerate` | Write a simulation's code on request, or rewrite it; a flagged one's error is passed to the model |
| POST | `/lessons/{id}/blocks/{block_id}/solution` | A problem part's solution: the stored one, or written on request the first time |
| GET | `/lessons/{id}/progress` | Progress for all blocks and parts, with code parts' saved code and test flags |
| GET | `/health` | Used by main to detect server readiness |
