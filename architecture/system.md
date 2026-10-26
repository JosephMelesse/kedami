# System

## Processes

| Process | Responsibility | Stack |
|---|---|---|
| Electron renderer | UI only: file drop, lesson rendering, answer input, progress, sandboxed simulation frames, Pomodoro timer, music player | TypeScript, React, KaTeX, DOMPurify |
| Electron main | Window management; spawns and kills the server; passes the port and session token to the renderer; copies and serves music player tracks; runs the Terminal panel's pseudo-terminal | TypeScript, node-pty |
| Terminal view | The Terminal panel: draws the pseudo-terminal, in its own renderer process (see `agent-mode.md`) | TypeScript, xterm.js |
| Local server | Checks and stores what Claude Code builds, checks answers, keeps progress; writes the plugin, serves its routes, and runs Claude Code's background jobs. Makes no model calls | Python, FastAPI, SymPy, SQLite |
| MCP server | Kedami's tools for Claude Code, started by it in a job or the Terminal panel; each tool calls an agent route | Python, MCP SDK |

## Launch

1. Main picks a free port and generates a random session token.
2. Main spawns the server, passing the port, token, and app data folder.
3. Main polls `/health` until the server is ready, then opens the window.
4. Main kills the server on quit. The server also exits on its own if main dies.

- Main passes the port, token, and data folder to the server as environment variables (`KEDAMI_PORT`, `KEDAMI_TOKEN`, `KEDAMI_DATA_DIR`), never as arguments, which other local users can read.
- The renderer gets the port and token from main over IPC, for the same reason.
- The server allows cross-origin requests only from the renderer's own origin.

In development, both processes can be started by hand.

## Repository layout

| Path | Contents |
|---|---|
| `kedami/architecture/` | These documents |
| `kedami/app/` | Electron main and renderer |
| `kedami/data/` | App data folder during development (git-ignored) |
| `kedami/server/` | FastAPI server |

## Models

Kedami makes no model calls and holds no API key. The student's own Claude Code builds lessons and writes solutions and simulations, as background jobs on their Claude plan; see `agent-mode.md`.

| Who | Model | Used for |
|---|---|---|
| The student's Claude Code, in a job or the Terminal panel | The student's default Claude Code model | Reading the files, extraction, planning, sections, hints, solutions, simulations |
| The plugin's `verifier` subagent | `claude-opus-5-5` | The independent second solve that verification compares against |
| The plugin's `hint-checker` subagent | `claude-haiku-4-5` | Judging whether a hint gives the answer away |

- The subagents' models live in `SUBAGENT_MODELS` in `server/kedami_server/config.py`, and the plugin takes them from there.
- What Claude Code submits is checked against the lesson models and rules in the server, so the lesson format holds whatever model wrote it.
- Kedami records no usage: calls run on the student's plan.

## Security and privacy

- The server binds to `127.0.0.1` only and rejects requests without the session token.
- Kedami itself sends nothing over the network. Fonts and the alarm sound are bundled. Programs the student runs in the Terminal panel, Claude Code included, make their own connections.
- The Terminal panel is a separate view with its own preload. Main accepts pseudo-terminal input only from that view, so the lesson window can never type into a shell. See Isolation in `agent-mode.md`.
- Kedami never types into the terminal; the student drives Claude Code there. The server runs Claude Code itself only as the background jobs a button starts, each allowed only to read the data folder and call Kedami's tools. See Background jobs in `agent-mode.md`.
- Code Claude Code writes for a simulation runs only inside a sandboxed frame with no network, no Node access, and no access to app data. The skills tell Claude Code not to run it anywhere.
- Electron main cancels any renderer request that isn't to a local file, the music protocol, or `127.0.0.1` or `localhost`, frames included, as a backstop to the CSPs.
- The music protocol serves only audio files directly inside the data folder's `music/`. The renderer names a track by file name; main resolves it and refuses anything outside that folder. Simulation frames can't load media at all.
- Diagram SVG is sanitized with DOMPurify before rendering.
- All expression parsing uses a restricted parser with whitelisted names, for both model output and user input. SymPy's default string parsing evaluates code and must not be used directly.
