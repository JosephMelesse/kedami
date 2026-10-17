# SQL lessons

A computer science lesson in the `sql` domain teaches querying from a databases course's material. The student uploads the problem set and reference material, and, when the course gives one, its database. Query exercises are solved in the workspace and checked on the server by running the student's query and a reference query against a copy of the database and comparing their results. No model writes tables: practice exercises come from Spider, a hand-built bank of databases with questions and reference queries, and the course's homework runs against the course's own database.

## Exercise bank

- Source: Spider (`yale-lily.github.io/spider`), whose data is CC BY-SA 4.0. Its databases are SQLite files, each with questions written by people and a reference query for each.
- The student downloads the Spider release and runs `python -m kedami_server.import_spider {data folder} {spider_data folder}`. The import copies each database of at most 5 MB to `sql/databases/{db_id}.sqlite` in the data folder and writes `sql/exercises.jsonl`, replacing any earlier import, and prints how many exercises it kept and dropped, and why. Kedami never fetches Spider.
- The import takes Spider's train, dev, and test questions. It leaves out `train_others.json`, whose databases come from other datasets with their own terms.
- Every reference query runs at import under the rules in Running SQL safely. An exercise is kept when its query runs and returns between 1 and 200 rows. Spider phrases most queries twice; each distinct query on a database is kept once, with its first question.
- An exercise's ID is its database and a hash of its query, so it is the same after any import of the same release.
- The server reads each exercise's SQL features from its reference query: selecting (every query), filtering (`WHERE`), sorting (`ORDER BY`), limiting (`LIMIT`), distinct (`DISTINCT`), aggregates (`COUNT`, `SUM`, `AVG`, `MIN`, `MAX`), grouping (`GROUP BY`), having (`HAVING`), joins (`JOIN`), subqueries (a `SELECT` inside parentheses), set operations (`UNION`, `INTERSECT`, `EXCEPT`), and patterns (`LIKE`).
- When this was written, the import kept 5,325 exercises on 196 databases (24 MB). Of the questions it dropped, 4,148 repeated another's query, 344 returned no rows, 248 were on the three databases over 5 MB, 113 returned over 200 rows, and 3 didn't run.

**Known gaps, accepted**
- Spider's questions were written to test programs that turn questions into SQL, so they are plain and sometimes ambiguous about naming or order. Practice exercises are checkpoints, which don't count toward completion, so a doubtful one can be left.
- Spider has no window functions, CTEs, or date arithmetic. Those are taught in explanations and practiced only in course homework.

## Course databases

- On the Upload screen of a SQL lesson, one file can be tagged as the database: a SQLite file (`.sqlite` or `.db`) or a SQL script (`.sql`), at most 20 MB.
- A SQLite file must hold at least one table, pass SQLite's quick check, and have every table readable. It is never opened in place: its bytes are loaded into memory, in SQLite's defensive mode, without trusting its schema. A SQL script is run once, at upload, into a fresh in-memory database that it may fill with tables and rows but not attach, pragma, or load extensions from, within 10 seconds. Either way, the result is saved as `materials/{lesson_id}/databases/{name}.sqlite`, where the name is the file's, without its extension, in letters, digits, underscores, and hyphens. A file that fails is refused with SQLite's message.
- The database isn't a material: it isn't listed with the lesson's files, read in stage 1, or sent to the model as a file. The model sees its tables: each table's columns, row count, and first 5 rows, with the course material.
- Its table and column names are kept as the course wrote them.

## In a lesson

- The pipeline is the general one (see `pipeline.md`), with the SQL rules below.
- **Homework:** a problem part that asks for a query gets a `query` answer when the lesson has a course database: the model writes the reference query in stage 4, and verification checks it. Without a course database, the part is a `self_check` whose rubric says what a correct query does. Parts that don't ask for a query use the existing kinds: `choice`, `multi_choice`, `numeric`, or `self_check`.
- **Practice:** the plan (stage 3) names the SQL features each section teaches, from the list above. After stage 4, the server adds up to 3 bank exercises to the end of each section as checkpoints with `query` answers, with IDs `{section_id}-practice-{n}` and no hints. An exercise is eligible when it uses at least one feature the section teaches and none that isn't taught by then. Selecting counts as taught from the start, since every query selects. Exercises with fewer features come first; a section's exercises come from one database where possible; no exercise appears twice in a lesson. With nothing imported, sections have no practice exercises.
- The model chooses features only. It never writes or chooses a bank exercise's tables, question, or query.
- Code in lessons is SQL, in fenced `sql` blocks, highlighted with the same neutral tokens as Python.

## Query answers

| Field | Meaning |
|---|---|
| `database` | `bank/{db_id}` for a bank exercise, or `course/{name}` for a course database |
| `reference` | The reference query, in SQLite |
| `ordered` | Whether row order matters. Set by the server, never the model: true when the reference has an `ORDER BY` outside any parentheses, strings, and comments, so one in a window, subquery, or CTE doesn't count |
| `exercise` | For a bank exercise, its ID; otherwise null |

- A model-written reference must run and return between 1 and 200 rows. One that doesn't is sent back to the model as a rejected reply. An empty result is refused because almost any wrong query also returns nothing.

## Checking a query

