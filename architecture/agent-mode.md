# Agent mode

A second way to build a lesson. Instead of the server calling the Anthropic API, the student's own Claude Code session builds the lesson from Kedami's Terminal screen, using tools Kedami provides through an MCP server. The API pipeline stays, and stays the default when an API key is set.

The student drives Claude Code: they start it, type the request, and approve its tool calls. Kedami never types into the terminal and never runs Claude Code non-interactively.

## Scope

- Math, physics, and general lessons. Computer science lessons are built by the API pipeline only.
- New lessons only. Reruns of agent lessons are in the backlog.
- Claude Code only. Codex is in the backlog.
- Claude Code runs inside Kedami's Terminal screen. A session started in another terminal can't reach the server.

## Pieces

| Piece | Where | Does |
|---|---|---|
| Terminal screen | Electron main, a separate view | Runs Claude Code, or a shell, in a pseudo-terminal |
| Plugin | `agent-plugin/` in the app data folder, written by the server | Skills with the instructions, two subagents, and the MCP server's launch config |
| MCP server | `python -m kedami_server.mcp`, started by Claude Code | Kedami's tools; each one is a call to an agent route |
| Agent routes | The server, under `/agent/` | Validate what the agent submits, assemble the lesson, and store it |

```
Window ── Terminal screen ── Claude Code (student's login, student types)
  │                              │ calls tools
  │                              ▼
  │                         MCP server
  │ HTTP + token                 │ HTTP + token
  └──────────► Server ◄──────────┘
                 │ validates, then writes
                 ▼
     kedami.db, lessons/{id}.json, work/{id}/
```

- The server is the only writer. The MCP server holds no state and touches no files.
- The window learns about an agent lesson the same way as any other: by polling the server.

## Building a lesson

1. **Upload.** The student uploads files on the Upload screen as today and picks **Claude Code** as the builder. The server saves the materials and creates the lesson as generating with no current stage, shown as "Waiting for Claude Code".
2. **Start.** In the Terminal screen the student starts Claude Code and runs `/kedami:lesson`. The skill calls `list_waiting_lessons`, then `start_lesson`, which returns the subject, each material's path and role, and the steps already done. Calling it on a lesson already started resumes the build, so a new session can pick up where a closed one stopped. Paths are inside the data folder, Claude Code's working directory, so reading them needs no extra permission.
3. **Stage 1, ingest.** Claude Code reads every file itself, PDFs and images included, and submits normalized Markdown with LaTeX per file through `save_pages`. Every page is recorded with the route `agent` in `pages.json`.
4. **Stage 2, extract.** It submits the problems, parts, options, concepts, and problem-to-concept map through `save_extraction`. The server validates them against the same rules as the pipeline's extraction and saves `extraction.json`.
5. **Stage 3, plan.** It submits the section order and each section's concepts through `save_plan`. The server places the problems, exactly as in the pipeline, saves `plan.json`, and returns each section with its problems.
6. **Stage 4, sections.** For each section, it writes the content and submits it through `save_section`. The server assembles the section as the pipeline does: problem text inserted verbatim, IDs derived, and the diagram layout check. A rejected section comes back with every reason, and the agent fixes and resubmits it. An accepted one comes back with its hint targets.
7. **Hints.** For each target, the agent writes hints, has the `hint-checker` subagent judge them, rewrites failing ones once, drops those still failing, and submits through `save_hints`. The server keeps the first 3 per target and drops any that fail the leak check, saying which. Hints saved for a target replace its earlier ones.
8. **Verification.** For each accepted section, the `verifier` subagent calls `get_questions`, which returns each part and checkpoint with the form of its answer and never the stored answer, solves them from the material, and submits through `save_verification`. The server compares the answers as the pipeline does, sets `verified`, and saves `verification-{n}.json`.
9. **Finish.** `finish_lesson` checks that every section is accepted, writes `lessons/{id}.json`, and marks the lesson ready. Verification is not required to finish: a section that wasn't verified stays unverified, as in the pipeline.

The stage outputs in `work/{id}/` have the same names and shapes as the pipeline's, so they can be inspected the same way.

