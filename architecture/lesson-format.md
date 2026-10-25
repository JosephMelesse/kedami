# Lesson format

A lesson is a JSON document. It is produced by stage 4, by the pipeline or in agent mode, never edited in place, and replaced only by a rerun.

The server's Pydantic models in `server/kedami_server/lesson.py` are the source of truth. The JSON Schema exported from them is committed at `server/schema/lesson.schema.json`, and the renderer's TypeScript types are generated from it. Field names below are the JSON keys.

## Structure

| Level | Fields |
|---|---|
| Lesson | `schema_version` (currently 1), `id`, `title`, `subject` (`math`, `physics`, `computer_science`, or `general`), `domain` (computer science only: `dsa` or `sql`; null otherwise), `credits` (plain-text lines naming bundled sources a lesson draws on, such as the SQL book; empty otherwise), `source_files`, `sections` |
| Section | `id`, `title`, `goal` (one line), `blocks` |
| Block | `id`, `type`, plus the fields for that type |

**IDs**
- Every ID is a lowercase slug: letters, digits, and single hyphens.
- Section IDs and block IDs are unique within a lesson.
- A problem block's ID is derived from its source reference. A part's ID is derived from its label.
- Derivation lowercases the text, turns every run of other characters into one hyphen, and trims hyphens from the ends. "PS3 #4" becomes `ps3-4`, "(a)" becomes `a`, and "4(b)(ii)" becomes `4-b-ii`.
- A derived ID may be omitted and the server fills it in. If present, it must match the derivation.
- The server rejects a lesson whose part labels derive to the same ID within a problem, or whose source reference or label has no letters or digits.

## Blocks

| Block | Purpose | Fields | Counts toward completion |
|---|---|---|---|
| `explanation` | Teach a concept | `body` (Markdown with LaTeX) | No |
| `worked_example` | A similar problem solved in steps, revealed one at a time | `prompt`, `steps` | No |
| `plot` | Functions over a domain | `functions` (`expression`, `label`), optional `parameters` (`name`, `min`, `max`, `default`), `x_domain` as `[min, max]`, optional `y_domain`, `caption` | No |
| `diagram` | Static figure | `svg`, `caption` | No |
| `simulation` | Interactive canvas simulation | `code`, `caption` | No |
| `checkpoint` | Model-written practice question | `prompt`, `answer`, `hints`, `verified` | No |
| `problem` | A real homework item | `source_ref`, `prompt` (shared, may be empty), `parts` | Yes |

**Problem parts**
- Each part has `id`, `label`, `prompt`, `answer`, `hints`, and `verified`.
- A single-part problem is a problem with one part. Its label still derives its ID, but the renderer doesn't show it.
- A plot expression may use only `x` and the plot's parameter names.

## Answer kinds

| Kind | Fields | Checked by |
|---|---|---|
| `numeric` | `value`, `rel_tolerance` (default 0.01), optional `unit` | Value within tolerance. The unit is shown beside the input; the student enters the number only. |
| `expression` | `expression` | Symbolic equivalence in SymPy, numeric sampling as fallback |
| `self_check` | `rubric` | The rubric is shown after the student commits; they grade themselves |
| `choice` | `options` (at least 2), `correct_index` | Index match |
| `multi_choice` | `options` (at least 2), `correct_indexes` (at least 1, no duplicates) | Exact set match, for "select all that apply" |
| `code` | `platform` (`leetcode`), `number`, `title`, `slug`, `difficulty`, `method`, `starter_code`, `tests` (each `args`, `expected`, `compare`) | Run in the sandboxed runner against its tests; see `code-problems.md`. Problem parts only |
| `external` | `platform` (`leetcode` or `pgexercises`); for LeetCode `number`, `title`, `slug`; for pgexercises `path`, `title` | Not checked. A LeetCode problem not in the imported dataset, or a pgexercises problem in a SQL lesson (see `sql-lessons.md`): the student solves it there and marks it done. Problem parts only |
| `query` | `database`, `reference`, `ordered`, `exercise` | The student's query and the reference run on a fresh copy of the database and their results are compared; see `sql-lessons.md`. SQL lessons only |

## Computer science lessons