- The student's query and the reference each run in a fresh in-memory copy of the database.
- **Columns:** the results must have the same number of columns, compared by position. Column names are ignored, so an alias doesn't matter.
- **Rows:** compared as lists when `ordered`, otherwise as multisets, so duplicates count and order doesn't.
- **Values:** null equals null. An integer equals a real of the same value (`2` and `2.0`), and reals are compared to 12 significant digits, so `0.1 + 0.2` equals `0.3`. Text is compared exactly, case included.
- A wrong result comes with one short reason, the first that applies: a different number of columns, a different number of rows, the same rows in the wrong order, or different rows. The reference's result is never shown.
- A query that fails to run (a syntax error, an unknown column, a write, a timeout) is rejected with SQLite's message and is not an attempt, like any malformed response (see `completion-and-verification.md`).

## Running SQL safely

SQL from the student, the bank, and the model runs on the server, so it is confined there.

- Every query runs in a fresh `:memory:` copy of its database, never in the database file, never in `kedami.db`, and the connection is closed after.
- A statement that starts with a word that begins no query, such as `INSERT`, `CREATE`, `PRAGMA`, `REINDEX`, or `VACUUM`, is refused before it is prepared, since SQLite doesn't ask the authorizer about every statement. Other words are left to SQLite, so a typo gets its syntax error.
- An authorizer allows only reading: selects, reads of the database's tables, functions, and recursive CTEs. It denies everything else, including writes inside a `WITH`, schema changes, transactions, `ATTACH` (which `VACUUM` also uses), and `PRAGMA` (which pragma table functions also use). Extension loading stays off.
- No database can be attached, and a string or blob is at most 1,000,000 bytes, so functions such as `randomblob()` can't use much memory.
- Only one statement runs: text with a second statement is refused.
- A progress handler stops a query after 2 seconds, which ends runaway recursive queries and huge joins.
- At most 1,000 rows are fetched. A result with more can't match any reference, so it is wrong. Text values are cut to 1,000 characters when shown.

## Workspace

The workspace from `code-problems.md`, with SQL in its panes. Its layout is unchanged (see Workspace in `ui.md`).

- **Description:** the part's or exercise's text, then the database's tables, each with its columns and its first 20 rows and a count of the rest, then the hints. A bank exercise ends with "From Spider (CC BY-SA 4.0)".
- **Editor:** SQL, highlighted like SQL code blocks, with long lines wrapped, and Vim as in `code-problems.md`. It opens with the saved query or, if none, empty.
- **Run** executes the query and shows its result as a table, at most 100 rows with the count of the rest. It is not an attempt.
- **Submit** checks the query through the usual check route. The console shows Correct, or Incorrect with the reason and the student's own result. A query that can't run shows SQLite's message as an error. A correct part is locked as usual; Run still works.
- The query is saved when typing stops for one second, and on Run and Submit, as code is, through the same save route.
- In the lesson, a query part or checkpoint shows its text, its state label, and a Solve button that opens the workspace. Mark done works as for any part. A checkpoint can't be marked done.

## Generation

- **Extraction** is the general one.
- **Planning** adds each section's SQL features.
- **Sections** follow the SQL rules: worked examples use the course database when there is one, and no lesson content gives the query for an assigned problem.
- **Hints** are written from the part's text and the database's tables. Besides the small judge, the cheap check refuses a hint that contains the reference query, compared without case or spacing.
- **Verification:** for a model-written reference, the second solver sees the problem, the course database's tables, and that the answer is a query. It writes its own query, which is checked against the reference by the rules above. Agreement marks the part verified; disagreement leaves the "Unverified answer" label, and mark done is the way past it. Bank exercises aren't verified, since their references come from the bank, and show no "Unverified answer" label.
- **Solutions:** no part of a SQL lesson has one yet, as in DSA lessons (see Not included).

## Storage and API

- The data folder gains `sql/databases/` and `sql/exercises.jsonl` from the import. A lesson's course database is in `materials/{lesson_id}/databases/`, so deleting the lesson deletes it.
- After a rerun, a query part's last query and state stand while it is still a query part, as a code part's do: rechecking would need its database.
- The lesson JSON gains the `query` answer kind. Progress stores the last query as the last response.
- `GET /lessons/{id}/blocks/{block_id}/tables` returns the tables of a query part's or checkpoint's database: each table's columns, its first 20 rows, and its row count.
- `POST /lessons/{id}/blocks/{block_id}/run-query` runs a query for a part or checkpoint against its database, without checking it, and returns the columns, the rows (at most 100), the total row count, and any error.
- `POST /lessons/{id}/blocks/{block_id}/check` checks a query like any response. For a query it also returns the reason it is wrong and the student's result, as Run returns it.

## Not included

Out of scope for this project:
- Dialects other than SQLite. A course taught in PostgreSQL or MySQL still works for standard SQL, but its own functions, such as `ILIKE` or `DATE_TRUNC`, don't run, and references are written in SQLite.
- Exercises that change data or schema (`INSERT`, `UPDATE`, `DELETE`, `CREATE`) and transactions. Questions about them use the existing answer kinds.
- Query plans and performance.

Cut to ship faster (backlog):
- Solutions for query parts on request.
- Showing a database's tables in the lesson itself, beside the explanations.
- Flagging a bank exercise as broken.
- Spider's three databases over 5 MB.

## Most likely to be wrong

Comparing results and the authorizer, which are built and tested. Next: choosing practice exercises by feature (an exercise must never use a feature the lesson hasn't taught yet) and running an uploaded SQL script, which may write but must stay in its own database. These get tests first.