**The draft.** Between start and finish, the lesson is a draft held in `work/{id}/`.
- Each step requires the one before it: no extraction before pages, no plan before extraction, no section before the plan, no verification before its section is accepted.
- A section may be resubmitted until finish; the newest accepted version wins, and its hints and verification are cleared.
- Submitting a step again after later steps exist deletes the later steps' outputs, as a rerun does.
- The draft is never served as a lesson. `GET /lessons/{id}` shows its status and current stage only.
- `fail_lesson` ends the build with a reason. The Generating screen's Cancel button does the same with "Canceled", through `POST /lessons/{id}/cancel`. Tools called on a failed lesson are refused.
- Closing the app ends the Terminal session. A lesson still generating is marked failed on the next start, as pipeline lessons are.

## The plugin

The server writes the plugin to `agent-plugin/` in the data folder on every start, replacing what was there.

| File | Contents |
|---|---|
| `.claude-plugin/plugin.json` | Name `kedami`, version, description |
| `skills/lesson/SKILL.md` | `/kedami:lesson`: the build steps above, with the rules from `prompts.py` |
| `skills/solution/SKILL.md` | `/kedami:solution`: write one problem part's solution |
| `skills/simulation/SKILL.md` | `/kedami:simulation`: write one simulation's code |
| `agents/verifier.md` | The second solve. Model from `MODEL_ROLES["second_solve"]` |
| `agents/hint-checker.md` | The hint judge. Model from `MODEL_ROLES["small_check"]` |
| `.mcp.json` | Starts `kedami_server.mcp` with the server's own Python (`sys.executable`) and the server folder |

- The skill text is built from the same prompts as the pipeline, so the two can't drift.
- Model names come from config, as everywhere else.
- No token is written into the plugin. The MCP server reads `KEDAMI_PORT` and `KEDAMI_TOKEN` from its environment, which it inherits from Claude Code, which inherits it from the Terminal screen. Confirm when building that Claude Code passes its environment to stdio MCP servers; if it doesn't, `.mcp.json` passes the two variables by name.
- The skills tell Claude Code not to run any code it writes. Simulation code runs only in the sandboxed frame, as always.

## Solutions and simulations

Show solution and Generate simulation work as today when an API key is set. Without one:
- The button explains that it needs Claude Code and gives the command to run, such as `/kedami:solution ps3-4 a`, with a Copy button.
- `get_solution_request` returns the material paths, the whole problem, the part, and the form of its answer, never the stored answer. `save_solution` stores it and compares the final answer with the stored one as today. On a disagreement the route returns the stored answer, the agent writes it once more, and a second disagreement saves it with `matches` false.
- `get_simulation_request` returns the brief and any flagged error. `save_simulation` stores the code under the same rules as a regenerated simulation.
- The window sees the new solution or simulation the next time it asks the server.

## Terminal screen

- **Opening:** a Terminal button in the app header, after "Kedami". The screen replaces everything below the header, like the workspace; the screen underneath keeps its state. The rest screen covers it like any other screen, and the session keeps running underneath.
- **Starting:** with no session, the screen shows two buttons: **Start Claude Code**, which runs `claude --plugin-dir {data}/agent-plugin`, and **Open a shell**, which runs the student's default shell. One session at a time. When it exits, the buttons return.
- **Missing Claude Code:** if `claude` isn't on the path, the screen says so and shows the install page's address as plain text.
- **Environment:** the session starts in the data folder, with the parent environment plus `KEDAMI_PORT` and `KEDAMI_TOKEN`.
- **Closing the app** kills the session.

**Isolation.** A terminal is the most powerful thing in the app, so the lesson window never gets it.
- The terminal is a separate `WebContentsView` with its own renderer process, loading the local page `terminal.html` (xterm.js) with its own preload. That preload is the only one that can send keystrokes, resize, or start a session.
- Main accepts pseudo-terminal messages only from that view's `webContents` and drops them from anywhere else.
- The lesson window can only ask main to show or hide the view and set its bounds.
- `terminal.html` has a CSP that allows only its own scripts and styles, and never shows lesson content. Terminal output is drawn as text, and links in it don't open.
- node-pty runs in main. The window and the terminal view never get Node access.

