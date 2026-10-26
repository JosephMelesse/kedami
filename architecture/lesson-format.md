# Lesson format

A lesson is a JSON document. The server writes it when Claude Code finishes building the lesson (see `agent-mode.md`), and it is never edited or replaced after that.

The server's Pydantic models in `server/kedami_server/lesson.py` are the source of truth. The JSON Schema exported from them is committed at `server/schema/lesson.schema.json`, and the renderer's TypeScript types are generated from it. Field names below are the JSON keys.

## Structure

| Level | Fields |
|---|---|
| Lesson | `schema_version` (currently 1), `id`, `title`, `subject` (`math`, `physics`, `computer_science`, or `general`), `domain` (null; it was set only on computer science lessons, which are not opened), `credits` (plain-text lines naming sources a lesson draws on; empty otherwise), `source_files`, `sections` |
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

## Computer science lessons

Computer science lessons are not opened. Ones the old API pipeline made stay on disk and are left out of the library. New ones can't be created.

## General lessons

- For courses that aren't math or physics.
- The problem set is free-form and goes through the same extraction, planning, generation, hints, and verification as math and physics.
- Every answer kind is allowed. A question with a short factual answer, such as a term or a name, is a `self_check` with the answer in the rubric. A True/False question is a `choice` with the options True and False.
- Code in lessons uses the language of the course material, in fenced blocks tagged with that language. Only Python is highlighted; other languages show in JetBrains Mono without highlighting.

## Hints

- Written by Claude Code with the lesson, ordered from gentle to specific, revealed one at a time.
- Hard cap of 3 per part and per checkpoint. If more are sent, the server keeps the first 3 and drops the rest before any check, so a hint too many is never refused.
- Hints never give a full solution. A worked solution for a problem part is shown only when the student asks for one; see Solutions.
- Each hint passes two checks: the server checks that the answer does not appear in it, and the plugin's hint-checker subagent judges that it doesn't give the answer away. A failing hint is rewritten once, then dropped.

## Solutions

- Every problem part in a math, physics, or general lesson has a Show solution button. Building the lesson writes nothing for it, as with simulations: Claude Code writes the solution the first time the student asks, through `/kedami:solution` (see Solutions and simulations in `agent-mode.md`), and it is stored and shown from storage after that.
- A confirmation popup comes first, stating that it shows the full solution. Viewing a solution doesn't complete the part; it still needs a correct answer or mark done.
- Solutions are short. Math and physics solutions are labels and math, no sentences.
  - Math: the method in a few words (such as "Integration by parts"), then the working as LaTeX lines down to the final answer.
  - Physics: Given (each known quantity with its value and unit), Required (each quantity asked for), then the solution, starting from the formula it uses and ending at the answer.
  - General: a few short Markdown lines, each one fact or step of reasoning from the course material, ending with a line that states the final answer. Short sentences are allowed; math is inline LaTeX.
- The whole solution shows at once. In math and physics, each line of math is display math centered in the lesson column, and the last line boxes the final answer. In general, lines are left-aligned Markdown, and the last line has an "Answer" label and is set in medium weight.
- Claude Code is given the course material and the whole problem, with the part to solve and the form its answer takes. It isn't given the stored answer, hints, or lesson content.
- The solution also gives its final answer in that form, which the server compares with the stored answer the way verification does. On a disagreement Claude Code is shown the stored answer and writes it once more; if they still disagree, the solution shows with a "Doesn't match the stored answer" label. `self_check` parts aren't compared.
- A solution is stored apart from the lesson JSON, in the `solutions` table, keyed by block and part ID.

## Simulations

- Placed where the section plan calls for one. Claude Code writes each one's code when the student asks, through `/kedami:simulation`.
- The code runs in a sandboxed frame with no network, no Node access, and no access to app data.
- The frame receives the design token values when it loads and uses them for all colors.
- The frame must report ready within a few seconds with no errors. Otherwise the block is hidden and flagged, and Regenerate asks Claude Code for a new one.
- Simulations are illustrative: they never count toward completion and never supply numbers the student is checked against.
- Each simulation has a regenerate button.
- The plan gives a section a one-line simulation brief only where one would teach what a static plot or diagram can't. The section places one `simulation` block (a caption) exactly when there is a brief. The block keeps the brief, and its code stays empty: Claude Code writes the code only when the student asks, so building the lesson never waits on it.
- The code is the body of `function simulation(root, canvas, tokens, ready)`: `root` is a div to build controls in, `canvas` is a 320 px tall canvas already in it, `tokens` holds the color token values and the font, and `ready()` must be called once it works. Code that never calls `ready(` is refused.
- The frame is a separate page, `simulation.html`, loaded with `sandbox="allow-scripts"` and no same-origin access. Its CSP allows no network. The ready window is 4 seconds; an error or timeout before ready flags the simulation on the server and shows a one-line notice with the regenerate button in its place.
- Simulation code is the one exception to never editing a lesson: it is stored apart from the lesson JSON, in the `simulations` table, and served in place of the JSON's empty code.

## Diagrams

- A diagram is a small static SVG with a `viewBox`, colored with `currentColor`, and sanitized with DOMPurify before rendering.
- The model places text by coordinate without seeing it drawn, so its text is monospace, where width follows from length. The root `svg` sets `font-family="monospace"` and a numeric `font-size`; no element sets another font family, and an element may set its own `font-size` as a number.
- When a section is assembled, the server measures each piece of text as 0.6 of its font size wide per character, 0.75 above the baseline, and 0.25 below. It rejects a diagram whose text runs past the `viewBox`, overlaps other text, or crosses the edge of a rectangle, circle, or ellipse, allowing 1 unit of slack. Lines, paths, and polygons aren't checked, so a label may sit on an arrow. A shape whose size isn't a plain number isn't checked either.
- Text the server can't measure is rejected: text with child elements such as `tspan`, text under a `transform` or a `style` attribute, a position that isn't a single number, a `text-anchor` other than `start`, `middle`, or `end`, and a `dominant-baseline` other than the default, `middle`, or `central`. Text inside `defs`, `marker`, and similar elements isn't drawn and isn't checked.
- A rejected diagram sends the section back to Claude Code with the problems found, like any other section error, to fix the diagram or leave it out.
- The check runs only while building. Lessons made before it are served as they are.

## Rules

- Worked examples and checkpoints never use an actual homework problem.
- All math strings use SymPy syntax. The restricted parser also accepts `^` for powers and `ln` and `abs` as aliases. It does not accept implicit multiplication such as `2x`.
- Display math in Markdown puts each `$$` on its own line. `$$...$$` on a single line renders as inline math.
- The server checks answers and samples points for static plots, so the renderer never parses SymPy.
- For plots with parameters, the server sends an expression tree that the renderer evaluates with plain arithmetic and `Math` functions, never as code. Nodes are numbers, names, sums, products, powers, and the whitelisted one-argument functions.
- The `verified` flag is set only by the server's comparison with the verifier subagent's second solve, never by what Claude Code sends with the lesson.
- Titles, section goals, and simulation briefs are plain text, not Markdown. A model sometimes writes a character as a literal escape such as `\u0394`; the server decodes these in plain-text fields when it reads a plan or a lesson, so they show as the character (Δ). The lesson JSON on disk is left as written.
- A model sometimes double-escapes the LaTeX in a Markdown field, writing `\\rightarrow` for `\rightarrow`. KaTeX reads `\\` as a line break, so the command name would show as text. When the server reads a lesson, it halves the backslashes in a math span if every backslash in the span is doubled and one comes before a command name. Text outside math is never changed, and the lesson JSON on disk is left as written.
