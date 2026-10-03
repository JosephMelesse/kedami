# Completion and verification

## Completion

- A part is done when it is answered correctly or marked done.
- A problem is done when every part is done.
- A lesson is done when every problem is done.
- Checkpoints never count toward completion.

## Part states

| State | Trigger | Label | Border |
|---|---|---|---|
| Not started | No interaction yet | None | `--border` |
| In progress | Hint revealed, no answer submitted | "In progress" in `--in-progress` | `--border` |
| In progress, wrong | Last submitted answer is wrong | "In progress" in `--in-progress` | `--retry` |
| Correct | Answer checked correct | "Correct" in `--correct` | `--correct` |
| Marked done | Confirmed manually | "Marked done" in `--text-muted` | `--border` |

- States apply per part and show on that part's answer field.
- A multi-part card shows a count in its header, such as "2 of 3 parts done".
- Checkpoints use the same states, except marked done.
- Attempts are unlimited.

## Mark done

- Available on every problem part, for work solved on paper or when the stored answer is unverified.
- A confirmation popup appears first, stating that the answer won't be checked.
- It is recorded as its own status, distinct from correct.
- It can be undone, which returns the part to its previous state.

## Checking a response

- The renderer sends the response to the server, which checks it by answer kind (see `lesson-format.md`).
- The server records the response, attempt count, and new state.
- For `self_check`, the student's own judgment after seeing the rubric is recorded as the result.

## Verifying stored answers

- During stage 4, a second, independent model call solves each part and checkpoint from scratch.
- If SymPy finds the two results equivalent, the item is marked verified.
- If not, it shows an "Unverified answer" label. For problem parts, mark done is the way past it.
- `self_check` answers are not verified.
