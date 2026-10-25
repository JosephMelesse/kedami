# Building lessons with Claude Code

Kedami makes no model calls. The student's own Claude Code session builds every lesson, and writes every solution and simulation, from Kedami's Terminal panel, using tools Kedami provides through an MCP server. Kedami checks and stores everything Claude Code sends.

The student drives Claude Code: they start it, type the request, and approve its tool calls. Kedami never types into the terminal and never runs Claude Code non-interactively.

## Scope

- Math, physics, and general lessons. Computer science lessons can no longer be created; those made earlier by the API pipeline still open and work.
- A ready lesson is never rebuilt: there are no reruns.
- Claude Code only.
- Claude Code runs inside Kedami's Terminal panel. A session started in another terminal can't reach the server.

## Pieces

| Piece | Where | Does |
|---|---|---|
| Terminal panel | Electron main, a separate view | Runs Claude Code, or a shell, in a pseudo-terminal |
| Plugin | `agent-plugin/` in the app data folder, written by the server | Skills with the instructions, two subagents, and the MCP server's launch config |
| MCP server | `python -m kedami_server.mcp`, started by Claude Code | Kedami's tools; each one is a call to an agent route |
| Agent routes | The server, under `/agent/` | Validate what Claude Code submits, assemble the lesson, and store it |