- A computer science lesson has a domain, which decides how it is built and shown. `dsa` (data structures and algorithms) is described below and in `code-problems.md`. `sql` is described in `sql-lessons.md`. A computer science lesson saved before domains existed has no `domain` and reads as `dsa`.
- In a DSA lesson, the student picks the problems in the problem picker (see Picking problems in `code-problems.md`). The renderer writes the picks as the problem set, a text file `problems.md` with one problem per line, each with its number and title, such as `1. Two Sum`, and the pipeline reads it like any problem set.
- The server reads the list strictly: blank lines and Markdown headings are ignored; any other line is an error, as are a missing title and a repeated number.
- Each listed problem becomes a problem block with source reference `LeetCode #N` and one part. A problem in the imported dataset gets a `code` answer, and its part text is the problem's description. Any other gets an `external` answer, and its text is "Complete LeetCode #N: Title." See `code-problems.md`.
- Every problem links to `https://leetcode.com/problems/{slug}/`. The slug is the dataset's when the problem is in it. Otherwise it is the title lowercased, with characters other than letters, digits, spaces, and hyphens removed and spaces turned into hyphens (`Pow(x, n)` becomes `powx-n`).
- The problem list is parsed by the server, not the model. The model maps each problem to the concepts it needs, from its title and, when the problem is in the dataset, its description. It must cover every listed number exactly once.
- Hints for a computer science problem part are written from its title and, for a `code` part, its description. The tests are never sent to the model.
- Comprehension checks use the existing answer kinds: `choice` and `multi_choice` for complexity and approach, `numeric` for questions such as what a snippet prints, and `self_check` for explanations.
- Code in lessons is Python, in fenced `python` blocks. No lesson content walks through a solution to an assigned LeetCode problem.

## General lessons

- For courses that aren't math, physics, or data structures and algorithms.
- The problem set is free-form and goes through the same extraction, planning, generation, hints, and verification as math and physics.
- Every answer kind except `external` is allowed. A question with a short factual answer, such as a term or a name, is a `self_check` with the answer in the rubric. A True/False question is a `choice` with the options True and False.
- Code in lessons uses the language of the course material, in fenced blocks tagged with that language. Only Python is highlighted; other languages show in JetBrains Mono without highlighting.

## Hints

- Generated with the lesson, ordered from gentle to specific, revealed one at a time.
- Hard cap of 3 per part and per checkpoint. If the model writes more, the server keeps the first 3 and drops the rest before any check, so a hint too many never fails the lesson.
- Hints never give a full solution. A worked solution for a problem part is shown only when the student asks for one; see Solutions.
- Each hint passes two checks: the answer does not appear in it, and a small check judges that it doesn't give the answer away. A failing hint is regenerated once, then dropped.

## Solutions

- Every problem part in a math, physics, or general lesson has a Show solution button. Lesson generation writes nothing for it, as with simulations: a separate call writes the solution the first time the student asks, and it is stored and shown from storage after that.
- A confirmation popup comes first, stating that it shows the full solution. Viewing a solution doesn't complete the part; it still needs a correct answer or mark done.
- Solutions are short. Math and physics solutions are labels and math, no sentences.
  - Math: the method in a few words (such as "Integration by parts"), then the working as LaTeX lines down to the final answer.
  - Physics: Given (each known quantity with its value and unit), Required (each quantity asked for), then the solution, starting from the formula it uses and ending at the answer.
  - General: a few short Markdown lines, each one fact or step of reasoning from the course material, ending with a line that states the final answer. Short sentences are allowed; math is inline LaTeX.
- The whole solution shows at once. In math and physics, each line of math is display math centered in the lesson column, and the last line boxes the final answer. In general, lines are left-aligned Markdown, and the last line has an "Answer" label and is set in medium weight.
- The call sees the course material and the whole problem, with the part to solve and the form its answer takes. It doesn't see the stored answer, hints, or lesson content.
- The reply also gives its final answer in that form, which the server compares with the stored answer the way verification does. On a disagreement the call is repeated once with the stored answer shown; if they still disagree, the solution shows with a "Doesn't match the stored answer" label. `self_check` parts aren't compared.
- A solution is stored apart from the lesson JSON, in the `solutions` table, keyed by block and part ID. A rerun replaces the lesson and clears these rows.
- `code` and `external` parts (computer science) have no solutions.
- Without an API key, the button asks for Claude Code instead: the student runs `/kedami:solution` in the Terminal screen and the same comparison applies. See Solutions and simulations in `agent-mode.md`.

## Simulations

