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
- The route and reason for each page are saved with the stage output.

## Stage 2: extraction

- Every problem in the problem set is captured with its source reference (for example, "PS3 #4") and its parts.
- Concepts are drawn from the reference material and linked to the problems that need them.

## Stage 3: sequencing rules

- A concept is introduced before any problem that needs it.
- Each problem appears in the section where its last prerequisite is covered.
- Every problem appears exactly once.

## Stage 4: generation

- One model call per section. A failed or invalid section is retried alone.
- Hints, simulations, and verification run after the section content exists.
- See `lesson-format.md` for the output and `completion-and-verification.md` for verification.

## Reruns

- A rerun starts from a chosen stage and repeats every stage after it.
- A bad page is fixed by turning on force transcription for its file and rerunning from stage 1.
- A rerun replaces the lesson JSON and increments the lesson's revision.

**Progress carries over**
- Problem block IDs are derived from the source reference and part IDs from the part label, so they stay the same across reruns.
- Each saved response is rechecked against the new stored answer, and the part's state is updated.
- Parts that were marked done stay marked done.
- Progress for parts that no longer exist is deleted. Checkpoint progress resets.
