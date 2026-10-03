# Storage and API

## Files

Everything lives in one app data folder, which main passes to the server at launch.

| Item | Location |
|---|---|
| Original files | `materials/{lesson_id}/` |
| Stage outputs | `work/{lesson_id}/`: `pages.json` (routes and text per page), `normalized/`, `extraction.json`, `plan.json`, `outline.json`, `section-{n}.json`, `verification-{n}.json` |
| Lessons | `lessons/{lesson_id}.json` |
| Index and progress | SQLite database |

## Tables

| Table | Key fields |
|---|---|
| `lessons` | id, title, subject, status, current stage, schema version, revision, created, error, folder id |
| `folders` | id, name (unique, ignoring case), created |
| `settings` | key, value (for example, that the sample lesson was added on the first start) |
| `materials` | id, lesson id, filename, role, force transcription |
| `progress` | lesson id, block id, part id, status, last response, attempts, hints used, updated |
| `simulations` | lesson id, block id, regenerated code, flagged, error, updated |

- Lesson status is one of: generating, ready, failed. Only a ready lesson has lesson JSON to serve.
- Material role is problem set or reference.
- Progress status is one of: not started, in progress, correct, marked done.
- Progress is stored apart from the lesson JSON and keyed by block and part ID. A checkpoint has no part and is stored with an empty part ID.
- The database is `kedami.db` in the app data folder.

## API

All routes require the session token.

| Method | Path | Purpose |
|---|---|---|
| POST | `/lessons` | Multipart upload: `subject`, optional `folder`, and per file `files`, `roles`, `force`; starts the pipeline |
| DELETE | `/lessons/{id}` | Delete a lesson that isn't generating: its JSON, files, stage outputs, progress, and simulations |
| POST | `/lessons/{id}/move` | Move a lesson to a folder, or home with `null` |
| GET | `/folders` | Folders with their lesson counts |
| POST | `/folders` | Create a folder |
| DELETE | `/folders/{id}` | Delete a folder; its lessons move home |
| GET | `/lessons` | List lessons with status and progress |
| GET | `/lessons/{id}` | Lesson JSON plus generation status, current stage, error, materials, and the stages a rerun can start from |
| POST | `/lessons/{id}/rerun` | Rerun from a given stage, with force transcription per material ID |
| GET | `/lessons/{id}/blocks/{block_id}/points` | Sampled points for a static plot |
| POST | `/lessons/{id}/blocks/{block_id}/check` | Check a response for a part; records progress and returns the new state |
| POST | `/lessons/{id}/blocks/{block_id}/hint` | Record hints revealed for a part or checkpoint; returns the new state |
| POST | `/lessons/{id}/blocks/{block_id}/mark-done` | Mark a part done, or undo it |
| GET | `/lessons/{id}/blocks/{block_id}/simulation` | A simulation's current code (regenerated, or from the lesson JSON) and whether it is flagged |
| POST | `/lessons/{id}/blocks/{block_id}/simulation-status` | Record whether a simulation loaded; a failure flags it |
| POST | `/lessons/{id}/blocks/{block_id}/regenerate` | Write a simulation's code on request, or rewrite it; a flagged one's error is passed to the model |
| GET | `/lessons/{id}/progress` | Progress for all blocks and parts |
| GET | `/health` | Used by main to detect server readiness |
