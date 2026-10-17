# Code problems

In a computer science lesson, each assigned LeetCode problem is shown in Kedami with an editor below it. The student writes Python, runs it in a sandboxed frame, and submits it against the problem's tests. The tests come from LeetCodeDataset, imported once by hand.

## Dataset

- Source: LeetCodeDataset (`github.com/newfacade/LeetCodeDataset`, also on Hugging Face), for personal use. It has 2,869 problems, each a method on a `Solution` class with a check function of about 100 asserts.
- The student downloads its JSONL files and runs `python -m kedami_server.import_leetcode {data folder} {jsonl files...}`. The import writes `leetcode.jsonl` to the data folder, replacing any earlier import, and prints how many problems it kept and dropped, and why. Kedami never fetches the dataset.
- Kept per problem: number, slug, difficulty, description, starter code, method name, and tests. Reference solutions, input/output pairs, prompt text, and the dataset's helper code are dropped. The runner has its own helpers.
- The import reads each check function with Python's `ast` parser and never runs it. Each top-level assert becomes one test with its arguments, expected value, and comparison:

| Assert | Comparison |
|---|---|
| `candidate(args) == expected` | `equal` |
| `is_same_list(candidate(args), expected)` | `same_list` |
| `is_same_tree(candidate(args), expected)` | `same_tree` |

- Arguments and expected values are kept as Python source, such as `nums = [3, 3], target = 6` and `[0, 1]`, and may call `list_node` and `tree_node`. They are evaluated only in the runner, never on the server.
- A problem is dropped if it has no tests, if any assert has another shape, or if its method returns `None`. Such a method changes its input in place, and the dataset's tests only check that nothing is returned. When this was written, every assert had one of the three shapes and 19 problems returned `None`.

**Known gaps, accepted**
- Design problems (classes such as LRU Cache) and some others (such as Clone Graph) aren't in the dataset. They are solved on LeetCode and marked done, as before.
- Expected values come from one reference solution and are compared exactly. A problem that accepts answers in any order (Two Sum, Group Anagrams) fails a correct answer given in another order. Mark done and flags are the ways past it. Floats are compared exactly too.
- Descriptions are text scraped from LeetCode, with superscripts flattened: 10^4 reads "104" and O(n^2) reads "O(n2)". The LeetCode link beside each problem shows the original.
- The tests' inputs were written by a model, so edge cases may be thin, and some go far beyond LeetCode's input limits: one Coin Change test has an amount of 8,675,309 where LeetCode allows 10^4. A correct solution can run past the time limit on such a test. Flags are the way past it.
- Pyodide is 32-bit, so a `range` longer than 2^31 overflows (as in `bisect_left(range(10**10), ...)`) and memory runs out sooner than on LeetCode. It has no threads. When this was written, the dataset's own reference solutions failed 13 problems this way.

## In a lesson

- The problem list is parsed as before (see Computer science lessons in `lesson-format.md`). At stage 2, each listed number is looked up in `leetcode.jsonl`.
- A problem in the dataset gets a `code` answer, and its part prompt is the problem's description. A problem not in the dataset, or every problem when nothing has been imported, gets an `external` answer: solved on LeetCode and marked done. A missing problem never fails the lesson.
- If a listed title's slug differs from the dataset's slug for that number, the problem list is rejected with the line named, since the number is probably wrong.
- Every problem keeps its LeetCode link.
- In the lesson, a code problem's block shows its title, difficulty, the part's state label, the LeetCode link, mark done, and a Solve button, the primary action, which opens the workspace. The description is shown only in the workspace.

## Workspace

A LeetCode-style screen for one code problem: the description on the left, the editor on the right, and the console below the editor. See Workspace in `ui.md` for the layout.

