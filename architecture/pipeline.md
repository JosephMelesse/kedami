# Pipeline

Each stage writes its output to disk, so any stage can be rerun alone.

| # | Stage | Input | Output |
|---|---|---|---|
| 1 | Ingest | Files, each tagged as problem set or reference | Normalized Markdown with LaTeX per page, plus the route each page took |
| 2 | Extract | Normalized text | Problem list with parts, concept list, problem-to-concept map |
| 3 | Plan | Extracted structure | Ordered sections, each with a goal, concepts, and target problems |
| 4 | Generate and verify | Plan plus source passages | Lesson JSON |
| 5 | Render and track | Lesson JSON | Interactive lesson, saved progress |

Stages 1 to 4 run as a background job on the server. The renderer polls lesson status and shows the current stage.

- Uploads are checked before anything is saved: at most 20 files, 30 MB each, and 100 pages in all. File names are made safe and unique in the materials folder.
- A stage whose reply is rejected (schema or rule violation) is retried up to 3 attempts, with the reason fed back. Temporary API failures (overload, rate limit, server errors, dropped connections, including an overload reported mid-stream) are retried after waits of 5, 15, and 45 seconds. Any other API error fails the lesson at once.
- A failed lesson records the reason, which the Generating screen shows.
- Generation runs inside the server process, so a lesson still generating when the app closes is marked failed on the next start.

## Upload rules

- At least one file must be tagged as a problem set.
- Supported inputs are PDF, images, plain text, and Markdown.
- Each file has a "force transcription" toggle.

## Stage 1: page routing

| Page type | Route | Decided by |
|---|---|---|
| Image file | Transcribe | File type |
| Any page in a file with force transcription on | Transcribe | Toggle |
| PDF page with no or negligible text layer | Transcribe | Local check |
| PDF page with a text layer | Keep the text if clean, otherwise transcribe | Small check |
| Plain text or Markdown | Keep | File type |

- "Transcribe" means a vision-capable model converts the page image to Markdown with LaTeX.
- The route and reason for each page are saved with the stage output (`pages.json`).
- "Negligible" means fewer than 40 non-space characters. The small check rules on all of a file's text-layer pages in one call, and a page it gives no verdict for is transcribed.
- Force transcription has no effect on text and Markdown files.
- Pages are joined into one normalized document per role, each page marked with its file and page number. Blank pages are left out. A problem set with no readable text fails the lesson.

## Stage 2: extraction

- Every problem in the problem set is captured with its source reference (for example, "PS3 #4") and its parts.
- For a computer science lesson, the server parses the LeetCode problem list itself and the model only maps problems to concepts. See `lesson-format.md`.
- Concepts are drawn from the reference material and linked to the problems that need them.

## Stage 3: sequencing rules

- A concept is introduced before any problem that needs it.
- Each problem appears in the section where its last prerequisite is covered.
- Every problem appears exactly once.
- The model orders sections and assigns each needed concept to exactly one of them. The server then places each problem in the section of its last prerequisite, so the rules hold by construction. A problem with no prerequisites goes in the first section, and a section with no concepts and no problems is dropped.

## Stage 4: generation

- One model call per section. A failed or invalid section is retried alone.
- The model places each of the section's problems among the teaching blocks and gives their answers by part label. The server inserts the problem and part text verbatim from extraction.
- Teaching block IDs are `{section_id}-block-{n}`.
- Hint checks: the cheap check looks for the answer in the hint (a number within tolerance, the expression, or the correct option). Integer answers below 10 are left to the small model, since they appear in ordinary working. A hint the small model doesn't rule on counts as failing.
- Hints, simulations, and verification run after the section content exists.
- See `lesson-format.md` for the output and `completion-and-verification.md` for verification.

## Reruns

- A rerun starts from a chosen stage and repeats every stage after it.
- A bad page is fixed by turning on force transcription for its file and rerunning from stage 1.
- A rerun replaces the lesson JSON and increments the lesson's revision.
- A rerun can start from stage 1 if the lesson has uploaded files, and from stage k > 1 only if the saved outputs of stages 1 to k-1 are on disk. Changing a force-transcription toggle requires starting from stage 1.
- Outputs of the stages being redone are deleted first, so nothing is left over from a longer earlier run.
- A rerun that fails, or is interrupted by the app closing, leaves the previous lesson and its progress in place. The lesson stays ready and shows why the rerun failed.

**Progress carries over**
- Problem block IDs are derived from the source reference and part IDs from the part label, so they stay the same across reruns.
- Each saved response is rechecked against the new stored answer, and the part's state is updated. A response that no longer fits the answer's form counts as wrong. A self check's result is the student's own judgment, so it stands while the part is still a self check.
- Hints used is capped at the new number of hints.
- Parts that were marked done stay marked done.
- Progress for parts that no longer exist is deleted. Checkpoint progress resets.
