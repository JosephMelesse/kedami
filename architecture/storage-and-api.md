# Storage and API

## Files

Everything lives in one app data folder, which main passes to the server at launch.

| Item | Location |
|---|---|
| Original files | `materials/{lesson_id}/` |
| Stage outputs | `work/{lesson_id}/`: `pages.json` (text per page), `normalized/`, `extraction.json`, `plan.json`, `outline.json`, `section-{n}.json`, `verification-{n}.json` |
| Lessons | `lessons/{lesson_id}.json` |
| Music player tracks | `music/`, written and read only by Electron main |
| Plugin | `agent-plugin/`: the Claude Code plugin that builds lessons, rewritten by the server on every start (see `agent-mode.md`) |
| LeetCode tests | `leetcode.jsonl`: the imported dataset, for computer science lessons made earlier (see `code-problems.md`). Written only by the import command, which applies the checked-in fixes. A lesson is served the import's current tests while the problem is imported (see In a lesson in `code-problems.md`) |
| SQL exercise bank | `sql/databases/` and `sql/exercises.jsonl`: the imported Spider bank, whose databases SQL lessons made earlier check queries against (see `sql-lessons.md`). Written only by the import command |
| Index and progress | SQLite database |

## Tables

| Table | Key fields |
|---|---|
| `lessons` | id, title, custom title, subject, domain, chapter (a SQL chapter lesson's), builder, status, current stage, schema version, revision, created, error, folder id, reading block, day starts, active |
| `folders` | id, name (unique, ignoring case), created |
| `settings` | key, value (for example, that the sample lesson was added on the first start) |
| `materials` | id, lesson id, filename, role (force transcription is a leftover of the API pipeline, always off) |
| `progress` | lesson id, block id, part id, status, last response, attempts, hints used, updated |
| `simulations` | lesson id, block id, code Claude Code wrote, flagged, error, updated |
| `solutions` | lesson id, block id, part id, solution JSON, matches stored answer, updated |
| `test_flags` | lesson id, block id, part id, test (arguments and expected value), created |

- Lesson status is one of: generating, ready, failed. Only a ready lesson has lesson JSON to serve.
- Builder is `agent` for every lesson Claude Code builds (see `agent-mode.md`), and `pipeline` for one the old API pipeline made. A lesson waiting for Claude Code is generating with no current stage.
- A lesson's title is the plan's until the student renames it. The custom title is kept in the index and served in place of the lesson JSON's title, which is never edited.
- Material role is problem set or reference. A SQL lesson made earlier may have a course database kept beside its materials, not as one (see Course databases in `sql-lessons.md`).
- Progress status is one of: not started, in progress, correct, marked done.
- Progress is stored apart from the lesson JSON and keyed by block and part ID. A checkpoint has no part and is stored with an empty part ID. For a code part, the last response is the saved code.
- The reading block is the ID of the block the student was last reading (see Reading position in `ui.md`). Deleting the lesson removes it.
- Day starts are the IDs of the blocks that begin day 2 onward, in lesson order (see Finish lines in `ui.md`). Splitting again replaces them, and deleting the lesson removes them.
- Active marks a lesson the student is working through (see Active lessons in `ui.md`). New lessons start inactive, and deleting the lesson removes it.
- The database is `kedami.db` in the app data folder.

## API

All routes require the session token.

| Method | Path | Purpose |
|---|---|---|
| POST | `/lessons` | Multipart upload: `subject` (math, physics, or general), optional `folder`, and per file `files` and `roles`; saves the files and leaves the lesson waiting for Claude Code |
| DELETE | `/lessons/{id}` | Delete a lesson that isn't generating: its JSON, files, stage outputs, progress, simulations, solutions, and test flags |
| POST | `/lessons/{id}/rename` | Rename a lesson |
| POST | `/lessons/{id}/active` | Mark a ready lesson active or not |
| POST | `/lessons/{id}/move` | Move a lesson to a folder, or home with `null` |
| GET | `/folders` | Folders with their lesson counts |
| POST | `/folders` | Create a folder |
| POST | `/folders/{id}/rename` | Rename a folder |
| DELETE | `/folders/{id}` | Delete a folder; its lessons move home |
| GET | `/lessons` | List lessons with status, progress, and whether each is active |
| GET | `/lessons/{id}` | Lesson JSON plus who built it, generation status, current stage, error, materials, the reading block, and the day starts |
| POST | `/lessons/{id}/reading-position` | Record the block being read; it must be a block in the lesson |
| POST | `/lessons/{id}/days` | Replace the day starts; each must be a block in the lesson other than the first, in lesson order, with no repeats. An empty list removes them |
| POST | `/lessons/{id}/cancel` | End a generating lesson's build, marking it failed with "Canceled" |
| GET | `/lessons/{id}/blocks/{block_id}/points` | Sampled points for a static plot |
| POST | `/lessons/{id}/blocks/{block_id}/check` | Check a response for a part; records progress and returns the new state. For a query, also the reason it is wrong and the student's result |
| POST | `/lessons/{id}/blocks/{block_id}/code` | Save a code part's code, or a query part's or checkpoint's query, as it is typed; returns the new state |
| POST | `/lessons/{id}/blocks/{block_id}/submit` | Record a code part's Submit: the code and whether every unflagged test passed; returns the new state |
| POST | `/lessons/{id}/blocks/{block_id}/flags` | Flag or unflag a code part's test, or clear its flags |
| GET | `/lessons/{id}/blocks/{block_id}/tables` | The tables of a query part's or checkpoint's database: columns, the first 20 rows, and the row count |
| POST | `/lessons/{id}/blocks/{block_id}/run-query` | Run a query part's or checkpoint's query against its database without checking it; returns columns, at most 100 rows, the row count, and any error |
| POST | `/lessons/{id}/blocks/{block_id}/hint` | Record hints revealed for a part or checkpoint; returns the new state |
| POST | `/lessons/{id}/blocks/{block_id}/mark-done` | Mark a part done, or undo it |
| GET | `/lessons/{id}/blocks/{block_id}/simulation` | A simulation's current code (Claude Code's, or the lesson JSON's empty code) and whether it is flagged |
| POST | `/lessons/{id}/blocks/{block_id}/simulation-status` | Record whether a simulation loaded; a failure flags it |
| GET | `/lessons/{id}/blocks/{block_id}/solution?part_id=` | A problem part's solution once Claude Code has written it, or null until then |
| GET | `/lessons/{id}/progress` | Progress for all blocks and parts, with code parts' saved code and test flags |
| GET | `/health` | Used by main to detect server readiness |

Routes under `/agent/` are called only by the MCP server; they are listed in `agent-mode.md`.
