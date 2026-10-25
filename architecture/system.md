# System

## Processes

| Process | Responsibility | Stack |
|---|---|---|
| Electron renderer | UI only: file drop, lesson rendering, answer input, progress, sandboxed simulation frames, code editor and sandboxed runner frame, Pomodoro timer, music player | TypeScript, React, KaTeX, DOMPurify, CodeMirror, Pyodide |
| Electron main | Window management; spawns and kills the server; passes the port and session token to the renderer; copies and serves music player tracks; runs the Terminal screen's pseudo-terminal | TypeScript, node-pty |
| Terminal view | The Terminal screen: draws the pseudo-terminal, in its own renderer process (see `agent-mode.md`) | TypeScript, xterm.js |
| Local server | Ingestion, model calls, verification, answer checking, storage; writes the agent plugin and serves its routes | Python, FastAPI, SymPy, SQLite |
| MCP server | Agent mode's tools, started by Claude Code; each tool calls an agent route | Python, MCP SDK |

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

- All calls Kedami makes go through one server function (`server/kedami_server/model.py`), so models and retry policy are set in one place. In agent mode Kedami makes no model calls: the student's Claude Code session makes them on their plan, and the plugin's subagents take their models from `MODEL_ROLES` (see `agent-mode.md`). Model names live in `MODEL_ROLES` in `server/kedami_server/config.py`.
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
- Stage 1 transcribes pages on several threads at once. Each of those calls is recorded under the run's lesson and stage, like a call made on the run's own thread.
- Latency is the wall time of the call, including waits before retrying a temporary failure.

**Tokens and cost**
- Input tokens are the uncached ones, as the API reports them. Input, cache write, and cache read add up to the size of the prompt.
- Cost is an estimate in US dollars from list prices per million tokens (input, output, cache write, cache read), which live in `MODEL_PRICES` in `server/kedami_server/config.py`, beside the roles. Cache writes are priced at the 5-minute rate, the only one the server uses.
- Cost is worked out when the call is recorded and stored with it, so a later price change doesn't rewrite what a lesson cost.
- When a declined request is re-run on a fallback model, the API reports each attempt on its own. The row's tokens are the sum over the attempts, and each attempt is priced at its own model's rate.
- Every reported attempt is priced, though the API doesn't bill some attempts that are declined before any output, so a lesson with declined requests can read slightly high.
- An attempt by a model with no listed price leaves the row's cost empty. Totals count such calls instead of treating them as free.

**Reading it**
- While a pipeline run is under way, the server's terminal shows `generating lesson...` above a table: a row per pipeline stage and a total, each with its calls, model time, and cost. The table covers that run only and is redrawn in place each time a call is recorded.
- When the run ends, the heading becomes `lesson ready in 10m 09s` or `lesson failed in 10m 09s`, the run's wall time, and the table stays.
- One table is redrawn at a time. A run that starts while another is under way, or whose output isn't a terminal, prints its table once, when it ends. Calls made on request print nothing.
- `python -m kedami_server.usage_report {data folder}` prints the totals per lesson, and per stage within a lesson, with tokens.
- A lesson's totals cover every run and every on-request call, so a rerun adds to them. Deleting a lesson deletes its rows.

**Not included:** usage in the app or the API, spending limits or warnings, and reconciling with Anthropic's billing.

Most likely to be wrong: the token and cost arithmetic (cached tokens, fallback attempts counted once, a model with no price) and tying a call to the right lesson while a generation thread and on-request calls run at the same time. These get tests first.

## Run log

Every pipeline run leaves one record of what it made and what it took, so the cost of a lesson can be followed from run to run without copying numbers by hand. The usage log answers what a lesson has cost in all; the run log answers what one run cost, and keeps the answer after the lesson is gone.

**What is recorded**
- One record per pipeline run, for a new lesson or a rerun, written when the run ends, whether the lesson is ready or the run failed.
- The run: when it started, its wall time, the stage it started from, whether it was a rerun of an existing lesson, and the outcome. A failed run also records the stage it failed in and the reason, as the Generating screen shows it for a new lesson.
- The code: the commit the server is running from and whether the working tree had uncommitted changes, read from git when the server starts. Both are empty when git can't be read.
- The material: each file with its role, the number of pages kept and transcribed, and the length of the normalized text. These come from the stage 1 output on disk and are empty if a run fails before it is written.
- The lesson: ID, title, and subject. A run that ends ready also records the number of sections, blocks, problems, and parts, and how many answers were verified out of those that could be.
- The usage: calls, model time, tokens of each kind, and cost, for each stage, role, and model that ran. These are the run's calls from the usage log, added up when the run ends.
- The prices: the list prices of the models that ran, as they stood in config, so cost by kind of token can be worked out later whatever the config says by then.

**Where it lives**
- `runs.jsonl` in the app data folder: one JSON object per line, only ever added to.
- It is apart from the database and from the lesson's files, so deleting a lesson, or the database, keeps it.
- Writing the record never fails the run. If it can't be written, the server logs a warning.

**Reading it**
- `python -m kedami_server.run_report {data folder}` prints the run log as Markdown: a table with a row per run (date, lesson, start stage, outcome, calls, wall time, cost), then for each run its material and lesson, and its usage by stage, by role, and by kind of token.

**Not included:** calls made on request (solutions and simulations stay in the usage log only), a run cut short by the app closing (it leaves no record, though its calls are in the usage log), runs made before this step, and anything in the app or the API.

Most likely to be wrong: counting the calls made on the transcription threads under the right run, and writing a complete record for a run that failed partway, when some stage outputs don't exist. These get tests first.

## Security and privacy

- The server binds to `127.0.0.1` only and rejects requests without the session token.
- The API key lives in the server's `.env`. The renderer never sees it.
- Kedami's only outbound traffic is to the Anthropic API. Fonts and the alarm sound are bundled. Programs the student runs in the Terminal screen, Claude Code included, make their own connections.
- The Terminal screen is a separate view with its own preload. Main accepts pseudo-terminal input only from that view, so the lesson window can never type into a shell. See Isolation in `agent-mode.md`.
- Kedami never types into the terminal and never runs a coding agent non-interactively. The student drives Claude Code.
- Model-written code runs only inside a sandboxed frame with no network, no Node access, and no access to app data.
- The student's code, and the dataset's test arguments and expected values, run only inside the runner frame, which has the same limits. Pyodide is bundled, never fetched. The server never runs or evaluates either; the import reads tests with Python's `ast` parser only.
- SQL from the student, the exercise bank, or the model runs only on the server, in a fresh in-memory copy of its database, never in the database file or `kedami.db`. An authorizer allows reads only, one statement runs, and a query stops after 2 seconds. See `sql-lessons.md`.
- Electron main cancels any renderer request that isn't to a local file, the music protocol, or `127.0.0.1` or `localhost`, frames included, as a backstop to the CSPs.
- The music protocol serves only audio files directly inside the data folder's `music/`. The renderer names a track by file name; main resolves it and refuses anything outside that folder. Simulation frames can't load media at all.
- Two kinds of link leave the app: a LeetCode problem and a pgexercises page. The renderer asks main to open one, main checks it (a LeetCode slug, or a pgexercises path of one section folder and one page name, such as `joins/self2.html`) and builds the URL, and the student's default browser opens it. The app itself sends nothing to either site.
- Diagram SVG is sanitized with DOMPurify before rendering.
- All expression parsing uses a restricted parser with whitelisted names, for both model output and user input. SymPy's default string parsing evaluates code and must not be used directly.