- Requested where the section plan calls for one; each is a separate model call.
- The code runs in a sandboxed frame with no network, no Node access, and no access to app data.
- The frame receives the design token values when it loads and uses them for all colors.
- The frame must report ready within a few seconds with no errors. Otherwise the block is hidden and flagged for regeneration.
- Simulations are illustrative: they never count toward completion and never supply numbers the student is checked against.
- Each simulation has a regenerate button.
- Without an API key, Generate simulation and regenerate ask for Claude Code instead: the student runs `/kedami:simulation` in the Terminal screen. See `agent-mode.md`.
- The plan gives a section a one-line simulation brief only where one would teach what a static plot or diagram can't. The section call places one `simulation` block (a caption) exactly when there is a brief. The block keeps the brief, and its code stays empty: the code is written by a separate call only when the student clicks Generate simulation, so lesson generation never waits on it.
- The code is the body of `function simulation(root, canvas, tokens, ready)`: `root` is a div to build controls in, `canvas` is a 320 px tall canvas already in it, `tokens` holds the color token values and the font, and `ready()` must be called once it works. Code that never calls `ready(` is rejected and retried.
- The frame is a separate page, `simulation.html`, loaded with `sandbox="allow-scripts"` and no same-origin access. Its CSP allows no network. The ready window is 4 seconds; an error or timeout before ready flags the simulation on the server and shows a one-line notice with the regenerate button in its place.
- Written and regenerated code is the one exception to never editing a lesson: it is stored apart from the lesson JSON, in the `simulations` table, and served in place of the JSON's empty code. A rerun replaces the lesson and clears these rows.

## Diagrams

- A diagram is a small static SVG with a `viewBox`, colored with `currentColor`, and sanitized with DOMPurify before rendering.
- The model places text by coordinate without seeing it drawn, so its text is monospace, where width follows from length. The root `svg` sets `font-family="monospace"` and a numeric `font-size`; no element sets another font family, and an element may set its own `font-size` as a number.
- When a section is assembled, the server measures each piece of text as 0.6 of its font size wide per character, 0.75 above the baseline, and 0.25 below. It rejects a diagram whose text runs past the `viewBox`, overlaps other text, or crosses the edge of a rectangle, circle, or ellipse, allowing 1 unit of slack. Lines, paths, and polygons aren't checked, so a label may sit on an arrow. A shape whose size isn't a plain number isn't checked either.
- Text the server can't measure is rejected: text with child elements such as `tspan`, text under a `transform` or a `style` attribute, a position that isn't a single number, a `text-anchor` other than `start`, `middle`, or `end`, and a `dominant-baseline` other than the default, `middle`, or `central`. Text inside `defs`, `marker`, and similar elements isn't drawn and isn't checked.
- A rejected diagram sends the section back to the model with the problems found, like any other section error. If the last attempt still has a bad diagram, that diagram is dropped and the section kept, so a figure never fails a lesson.
- The check runs only while generating. Lessons made before it are served as they are.

## Rules

- Worked examples and checkpoints never use an actual homework problem.
- All math strings use SymPy syntax. The restricted parser also accepts `^` for powers and `ln` and `abs` as aliases. It does not accept implicit multiplication such as `2x`.
- Display math in Markdown puts each `$$` on its own line. `$$...$$` on a single line renders as inline math.
- The server checks answers and samples points for static plots, so the renderer never parses SymPy.
- For plots with parameters, the server sends an expression tree that the renderer evaluates with plain arithmetic and `Math` functions, never as code. Nodes are numbers, names, sums, products, powers, and the whitelisted one-argument functions.
- The `verified` flag is set only by the server's verification pass, never by the model. In agent mode the second solve comes from the plugin's verifier subagent, and the server still does the comparison and sets the flag.
- Titles, section goals, and simulation briefs are plain text, not Markdown. A model sometimes writes a character as a literal escape such as `\u0394`; the server decodes these in plain-text fields when it reads a plan or a lesson, so they show as the character (Δ). The lesson JSON on disk is left as written.
- A model sometimes double-escapes the LaTeX in a Markdown field, writing `\\rightarrow` for `\rightarrow`. KaTeX reads `\\` as a line break, so the command name would show as text. When the server reads a lesson, it halves the backslashes in a math span if every backslash in the span is doubled and one comes before a command name. Text outside math is never changed, and the lesson JSON on disk is left as written.
