# Kedami

Kedami is a local-first desktop app that turns course material into one interactive lesson, sequenced so that finishing the lesson means the problem set is done. The MVP covers math and physics for a single user.

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

## Rules that must hold

**Boundaries**
- The renderer is UI only. It never calls the model API and never sees the API key.
- The server binds to `127.0.0.1` and rejects requests without the session token.
- The only outbound traffic is to the Anthropic API. Fonts and audio are bundled, never fetched.

**Model calls**
- All model calls go through one server function.
- Model names live in config, never hardcoded at call sites.

**Untrusted content**
- Model-written code runs only in a sandboxed frame with no network, no Node access, and no access to app data.
- Diagram SVG is sanitized with DOMPurify before rendering.
- Math strings are parsed only with the restricted, whitelisted parser. Never pass model or user input to SymPy's default string parsing or to `eval`.

**Lesson data**
- Lesson JSON is never edited in place. Only a rerun replaces it.
- Progress is stored apart from the lesson, keyed by block and part ID.
- The `verified` flag is set only by the server's verification pass.
- Problem block IDs derive from the source reference, and part IDs from the part label.

**UI**
- All colors come from the design tokens in `architecture/ui.md`.
- Feedback colors the border and a short label, never the whole card.

## Secrets and data

- The API key lives in `server/.env`. Never commit it, log it, or send it to the renderer.
- Never commit anything under `data/`.

## Most likely to be wrong

The lesson schema and ID derivation (`server/kedami_server/lesson.py`, `ids.py`) and the restricted math parser (`mathparse.py`). Every later step depends on them, so they get tests first and changes to them come with tests.

## Commands

### Server (`server/`)

```bash
cd server
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest
.venv/bin/python -m kedami_server.export_schema   # after changing lesson models, then run gen:types in app/
```

The server will not start without `KEDAMI_PORT`, `KEDAMI_TOKEN`, and `KEDAMI_DATA_DIR`. Electron main sets them. To start it by hand:

```bash
KEDAMI_PORT=8765 KEDAMI_TOKEN=dev KEDAMI_DATA_DIR=../data KEDAMI_ALLOWED_ORIGINS=http://localhost:5173 \
  .venv/bin/python -m kedami_server
```

On startup it copies `server/fixtures/sample-lesson.json` to `data/lessons/sample.json` if that file is missing. Delete the copy to pick up fixture edits.

### App (`app/`)

```bash
cd app
npm install          # also downloads the Electron binary
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