- **Description:** the problem's description as plain text with its line breaks kept, not as Markdown, since it contains `*` and `_` in code-like text. Above it, the title, difficulty, the part's state label, and the LeetCode link. Below it, the part's hints, revealed one at a time as in the lesson.
- **Editor:** a Python editor opening with the saved code or, if none, the starter code. Code is set in JetBrains Mono with ligatures off, highlighted like Python code blocks (see Consistency in `ui.md`), on `--surface-raised`. Tab inserts four spaces.
- The code is saved when typing stops for one second, and on Run and Submit. Reset returns to the starter code after a confirmation popup.
- **Console:** shows the last Run or Submit. It is output only, with no typed input, so code that reads input gets an error. Before any run it shows a muted line saying results appear here.
- **Run** tries the first three tests that aren't flagged. The console shows each one's input, expected value, what the code returned, and whether it passed, then any printed output and any error. A Run is not an attempt.
- **Submit** is the primary action. It runs every test that isn't flagged, in order, and the console shows how many have passed while it runs. It stops at the first failure, showing "Failed test 12 of 100" with that test's input, expected value, and what the code returned. If every test passes, the part is correct.
- Run and Submit sit along the bottom of the console. While a run is going, both are disabled. Results are colored by the border and a short label per the feedback rule in `ui.md`.
- The runner starts when a lesson with code parts opens, so the first Run doesn't wait for Pyodide. Until it is ready, Run and Submit show "Starting Python".

## Runner

- A separate page, `runner.html`, loaded with `sandbox="allow-scripts"` and no same-origin access. Its CSP allows no network and allows WebAssembly.
- Python is Pyodide, at a pinned version, bundled with the app with one package: `sortedcontainers`, which LeetCode provides. It runs in a worker inside the frame, which is started when a lesson with code parts opens and reused between runs.
- Having no origin, the frame can't load scripts, workers, or files. Main reads Pyodide's binaries from the installed package, and the renderer posts them to the frame with the frame's script, which is bundled with the worker's. The worker starts from a data URL of its source, since Chromium refuses a blob URL made in a frame with no origin.
- The renderer posts the code, the method name, and the tests to the frame. Each Run or Submit starts from a fresh namespace: the runner's preamble (the imports LeetCode provides, including `SortedList`, then `ListNode`, `TreeNode`, `list_node`, `tree_node`), then the student's code, then each test calling `Solution().{method}({args})`. The worker reports each test's result as it finishes.
- `equal` compares with Python's `==`. `same_list` and `same_tree` compare node values and shape.
- Each test has 10 seconds, timed from when the previous test finished (or, for the first, from when the code was posted), not counting Pyodide's startup. Past that, the frame ends the worker, reports "Time limit exceeded" as that test's failure, and starts a fresh one. The limit stops runaway loops; it doesn't judge speed. A timed-out test can be flagged like any failed test.
- Returned values are shown with `repr`, and printed output with its last lines. Each is cut to 1,000 characters.

## Completion

- Each Submit is an attempt. Passing every unflagged test makes the part correct. A failure leaves it in progress with the `--retry` border.
- The renderer sends the result and the code to the server, which records them. The server can't run the code, so it trusts the result. This is acceptable for a single user.
- A correct part is locked: Submit goes away, but editing and Run still work.
- Saving code changed from the starter code puts a part in progress.
- Mark done works as for any part.
- Code parts have hints like any problem part, written from the description, but no solutions and no verification, and show no "Unverified answer" label.

## Flags

- A failed test's result has a Flag as broken button. Flagged tests are skipped by Run and Submit.
- A problem with flags shows "2 tests flagged" and a Clear flags button.
- Flags are saved on the server, keyed by lesson, block, part, and the test's text (arguments and expected value), so a rerun keeps them while the test still exists.
- Flagging doesn't change a part's state. The next Submit decides it.

## Not included

Languages other than Python, custom test input, judging speed or memory, design problems, reference solutions, and answers accepted in any order. SQL is in the backlog.

## Most likely to be wrong

The harness: turning asserts into tests, building lists and trees, comparing results, and stopping runaway code without freezing the app. Loading Pyodide in a worker inside a frame with no origin is the riskiest part of that. These get tests first: the import in pytest against sample dataset records covering every assert shape and every reason to drop a problem, and the harness in Node with the bundled Pyodide.
