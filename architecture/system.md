# System

## Processes

| Process | Responsibility | Stack |
|---|---|---|
| Electron renderer | UI only: file drop, lesson rendering, answer input, progress, sandboxed simulation frames, Pomodoro timer, music player | TypeScript, React, KaTeX, DOMPurify |
| Electron main | Window management; spawns and kills the server; passes the port and session token to the renderer; copies and serves music player tracks | TypeScript |
| Local server | Ingestion, model calls, verification, answer checking, storage | Python, FastAPI, SymPy, SQLite |

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

## Model roles

Anthropic is the only provider.

| Role | Model | Used for |
|---|---|---|
| Generate | `claude-sonnet-5-5` at high effort | Extraction, planning, lesson sections, hints, simulations |
| Transcribe | `claude-opus-5-5` at medium effort | Turning flagged pages into Markdown with LaTeX |
| Second solve | `claude-opus-5-5` at high effort | Independent solution for verification |
| Solution | `claude-opus-5-5` at high effort | Step-by-step solutions to problem parts, on request |
| Small checks | `claude-haiku-4-5` | Scoring extracted page text, hint leak check |

- All calls go through one server function (`server/kedami_server/model.py`), so models and retry policy are set in one place. Model names live in `MODEL_ROLES` in `server/kedami_server/config.py`.
- Generate calls opt into server-side refusal fallback (`fallbacks: "default"`), so a declined request is re-run on Anthropic's recommended fallback model instead of failing the lesson.
- Generation stages request structured output against the JSON Schema exported from the server's lesson models.
- When a small check is uncertain, the server takes the safer route (for example, transcribe the page).

## Usage log

Every model call is recorded against its lesson, so a lesson shows what it took to make: time, tokens, and cost.

**What is recorded**
- One row per call that gets a reply, written by the one model function: the lesson, the stage, the role, the model that answered, when the call started, how long it took, and its tokens (input, output, cache write, cache read).
- A reply that is then rejected, cut off, or declined is recorded too, since it is billed. A call that ends in an API error returns no usage and is not recorded.
- The stage is `ingest`, `extract`, `plan`, or `generate` for pipeline calls (hints and verification count as `generate`), and `solution` or `simulation` for calls made on request.
- The pipeline and the on-request routes name the lesson and stage before they call. A call made with no lesson named is not recorded.
- Latency is the wall time of the call, including waits before retrying a temporary failure.

**Tokens and cost**
- Input tokens are the uncached ones, as the API reports them. Input, cache write, and cache read add up to the size of the prompt.
- Cost is an estimate in US dollars from list prices per million tokens (input, output, cache write, cache read), which live in `MODEL_PRICES` in `server/kedami_server/config.py`, beside the roles. Cache writes are priced at the 5-minute rate, the only one the server uses.
- Cost is worked out when the call is recorded and stored with it, so a later price change doesn't rewrite what a lesson cost.
- When a declined request is re-run on a fallback model, the API reports each attempt on its own. The row's tokens are the sum over the attempts, and each attempt is priced at its own model's rate.
- An attempt by a model with no listed price leaves the row's cost empty. Totals count such calls instead of treating them as free.

**Reading it**
- When a pipeline run ends, ready or failed, the server prints one line: the lesson, the outcome, the run's wall time, and the calls, tokens, and cost of that run.
- `python -m kedami_server.usage_report {data folder}` prints the totals per lesson, and per stage within a lesson.
- A lesson's totals cover every run and every on-request call, so a rerun adds to them. Deleting a lesson deletes its rows.

**Not included:** usage in the app or the API, spending limits or warnings, and reconciling with Anthropic's billing.

Most likely to be wrong: the token and cost arithmetic (cached tokens, fallback attempts counted once, a model with no price) and tying a call to the right lesson while a generation thread and on-request calls run at the same time. These get tests first.

## Security and privacy

- The server binds to `127.0.0.1` only and rejects requests without the session token.
- The API key lives in the server's `.env`. The renderer never sees it.
- The only outbound traffic is to the Anthropic API. Fonts and the alarm sound are bundled.
- Model-written code runs only inside a sandboxed frame with no network, no Node access, and no access to app data.
- Electron main cancels any renderer request that isn't to a local file, the music protocol, or `127.0.0.1` or `localhost`, frames included, as a backstop to the CSPs.
- The music protocol serves only audio files directly inside the data folder's `music/`. The renderer names a track by file name; main resolves it and refuses anything outside that folder. Simulation frames can't load media at all.
- The one link that leaves the app is a LeetCode problem: the renderer asks main to open `https://leetcode.com/problems/{slug}/`, main checks the slug, and the student's default browser opens it. The app itself sends nothing to LeetCode.
- Diagram SVG is sanitized with DOMPurify before rendering.
- All expression parsing uses a restricted parser with whitelisted names, for both model output and user input. SymPy's default string parsing evaluates code and must not be used directly.
