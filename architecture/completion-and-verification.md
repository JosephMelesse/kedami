# Completion and verification

## Completion

- A part is done when it is answered correctly or marked done.
- A problem is done when every part is done.
- A lesson is done when every problem is done.
- Checkpoints never count toward completion.
- Viewing a problem part's solution doesn't complete it.

## Part states

| State | Trigger | Label | Border |
|---|---|---|---|
| Not started | No interaction yet | None | `--border` |
| In progress | Hint revealed, no answer submitted | "In progress" in `--in-progress` | `--border` |
| In progress, wrong | Last submitted answer is wrong | "In progress" in `--in-progress` | `--retry` |
| Correct | Answer checked correct | "Correct" in `--correct` | `--correct` |
| Marked done | Confirmed manually | "Marked done" in `--text-muted` | `--border` |

- States apply per part and show on that part's answer field.
- "In progress, wrong" is not stored separately: it is an in-progress part with a recorded response. A correct response always moves a part to correct.
- A multi-part card shows a count in its header, such as "2 of 3 parts done".
- Checkpoints use the same states, except marked done.
- Attempts are unlimited until a part is correct. A correct part is locked: no more checks and no mark done.
- A malformed response (not a number, an unreadable expression, a name not in the stored answer) is rejected with a message and does not count as an attempt.
- Revealing a hint asks for "hints up to n", so repeating the request changes nothing.

## Mark done

- Available on every problem part, for work solved on paper or when the stored answer is unverified.
- A confirmation popup appears first, stating that the answer won't be checked.
- It is recorded as its own status, distinct from correct.
- It can be undone, which returns the part to its previous state: in progress if a response or hint was recorded, otherwise not started.
- A marked part accepts no checks until it is undone.

## Checking a response

- The renderer sends the response to the server, which checks it by answer kind (see `lesson-format.md`).
- The server records the response, attempt count, and new state.
- Numeric: a stored value of zero uses the tolerance as an absolute one.
- Expression: the response may use only the names in the stored answer. SymPy simplification is tried first; otherwise both sides are compared at 8 points with every name drawn from 0.5 to 3 with a fixed seed, so a response always gets the same result.
- For `self_check`, the student's own judgment after seeing the rubric is recorded as the result.

## Verifying stored answers

- During stage 4, a second, independent model call solves each part and checkpoint from scratch: one call per section, after its hints.
- The solver sees the course material and each question with the form its answer takes (a number in a given unit, an expression in given names, or the options). It never sees the stored answer, the hints, or the lesson content.
- If SymPy finds the two results equivalent, the item is marked verified. Numbers agree within the stored tolerance, expressions by the same equivalence check used for student answers, and choices by the selected indexes.
- A verification call whose replies stay malformed after its retries leaves the section unverified rather than failing the lesson. An API error still fails the lesson.
- Each section's results, with both answers, are saved to `work/{lesson_id}/verification-{n}.json`.
- If not, it shows an "Unverified answer" label. For problem parts, mark done is the way past it.
- `self_check` answers are not verified.
- `external` answers (LeetCode problems in computer science lessons) are not checked or verified, and show no "Unverified answer" label. Mark done is the only way to finish them.
