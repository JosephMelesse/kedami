# SQL lessons

A computer science lesson in the `sql` domain teaches querying from a databases course's material. The student uploads the problem set and reference material, as for a general lesson. Each exercise that asks for a query is solved in the workspace against small tables the lesson carries, in SQLite, and checked on the server by comparing its result with a reference query's.

## In a lesson

- The Upload screen's domain choice gains SQL. A SQL lesson has a file drop like any non-DSA lesson: a problem set and any reference files.
- The pipeline is the general one (see `pipeline.md`), with SQL rules in extraction and section generation, described below.
- A part or checkpoint that asks for a query gets a `query` answer. Any other part, such as a question about normalization or which index helps, uses the existing kinds: `choice`, `multi_choice`, `numeric`, or `self_check`.
- Checkpoints may have `query` answers, so a lesson can give SQLBolt-style practice queries between its explanations.
- Code in lessons is SQL, in fenced `sql` blocks, highlighted with the same neutral tokens as Python.

## Datasets

The tables a lesson's queries run against.

- A SQL lesson has `datasets`: each with an `id`, a `title`, and `tables`. A table has a `name`, `columns` (each a `name` and a `type`: `INTEGER`, `REAL`, or `TEXT`), and `rows`, each a list of values matching the columns, where a value may be null. Dates are ISO text, as SQLite keeps them.
- Limits: at most 4 datasets, 8 tables in a dataset, 12 columns in a table, and 40 rows in a table. Names are SQL identifiers: letters, digits, and underscores, not starting with a digit, and not SQL keywords.
- Datasets are written in stage 2. The model takes each schema from the problem set where it gives one, keeping its table and column names, and writes the rows. Where the course works on a database too large to carry, such as a sample database, the model writes a small one with the same schema and says so in the dataset's title.
- Rows are written to tell right queries from wrong ones: they include nulls, ties, duplicates, rows that a join leaves unmatched, and values on each side of any boundary an exercise mentions.
- The server builds every dataset in a fresh in-memory database when stage 2 ends. A dataset that won't build (a row of the wrong length, a value of the wrong type) sends the reason back to the model, as for any rejected reply.
- Datasets are part of the lesson JSON, which is never edited in place, so a rerun from stage 2 replaces them.

## Query answers

| Field | Meaning |
|---|---|
| `dataset` | The `id` of the dataset the query runs against |
| `reference` | The reference query, in SQLite |
| `ordered` | Whether row order matters. Set by the server, never the model: true when the reference ends with `ORDER BY` outside any parentheses |

- A reference must run, return between 1 and 200 rows, and take under the time limit. One that doesn't is sent back to the model as a rejected reply. An empty result is refused because almost any wrong query also returns nothing.

## Checking a query

- The student's query and the reference each run in a fresh in-memory copy of the dataset.
- **Columns:** the results must have the same number of columns, compared by position. Column names are ignored, so an alias doesn't matter.
- **Rows:** compared as lists when `ordered`, otherwise as multisets, so duplicates count and order doesn't.
- **Values:** null equals null. An integer equals a real of the same value (`2` and `2.0`), and reals are equal within a relative 1e-9. Text is compared exactly, case included.
- A wrong result comes with one short reason, the first that applies: a different number of columns, a different number of rows, the same rows in the wrong order, or different rows. The reference's result is never shown.
- A query that fails to run (a syntax error, an unknown column, a write, a timeout) is rejected with SQLite's message and is not an attempt, like any malformed response (see `completion-and-verification.md`).

## Running SQL safely

SQL from the student and from the model runs on the server, so it is confined there.

- Every query runs in a fresh `:memory:` database built from its dataset, never in `kedami.db`, and the connection is closed after.
- An authorizer allows only reading: selects, reads of the dataset's columns, and functions. It denies everything else, including writes, schema changes, transactions, `ATTACH`, and `PRAGMA`. Extension loading stays off.
- Only one statement runs: text with a second statement is refused.
- A progress handler stops a query after 2 seconds, which ends runaway recursive queries and huge joins.
- At most 1,000 rows are fetched. A result with more can't match any reference, so it is wrong. Text values are cut to 1,000 characters when shown.

## Workspace

The workspace from `code-problems.md`, with SQL in its panes. Its layout is unchanged (see Workspace in `ui.md`).

- **Description:** the part's text, then the dataset's tables, each with its columns and rows, then the hints.
- **Editor:** SQL, highlighted like SQL code blocks. It opens with the saved query or, if none, empty.
- **Run** executes the query and shows its result as a table, at most 100 rows with the count of the rest. It is not an attempt.
- **Submit** checks the query through the usual check route. The console shows Correct, or the reason it is wrong with the student's own result. A correct part is locked as usual; Run still works.
- The query is saved when typing stops for one second, and on Run and Submit, as code is.
- There are no flags, since the lesson's own reference is checked by verification instead.
- In the lesson, a query part or checkpoint shows its text, its state label, and a Solve button that opens the workspace. Mark done works as for any part. A checkpoint can't be marked done.

## Generation

- **Extraction** returns problems, concepts, and datasets. Each dataset is validated and built (see Datasets).
- **Sections** follow the SQL rules: query answers name a dataset of the lesson, worked examples use the lesson's datasets, and no lesson content gives the query for an assigned problem.
- **Hints** are written from the part's text and the dataset's schema. Besides the small judge, the cheap check refuses a hint that contains the reference query, compared without case or spacing.
- **Verification:** the second solver sees the problem, the dataset, and that the answer is a query. It writes its own query, which is checked against the reference by the rules above. Agreement marks the part verified; disagreement leaves the "Unverified answer" label, and mark done is the way past it.
- **Solutions:** query parts have none yet (see Not included).

## Storage and API

- The lesson JSON gains `datasets` (empty for other lessons), and the `query` answer kind. Progress stores the last query as the last response.
- `POST /lessons/{id}/blocks/{block_id}/run-query` runs a query for a part or checkpoint against its dataset, without checking it, and returns the columns, the rows (at most 100), the total row count, and any error.
- `POST /lessons/{id}/blocks/{block_id}/check` checks a query like any response. For a query it also returns the reason it is wrong and the student's result, as Run returns it.

## Not included

Out of scope for this project:
- Dialects other than SQLite. A course taught in PostgreSQL or MySQL still works for standard SQL, but its own functions, such as `ILIKE` or `DATE_TRUNC`, don't run, and the reference is written in SQLite.
- Exercises that change data or schema (`INSERT`, `UPDATE`, `DELETE`, `CREATE`) and transactions. Questions about them use the existing answer kinds.
- Query plans and performance.

Cut to ship faster (backlog):
- Solutions for query parts on request.
- Importing a database from the course files, such as a `.sqlite` or `.sql` file, in place of model-written rows.
- Showing a dataset's tables in the lesson itself, beside the explanations.

## Most likely to be wrong

Comparing results (order, duplicates, nulls, integers against reals) and the authorizer (allowing every read, including CTEs, window functions, and subqueries, while denying every write and `ATTACH`). These get tests first, on the server, before any generation or UI.
