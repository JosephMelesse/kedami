# Lesson format

A lesson is a JSON document. It is produced by stage 4, never edited in place, and replaced only by a rerun.

## Structure

| Level | Fields |
|---|---|
| Lesson | schema version, id, title, subject (math or physics), source files, sections |
| Section | id, title, goal (one line), blocks |
| Block | id, type, plus the fields for that type |

**IDs**
- Block IDs are unique within a lesson.
- A problem block's ID is derived from its source reference. A part's ID is derived from its label.

## Blocks

| Block | Purpose | Fields | Counts toward completion |
|---|---|---|---|
| `explanation` | Teach a concept | body (Markdown with LaTeX) | No |
| `worked_example` | A similar problem solved in steps, revealed one at a time | prompt, steps | No |
| `plot` | Functions over a domain | functions (expression, label), optional parameters (name, min, max, default), x domain, optional y domain, caption | No |
| `diagram` | Static figure | svg, caption | No |
| `simulation` | Interactive canvas simulation | code, caption | No |
| `checkpoint` | Model-written practice question | prompt, answer, hints, verified | No |
| `problem` | A real homework item | source reference, shared prompt, parts | Yes |

**Problem parts**
- Each part has an id, label, prompt, answer, hints, and a verified flag.
- A single-part problem is a problem with one part.

## Answer kinds

| Kind | Fields | Checked by |
|---|---|---|
| `numeric` | value, relative tolerance (default 1%), optional unit | Value within tolerance. The unit is shown beside the input; the student enters the number only. |
| `expression` | expression | Symbolic equivalence in SymPy, numeric sampling as fallback |
| `self_check` | rubric | The rubric is shown after the student commits; they grade themselves |
| `choice` | options, correct index | Index match |
| `multi_choice` | options, correct indexes | Exact set match, for "select all that apply" |

## Hints

- Generated with the lesson, ordered from gentle to specific, revealed one at a time.
- Hard cap of 3 per part and per checkpoint.
- There is no full-solution reveal for problems.
- Each hint passes two checks: the answer does not appear in it, and a small check judges that it doesn't give the answer away. A failing hint is regenerated once, then dropped.

## Simulations

- Requested where the section plan calls for one; each is a separate model call.
- The code runs in a sandboxed frame with no network, no Node access, and no access to app data.
- The frame receives the design token values when it loads and uses them for all colors.
- The frame must report ready within a few seconds with no errors. Otherwise the block is hidden and flagged for regeneration.
- Simulations are illustrative: they never count toward completion and never supply numbers the student is checked against.
- Each simulation has a regenerate button.

## Rules

- Worked examples and checkpoints never use an actual homework problem.
- All math strings use SymPy syntax.
- The server checks answers and samples points for static plots, so the renderer never parses SymPy.
- For plots with parameters, the server sends an expression form that the renderer evaluates with a math library, never as code.
- The `verified` flag is set only by the server's verification pass, never by the model.
