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

## Commands

Add the install, run, and test commands for `app/` and `server/` here as they are created.
