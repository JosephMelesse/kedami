# Storage and API

## Files

Everything lives in one app data folder, which main passes to the server at launch.

| Item | Location |
|---|---|
| Original files | `materials/{lesson_id}/` |
| Stage outputs | `work/{lesson_id}/` (page routes, normalized text, extraction, plan) |
| Lessons | `lessons/{lesson_id}.json` |
| Index and progress | SQLite database |

## Tables

| Table | Key fields |
|---|---|
| `lessons` | id, title, subject, status, current stage, schema version, revision, created |
| `materials` | id, lesson id, filename, role, force transcription |
| `progress` | lesson id, block id, part id, status, last response, attempts, hints used, updated |

- Lesson status is one of: generating, ready, failed. Only a ready lesson has lesson JSON to serve.
- Material role is problem set or reference.
- Progress status is one of: not started, in progress, correct, marked done.
- Progress is stored apart from the lesson JSON and keyed by block and part ID. A checkpoint has no part and is stored with an empty part ID.
- The database is `kedami.db` in the app data folder.

## API

All routes require the session token.

| Method | Path | Purpose |
|---|---|---|
| POST | `/lessons` | Upload files with roles and toggles; starts the pipeline |
| GET | `/lessons` | List lessons with status and progress |
| GET | `/lessons/{id}` | Lesson JSON plus generation status and current stage |
| POST | `/lessons/{id}/rerun` | Rerun from a given stage, with updated file toggles |
| GET | `/lessons/{id}/blocks/{block_id}/points` | Sampled points for a static plot |
| POST | `/lessons/{id}/blocks/{block_id}/check` | Check a response for a part; records progress and returns the new state |
| POST | `/lessons/{id}/blocks/{block_id}/hint` | Record hints revealed for a part or checkpoint; returns the new state |
| POST | `/lessons/{id}/blocks/{block_id}/mark-done` | Mark a part done, or undo it |
| POST | `/lessons/{id}/blocks/{block_id}/regenerate` | Regenerate a simulation |
| GET | `/lessons/{id}/progress` | Progress for all blocks and parts |
| GET | `/health` | Used by main to detect server readiness |
