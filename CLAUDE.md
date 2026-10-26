# Kedami

Kedami is a local-first desktop app that turns course material into one interactive lesson, sequenced so that finishing the lesson means the problem set is done. The student's own Claude Code builds each lesson as a background job started from a button; Kedami makes no model calls. The MVP covers math, physics, and a general subject for any other course, for a single user. Computer science lessons are not opened, and new ones can't be created.

## Read first

Before writing code, read `README.md` and every file in `architecture/`. Those documents are the source of truth.

- If a document is ambiguous or silent on something, ask before deciding.
- If an implementation needs to differ from a document, say so and propose the document change. Don't diverge silently.

## How to work

- Follow the build order in `architecture/roadmap.md`, one step at a time.
- Finish and demonstrate a step before starting the next.
- Don't build anything listed in the backlog, and don't add features that aren't in the documents.

## Layout

| Path | Contents |
|---|---|
| `architecture/` | Design documents |
| `app/` | Electron main and renderer (TypeScript, React) |
| `server/` | Local server (Python, FastAPI, SymPy, SQLite) |
| `data/` | App data folder during development (git-ignored) |
| `research/` | Research notes, such as the cost of generating a lesson (git-ignored) |

## Rules that must hold

**Boundaries**
- The renderer is UI only.
- The server binds to `127.0.0.1` and rejects requests without the session token.
- Kedami itself sends nothing over the network. Fonts and audio are bundled, never fetched. Programs the student runs in the Terminal panel, Claude Code included, are their own.
- The terminal is a separate view, and main accepts pseudo-terminal input only from it. The lesson window can never type into a shell.
- Kedami never types into the terminal; the student drives Claude Code there.
- The server runs Claude Code itself only as the background jobs in `architecture/agent-mode.md`, each started by a button, one at a time, and allowed only to read the data folder and call Kedami's tools. Never widen those limits.

**Models**
- Kedami makes no model calls and holds no API key. Claude Code builds lessons and writes solutions and simulations, through the plugin and the MCP server.
- The plugin's subagent models live in `SUBAGENT_MODELS` in config, never hardcoded elsewhere.
- In the build, the server is the only writer. The MCP server holds no state and touches no files.

**Untrusted content**
- Code Claude Code writes for a simulation runs only in a sandboxed frame with no network, no Node access, and no access to app data.
- Diagram SVG is sanitized with DOMPurify before rendering.
- Math strings are parsed only with the restricted, whitelisted parser. Never pass Claude Code's or the student's input to SymPy's default string parsing or to `eval`.

**Lesson data**
- Lesson JSON is never edited or replaced once written. Simulation code, and simulations the student adds, are stored apart from it.
- Progress is stored apart from the lesson, keyed by block and part ID.
- The `verified` flag is set only by the server, comparing a stored answer with the verifier subagent's second solve.
- Problem block IDs derive from the source reference, and part IDs from the part label.

**UI**
- All colors come from the design tokens in `architecture/ui.md`.
- Feedback colors the border and a short label, never the whole card.

## Secrets and data

- Never commit anything under `data/`.

## Most likely to be wrong

The lesson schema and ID derivation (`server/kedami_server/lesson.py`, `ids.py`), the restricted math parser (`mathparse.py`), the draft lesson Claude Code builds, assembled across many tool calls, and the job runner (see `architecture/agent-mode.md`). Every later step depends on them, so they get tests first and changes to them come with tests.

## Commands

### Server (`server/`)

```bash
cd server
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest
.venv/bin/python -m kedami_server.export_schema   # after changing lesson models, then run gen:types in app/
```

The server will not start without `KEDAMI_PORT`, `KEDAMI_TOKEN`, and `KEDAMI_DATA_DIR`. Electron main sets them. It needs no API key. To start it by hand:

```bash
KEDAMI_PORT=8765 KEDAMI_TOKEN=dev KEDAMI_DATA_DIR=../data KEDAMI_ALLOWED_ORIGINS=http://localhost:5000 \
  .venv/bin/python -m kedami_server
```

On startup it copies `server/fixtures/sample-lesson.json` to `data/lessons/sample.json` if that file is missing, and indexes it. Delete the copy to pick up fixture edits. Lessons and progress live in `data/kedami.db`; delete it to reset progress.

### App (`app/`)

```bash
cd app
npm install          # also downloads the Electron binary, and builds node-pty (needs a C++ toolchain on Linux)
npm run dev          # builds, spawns the server, opens the window, hot reloads the renderer
npm start            # runs the production build
npm test
npm run typecheck
npm run gen:types    # regenerates src/renderer/src/lesson/types.ts from the server schema
```

- `npm run dev` expects the server venv at `server/.venv`. Override with `KEDAMI_PYTHON`. The data folder defaults to `data/`; override with `KEDAMI_DATA_DIR`.
- To use a server started by hand, run `KEDAMI_PORT=8765 KEDAMI_TOKEN=dev npm run dev`.
- On Ubuntu 24.04 and later, Electron aborts until its sandbox helper is owned by root. Run this once, and again after reinstalling Electron:

```bash
sudo chown root:root app/node_modules/electron/dist/chrome-sandbox
sudo chmod 4755 app/node_modules/electron/dist/chrome-sandbox
```