## Agent routes

All require the session token, like every route. They refuse lessons whose builder isn't `agent`.

| Method | Path | Tool | Purpose |
|---|---|---|---|
| GET | `/agent/lessons` | `list_waiting_lessons` | Agent lessons waiting for Claude Code |
| POST | `/agent/lessons/{id}/start` | `start_lesson` | Claim a waiting lesson, or resume one already started; returns its subject, materials, and the steps done |
| POST | `/agent/lessons/{id}/pages` | `save_pages` | Normalized text per file; stage 1 |
| POST | `/agent/lessons/{id}/extraction` | `save_extraction` | Stage 2 |
| POST | `/agent/lessons/{id}/plan` | `save_plan` | Stage 3; returns each section with its problems placed |
| POST | `/agent/lessons/{id}/sections/{n}` | `save_section` | One section; returns its hint targets, or every reason it was rejected |
| POST | `/agent/lessons/{id}/sections/{n}/hints` | `save_hints` | Hints for some targets, replacing theirs; returns any dropped by the leak check |
| GET | `/agent/lessons/{id}/sections/{n}/questions` | `get_questions` | Each part and checkpoint with its answer form, without stored answers |
| POST | `/agent/lessons/{id}/sections/{n}/verification` | `save_verification` | The second solve's answers; the server sets `verified` |
| POST | `/agent/lessons/{id}/finish` | `finish_lesson` | Write the lesson JSON and mark it ready |
| POST | `/agent/lessons/{id}/fail` | `fail_lesson` | End the build with a reason |
| GET | `/agent/lessons/{id}/blocks/{block_id}/solution-request` | `get_solution_request` | What the solution writer may see |
| POST | `/agent/lessons/{id}/blocks/{block_id}/solution` | `save_solution` | Store a solution and compare its answer; a first disagreement is returned unsaved, with the stored answer |
| GET | `/agent/lessons/{id}/blocks/{block_id}/simulation-request` | `get_simulation_request` | A simulation's brief and any flagged error |
| POST | `/agent/lessons/{id}/blocks/{block_id}/simulation` | `save_simulation` | Store a simulation's code |

The solution and simulation routes accept a lesson from either builder, since they serve a student without an API key.

## What changes and what doesn't

**Unchanged:** the lesson format, the validators, problem placement, ID derivation, verbatim problem text, answer checking, progress, and every screen after the lesson is ready.

**Weaker than the pipeline:**
- **Independence of the second solve.** The server never sends stored answers to the verifier, but it can't prove the main session didn't pass one along. The skill forbids it; the server only checks that the question set matches.
- **The hint judge.** The server still runs the leak check on every hint, but it can't confirm the subagent judged them.
- **Cost and the usage log.** Calls run on the student's plan, so nothing is recorded in `model_calls` or `runs.jsonl`.

## Non-goals

**Don't belong in agent mode**
- Kedami calling Claude Code or any coding agent CLI itself, or typing into the terminal
- Offering claude.ai login inside Kedami
- Running code the agent writes anywhere but the sandboxed frames

**Cut to ship faster (backlog)**
- Computer science lessons in agent mode
- Reruns of agent lessons
- Codex
- Claude Code sessions outside the Terminal screen
- Agent builds in the run log

## Most likely to be wrong

The draft: a lesson assembled across many tool calls. That means steps arriving out of order or twice, a resubmitted section replacing an accepted one and clearing its verification, a build that stops halfway, and a draft that must never be served as ready. The agent routes get tests for these first, with no Claude Code involved.

Second: the Terminal screen's isolation. Its test sends pseudo-terminal messages from the lesson window and checks that main drops them.

## Commands

Try agent mode against a server started by hand (see `CLAUDE.md`):

```bash
cd data
KEDAMI_PORT=8765 KEDAMI_TOKEN=dev claude --plugin-dir agent-plugin
```

Then upload a lesson with Claude Code as the builder and run `/kedami:lesson`. The server needs no API key for this.
