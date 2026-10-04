# Lesson format

A lesson is a JSON document. It is produced by stage 4, never edited in place, and replaced only by a rerun.

The server's Pydantic models in `server/kedami_server/lesson.py` are the source of truth. The JSON Schema exported from them is committed at `server/schema/lesson.schema.json`, and the renderer's TypeScript types are generated from it. Field names below are the JSON keys.

## Structure

| Level | Fields |
|---|---|
| Lesson | `schema_version` (currently 1), `id`, `title`, `subject` (`math`, `physics`, or `computer_science`), `source_files`, `sections` |
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
| `external` | `platform` (`leetcode`), `number`, `title`, `slug` | Not checked. The student solves it on LeetCode and marks it done. Problem parts only |

## Computer science lessons

- The problem set is a list of LeetCode problems, one per line, each with its number and title, such as `1. Two Sum`. Blank lines and Markdown headings are ignored; any other line is an error, as are a missing title and a repeated number.
- Each listed problem becomes a problem block with source reference `LeetCode #N` and one part with an `external` answer. Its text is "Complete LeetCode #N: Title." and it links to `https://leetcode.com/problems/{slug}/`, where the slug is the title lowercased, with characters other than letters, digits, spaces, and hyphens removed and spaces turned into hyphens (`Pow(x, n)` becomes `powx-n`).
- The problem list is parsed by the server, not the model. The model maps each problem to the concepts it needs, and must cover every listed number exactly once.
- Comprehension checks use the existing answer kinds: `choice` and `multi_choice` for complexity and approach, `numeric` for questions such as what a snippet prints, and `self_check` for explanations.
- Code in lessons is Python, in fenced `python` blocks. No lesson content walks through a solution to an assigned LeetCode problem.

## Hints

- Generated with the lesson, ordered from gentle to specific, revealed one at a time.
- Hard cap of 3 per part and per checkpoint.
- Hints never give a full solution. A worked solution for a problem part is shown only when the student asks for one; see Solutions.
- Each hint passes two checks: the answer does not appear in it, and a small check judges that it doesn't give the answer away. A failing hint is regenerated once, then dropped.

## Solutions

- Every problem part in a math or physics lesson has a Show solution button. Lesson generation writes nothing for it, as with simulations: a separate call writes the solution the first time the student asks, and it is stored and shown from storage after that.
- A confirmation popup comes first, stating that it shows the full solution. Viewing a solution doesn't complete the part; it still needs a correct answer or mark done.
- Solutions are short: labels and math, no sentences.
  - Math: the method in a few words (such as "Integration by parts"), then the working as LaTeX lines down to the final answer.
  - Physics: Given (each known quantity with its value and unit), Required (each quantity asked for), then the solution, starting from the formula it uses and ending at the answer.
- The whole solution shows at once. Each line of math is display math centered in the lesson column, and the last line boxes the final answer.
- The call sees the course material and the whole problem, with the part to solve and the form its answer takes. It doesn't see the stored answer, hints, or lesson content.
- The reply also gives its final answer in that form, which the server compares with the stored answer the way verification does. On a disagreement the call is repeated once with the stored answer shown; if they still disagree, the solution shows with a "Doesn't match the stored answer" label. `self_check` parts aren't compared.
- A solution is stored apart from the lesson JSON, in the `solutions` table, keyed by block and part ID. A rerun replaces the lesson and clears these rows.
- `external` parts (computer science) have no solutions.

## Simulations

- Requested where the section plan calls for one; each is a separate model call.
- The code runs in a sandboxed frame with no network, no Node access, and no access to app data.
- The frame receives the design token values when it loads and uses them for all colors.
- The frame must report ready within a few seconds with no errors. Otherwise the block is hidden and flagged for regeneration.
- Simulations are illustrative: they never count toward completion and never supply numbers the student is checked against.
- Each simulation has a regenerate button.
- The plan gives a section a one-line simulation brief only where one would teach what a static plot or diagram can't. The section call places one `simulation` block (a caption) exactly when there is a brief. The block keeps the brief, and its code stays empty: the code is written by a separate call only when the student clicks Generate simulation, so lesson generation never waits on it.
- The code is the body of `function simulation(root, canvas, tokens, ready)`: `root` is a div to build controls in, `canvas` is a 320 px tall canvas already in it, `tokens` holds the color token values and the font, and `ready()` must be called once it works. Code that never calls `ready(` is rejected and retried.
- The frame is a separate page, `simulation.html`, loaded with `sandbox="allow-scripts"` and no same-origin access. Its CSP allows no network. The ready window is 4 seconds; an error or timeout before ready flags the simulation on the server and shows a one-line notice with the regenerate button in its place.
- Written and regenerated code is the one exception to never editing a lesson: it is stored apart from the lesson JSON, in the `simulations` table, and served in place of the JSON's empty code. A rerun replaces the lesson and clears these rows.

## Rules

- Worked examples and checkpoints never use an actual homework problem.
- All math strings use SymPy syntax. The restricted parser also accepts `^` for powers and `ln` and `abs` as aliases. It does not accept implicit multiplication such as `2x`.
- Display math in Markdown puts each `$$` on its own line. `$$...$$` on a single line renders as inline math.
- The server checks answers and samples points for static plots, so the renderer never parses SymPy.
- For plots with parameters, the server sends an expression tree that the renderer evaluates with plain arithmetic and `Math` functions, never as code. Nodes are numbers, names, sums, products, powers, and the whitelisted one-argument functions.
- The `verified` flag is set only by the server's verification pass, never by the model.
- Titles, section goals, and simulation briefs are plain text, not Markdown. A model sometimes writes a character as a literal escape such as `\u0394`; the server decodes these in plain-text fields when it reads a plan or a lesson, so they show as the character (Δ). The lesson JSON on disk is left as written.