```
Window ── Terminal panel ── Claude Code (student's login, student types)
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
- The window learns about a lesson being built by polling the server.

## Uploading

- The student picks the subject and adds files on the Upload screen. At least one file is tagged as a problem set; the others are reference material.
- Supported inputs are PDF, images, plain text, and Markdown.
- Uploads are checked before anything is saved: at most 20 files, 30 MB each, and 100 pages in all. File names are made safe and unique in the materials folder.
- The server saves the files and creates the lesson as generating with no current stage, shown as "Waiting for Claude Code".

## Building a lesson

1. **Start.** In the Terminal panel the student starts Claude Code and runs `/kedami:lesson`. The skill calls `list_waiting_lessons`, then `start_lesson`, which returns the subject, each material's path and role, and the steps already done. Calling it on a lesson already started resumes the build, so a new session can pick up where a closed one stopped. Paths are inside the data folder, Claude Code's working directory, so reading them needs no extra permission.
2. **Stage 1, ingest.** Claude Code reads every file itself, PDFs and images included, and submits each page as Markdown with LaTeX through `save_pages`. The server joins the pages into one document per role, each page marked with its file and page number and blank pages left out, and records every page in `pages.json`. A problem set with no text is refused.
3. **Stage 2, extract.** It submits every problem with its source reference and parts, the options of any part that lists them, the concepts, and which concepts each problem needs, through `save_extraction`. The server validates them and saves `extraction.json`.
4. **Stage 3, plan.** It submits the section order and each section's concepts through `save_plan`. The server places the problems (see Sequencing), saves `plan.json`, and returns each section with its problems.
5. **Stage 4, sections.** For each section, it writes the content and submits it through `save_section`. The server assembles the section: problem text inserted verbatim from extraction, IDs derived, a part with extracted options given those options, and the diagram layout check. A rejected section comes back with every reason, and Claude Code fixes and resubmits it. An accepted one comes back with its hint targets.
6. **Hints.** For each target, Claude Code writes hints, has the `hint-checker` subagent judge them, rewrites failing ones once, drops those still failing, and submits through `save_hints`. The server keeps the first 3 per target and drops any that fail the leak check, saying which. Hints saved for a target replace its earlier ones.
7. **Verification.** For each accepted section, the `verifier` subagent calls `get_questions`, which returns each part and checkpoint with the form of its answer and never the stored answer, solves them from the material, and submits through `save_verification`. The server compares the answers, sets `verified`, and saves `verification-{n}.json`. See `completion-and-verification.md`.
8. **Finish.** `finish_lesson` checks that every section is accepted, writes `lessons/{id}.json`, and marks the lesson ready. Verification is not required to finish: a section that wasn't verified stays unverified.

**Sequencing.** The model orders the sections and assigns each concept to exactly one of them; the server places the problems, so these hold by construction:
- A concept is introduced before any problem that needs it.
- Each problem appears in the section where its last prerequisite is covered. A problem with no prerequisites goes in the first section.
- Every problem appears exactly once.
- A section with no concepts and no problems is dropped.

**The draft.** Between start and finish, the lesson is a draft held in `work/{id}/`.
- Each step requires the one before it: no extraction before pages, no plan before extraction, no section before the plan, no verification before its section is accepted.
- A section may be resubmitted until finish; the newest accepted version wins, and its hints and verification are cleared.
- Submitting a step again after later steps exist deletes the later steps' outputs.
- The draft is never served as a lesson. `GET /lessons/{id}` shows its status and current stage only.
- `fail_lesson` ends the build with a reason. The Generating screen's Cancel button does the same with "Canceled", through `POST /lessons/{id}/cancel`. Tools called on a failed lesson are refused.
- Closing the app ends the Terminal session. A lesson still generating is marked failed on the next start.

## The plugin

The server writes the plugin to `agent-plugin/` in the data folder on every start, replacing what was there.

| File | Contents |
|---|---|
| `.claude-plugin/plugin.json` | Name `kedami`, version, description |
| `skills/lesson/SKILL.md` | `/kedami:lesson`: the build steps above, with the rules from `generation/prompts.py` |
| `skills/solution/SKILL.md` | `/kedami:solution <lesson-id> <block-id> <part-id>`: write one problem part's solution |
| `skills/simulation/SKILL.md` | `/kedami:simulation <lesson-id> <block-id>`: write one simulation's code |
| `agents/verifier.md` | The second solve. Model from `SUBAGENT_MODELS["verifier"]` |
| `agents/hint-checker.md` | The hint judge. Model from `SUBAGENT_MODELS["hint_checker"]` |
| `.mcp.json` | Starts `kedami_server.mcp` with the server's own Python (`sys.executable`) and the server folder |

- The rules live in `generation/prompts.py` and the subagents' models in `config.py`, so they change in one place.
- The main session runs on whatever model the student picked in Claude Code.
- No token is written into the plugin. `.mcp.json` passes `KEDAMI_PORT` and `KEDAMI_TOKEN` to the MCP server by name, as `${KEDAMI_PORT}` and `${KEDAMI_TOKEN}`, which Claude Code expands from its own environment, which it inherits from the Terminal panel. Without them, every tool says to start Claude Code from the Terminal panel.
- The skills run only when the student types them (`disable-model-invocation`), so the plugin adds nothing to Claude Code's context until then.
- A refused tool call comes back as a tool error carrying the server's reason, so Claude Code can fix what it sent.
- The skills tell Claude Code not to run any code it writes. Simulation code runs only in the sandboxed frame.

## Solutions and simulations

Lesson building writes neither; Claude Code writes each one when the student asks.
- **Show solution** and **Generate simulation** (or **Regenerate**) show the command to run, such as `/kedami:solution {lesson-id} ps3-4 a`, with a Copy button, until Claude Code has saved the result. The window checks every 3 seconds and shows it as soon as it is saved.
- `get_solution_request` returns the material paths, the whole problem, the part, and the form of its answer, never the stored answer. `save_solution` stores it and compares the final answer with the stored one. On a disagreement the route returns the stored answer unsaved, Claude Code writes it once more, and a second disagreement saves it with `matches` false.
- `get_simulation_request` returns the brief, the section's teaching, and any flagged error. `save_simulation` stores the code apart from the lesson JSON, under the rules in `lesson-format.md`.
- Both work on any ready lesson, including ones the old API pipeline made.

## Terminal panel

- **Opening:** a panel on the right, below the header, at full height. The Terminal button in the app header, after "Kedami", opens and closes it, and so does Ctrl+` (Cmd+` on macOS) from anywhere in the app, the terminal included. Main handles the shortcut, so it works while the terminal has the keyboard. Closing the panel leaves the session running.
- **Beside the content:** the screen on the left, the code workspace included, narrows to make room instead of being covered, so the student can read the lesson or watch the Generating screen while Claude Code works. Clicking Kedami goes home and leaves the panel open. Dialogs center in the area left of the panel, since the terminal's view draws over the window's own content.
- **Width:** the panel's left edge is a handle the student drags. The width is kept between 320px and the window's width less 360px, and remembered locally between launches; the first width is 40% of the window. While dragging, the terminal's view hides and the panel shows empty, then the view returns at the new width.
- **Narrow windows:** at 720px wide or less, the open panel covers everything below the header, and the screen underneath keeps its state and takes no input.
- **Rest:** the rest screen covers the panel too. The view hides during rest and returns after it, and the session keeps running.
- **Starting:** with no session, the panel shows two buttons: **Start Claude Code**, which runs `claude --plugin-dir {data}/agent-plugin`, and **Open a shell**, which runs the student's default shell. One session at a time. When it exits, the buttons return.
- **Missing Claude Code:** if `claude` isn't on the path, the panel says so and shows the install page's address as plain text.
- **Environment:** the session starts in the data folder, with the parent environment plus `KEDAMI_PORT` and `KEDAMI_TOKEN`.
- **Closing the app** kills the session.

**Isolation.** A terminal is the most powerful thing in the app, so the lesson window never gets it.
- The terminal is a separate `WebContentsView` with its own renderer process, loading the local page `terminal.html` (xterm.js) with its own preload. That preload is the only one that can send keystrokes, resize, or start a session.
- Main accepts pseudo-terminal messages only from that view's `webContents` and drops them from anywhere else.
- The lesson window can only ask main to show or hide the view and set its bounds. The shortcut goes from main to the lesson window, which decides whether the panel opens.
- `terminal.html` has a CSP that allows only its own scripts and styles, and never shows lesson content. Terminal output is drawn as text, and links in it don't open.
- node-pty runs in main. The window and the terminal view never get Node access.

## Agent routes

All require the session token, like every route. The build routes refuse a lesson the old API pipeline made.

| Method | Path | Tool | Purpose |
|---|---|---|---|
| GET | `/agent/lessons` | `list_waiting_lessons` | Lessons waiting for Claude Code |
| POST | `/agent/lessons/{id}/start` | `start_lesson` | Claim a waiting lesson, or resume one already started; returns its subject, materials, and the steps done |
| POST | `/agent/lessons/{id}/pages` | `save_pages` | Each file's pages as Markdown; stage 1 |
| POST | `/agent/lessons/{id}/extraction` | `save_extraction` | Stage 2 |
| POST | `/agent/lessons/{id}/plan` | `save_plan` | Stage 3; returns each section with its problems placed |
| POST | `/agent/lessons/{id}/sections/{n}` | `save_section` | One section; returns its hint targets, or every reason it was rejected |
| POST | `/agent/lessons/{id}/sections/{n}/hints` | `save_hints` | Hints for some targets, replacing theirs; returns any dropped by the leak check |
| GET | `/agent/lessons/{id}/sections/{n}/questions` | `get_questions` | Each part and checkpoint with its answer form, without stored answers, and the course material files |
| POST | `/agent/lessons/{id}/sections/{n}/verification` | `save_verification` | The second solve's answers; the server sets `verified` |
| POST | `/agent/lessons/{id}/finish` | `finish_lesson` | Write the lesson JSON and mark it ready |
| POST | `/agent/lessons/{id}/fail` | `fail_lesson` | End the build with a reason |
| GET | `/agent/lessons/{id}/blocks/{block_id}/solution-request` | `get_solution_request` | What the solution writer may see |
| POST | `/agent/lessons/{id}/blocks/{block_id}/solution` | `save_solution` | Store a solution and compare its answer; a first disagreement is returned unsaved, with the stored answer |
| GET | `/agent/lessons/{id}/blocks/{block_id}/simulation-request` | `get_simulation_request` | A simulation's brief and any flagged error |
| POST | `/agent/lessons/{id}/blocks/{block_id}/simulation` | `save_simulation` | Store a simulation's code |

## What the server can't check

- **Independence of the second solve.** The server never sends stored answers to the verifier, but it can't prove the main session didn't pass one along. The skill forbids it; the server only checks that the question set matches.
- **The hint judge.** The server runs the leak check on every hint, but it can't confirm the subagent judged them.
- **Cost.** Calls run on the student's Claude plan, so Kedami records no usage.

## Non-goals

**Don't belong in Kedami**
- Kedami calling a model, Claude Code, or any coding agent CLI itself, or typing into the terminal
- Offering claude.ai login inside Kedami
- Running code Claude Code writes anywhere but the sandboxed frames

**Cut to ship faster (backlog)**
- Creating computer science lessons through Claude Code
- Changing a ready lesson from the Terminal panel, in place of reruns
- Codex
- Claude Code sessions outside the Terminal panel

## Most likely to be wrong

The draft: a lesson assembled across many tool calls. That means steps arriving out of order or twice, a resubmitted section replacing an accepted one and clearing its verification, a build that stops halfway, and a draft that must never be served as ready. The agent routes get tests for these first, with no Claude Code involved.

Second: the Terminal panel's isolation. Its test sends pseudo-terminal messages from the lesson window and checks that main drops them.

## Commands

Run the app (`npm run dev` in `app/`), create a lesson, open the Terminal panel, click Start Claude Code, and run `/kedami:lesson`. Claude Code must be on the path of the terminal `npm run dev` was started from.

Or against a server started by hand (see `CLAUDE.md`):

```bash
cd data
KEDAMI_PORT=8765 KEDAMI_TOKEN=dev claude --plugin-dir agent-plugin
```
