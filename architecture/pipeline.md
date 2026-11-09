# Pipeline

A lesson is built from its material, not written over it. The problem set and the reference are both cut up and placed by the server, word for word. The model decides how they fit together and writes only what connects them.

Each stage writes its output to disk, so any stage can be rerun alone.

| # | Stage | Input | Output |
|---|---|---|---|
| 1 | Ingest | Files, each tagged as problem set or reference | Normalized Markdown with LaTeX per page, the route each page took, cropped figures, and the reference as numbered passages |
| 2 | Extract | Normalized text and passages | Problem list with parts, the reference cut into units and skipped ranges, problem-to-unit map |
| 3 | Plan | Extracted structure | Ordered sections, each with a goal, units, target problems, and a simulation brief |
| 4 | Generate and verify | Plan plus units | Lesson JSON |
| 5 | Render and track | Lesson JSON | Interactive lesson, saved progress |

Stages 1 to 4 run as a background job on the server. The renderer polls lesson status and shows the current stage.

- Uploads are checked before anything is saved: at most 20 files, 30 MB each, and 100 pages in all. File names are made safe and unique in the materials folder.
- A stage whose reply is rejected (schema or rule violation) is retried up to 3 attempts, with the reason fed back. Temporary API failures (overload, rate limit, server errors, dropped connections, including an overload reported mid-stream) are retried after waits of 5, 15, and 45 seconds. Any other API error fails the lesson at once.
- A failed lesson records the reason, which the Generating screen shows.
- Generation runs inside the server process, so a lesson still generating when the app closes is marked failed on the next start.

## Filling in a placeholder

A placeholder (see Placeholder lessons in `ui.md`) becomes a generating lesson under its own ID.

- The upload is checked as for a new lesson, before anything is saved, so a refused upload leaves the placeholder as it was.
- The files are written to a staging folder, then one transaction takes the placeholder only if it is still one, records the materials, and moves the folder into place. A second upload or a delete that got there first refuses this one, and nothing of either is left behind.
- From there it is a new lesson's first run. A run that fails or is interrupted leaves a failed lesson with its files, which can be rerun from stage 1.

## Upload rules

- At least one file must be tagged as a problem set, and at least one as a reference. A lesson needs both.
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
- A PDF's text layer has its control characters removed and its line ends made plain. PDFium's mark for a hyphen at a line end becomes a hyphen.
- Pages are joined into one normalized document per role, each page marked with its file and page number. Blank pages are left out. A problem set or reference with no readable text fails the lesson.

## Stage 1: formatting the reference

A kept PDF page is its raw text layer: lines wrapped where the page wrapped them, bullets split across lines, running headers and page numbers mixed in, and code broken apart. Shown as it is, it reads badly, so it is formatted first. Problem sets aren't formatted, since extraction copies their text.

- The format model gets up to 10 consecutive kept pages in one call and returns each as Markdown, with a list of the lines it dropped.
- It may only add structure: join wrapped lines, and mark headings, lists, tables, and code. It may drop only running headers, footers, and page numbers. It may not reword, correct, summarize, or reorder.
- **The word check:** the server removes the dropped lines from the page, then compares the page's letters and digits, in order, with the reply's. A dropped line must match a whole line of the page. Spacing, punctuation, and Markdown syntax are ignored, so `out-\ngoing` and `outgoing` count as the same.
- A page that fails the check, that the reply leaves out, or whose call fails keeps its raw text. `pages.json` records which, and the lines dropped from each formatted page. Formatting never fails the lesson.
- A dropped line that appears more than once on a page can be any of them, so a page number that is also a table cell doesn't fail the check.
- Transcribed pages and text files are not formatted.

## Stage 1: figures

- **Finding them:** each page of a reference PDF is checked locally for raster images covering 2% to 95% of the page. Images that overlap on a page count as one figure.
- **Repeats:** an image found on 3 or more pages is a logo or background, and is left out.
- **Cropping:** the figure's region is rendered from the page with a small margin, so labels drawn over the image come with it, and saved as a PNG with the same size limit as a transcribed page. Its ID is `{file slug}-p{page}-{n}`.
- **Describing them:** the small model sees each crop, in one call per figure, and returns a one-line description and whether the figure is only decoration. Decoration is left out. A figure with no reply is kept, with a caption naming its file and page.
- Vector drawings, and figures on scanned pages or in image files, aren't cropped. See the backlog.
- The figures and descriptions are saved with the stage output (`figures/`, `figures.json`).

## Stage 1: passages

The server splits the normalized reference into numbered passages, saved as `passages.json`. They are the only way later stages refer to the reference.

| Kind | Contents | Shown in the lesson |
|---|---|---|
| `text` | Text between blank lines | Yes, word for word |
| `figure` | A figure's ID and description | Yes, as the cropped image |
| `note` | A `[Figure: ...]` line from a transcribed page | No. The model reads it, and can draw from it |

- A fenced code block, a `$$` math block, a table, or a whole list stays in one passage, even with blank lines inside.
- Each passage records its file and page. Page markers are not passages.
- A figure passage follows the text of its page, since a text layer doesn't say where on the page its text falls.
- A paragraph that runs across a page break becomes two passages.
- In model requests, the reference is the passages, each marked with its number, such as `[p12]`, under a line naming its file and page. A lesson from before passages shows its normalized reference instead, in the calls made on request.

## Stage 2: extraction

- Every problem in the problem set is captured with its source reference (for example, "PS3 #4") and its parts.
- A part that asks the student to pick from listed options, including True/False, has its options captured separately, as written and in order, and left out of the part's text. The lesson shows them once, as the answer's choices.
- The same call cuts the reference into units. A unit is a run of consecutive passages that teaches one idea, with an ID, a title, and a one-line summary. The model gives only the first and last passage numbers. The server cuts the text, so a unit can't differ from the reference.
- A unit stays within one file and holds at least one `text` passage. A skipped range may cross files.
- Every `text` and `figure` passage belongs to exactly one unit or one skipped range. A gap, an overlap, or a range outside the passages sends the reply back with the numbers, every problem in one reply. `note` passages can fall anywhere.
- A skipped range is material that doesn't teach: course logistics, a table of contents, a bibliography, or a repeated slide. Each has a reason, saved in `extraction.json`. Material no problem needs is not a reason to skip it.
- Each problem lists the IDs of the units a student needs to solve it.

## Stage 3: sequencing rules

- Every unit appears in exactly one section.
- Within one file, units keep the order of the file, and a plan that breaks this is sent back. Sections may alternate between files.
- A unit comes before any problem that needs it.
- Each problem appears in the section where its last unit is covered.
- Every problem appears exactly once.
- Every section has a one-line simulation brief.
- The model orders sections and assigns each unit to exactly one of them. The server then places each problem in the section of its last unit, so the rules hold by construction. A problem that needs no unit goes in the first section, and a section with no units and no problems is dropped.

## Stage 4: generation

- One model call per section. A failed or invalid section is retried alone.
- The model places each of the section's units with a `source` marker naming it, and places each of the section's problems. It gives the problems' answers by part label. The server inserts the unit and the problem and part text verbatim, so the model never restates either.
- Every unit of the section is placed exactly once, in the plan's order. Otherwise the section is sent back. The server expands a unit into blocks: each run of text passages becomes a `source` block, and each figure a `figure` block. A `note` isn't shown, so it doesn't end a run.
- Around them, the model writes only what the material doesn't supply: a short `explanation` that connects two units or fills a gap the problems need, worked examples, checkpoints, and plots.
- A section whose units hold no figure must have one `diagram`, and a section whose units hold one must have none. A diagram with a bad layout is retried with the section, then dropped, so a section can end with no figure, but a figure never fails a lesson.
- Every section has exactly one `simulation` block. Its code is still written when the student asks for it.
- A part with extracted options must get a `choice` or `multi_choice` answer with the same number of options, and the server stores the extracted options in place of the model's wording, so the choices read as in the problem set.
- Teaching block IDs are `{section_id}-block-{n}`, where `n` is the block's place in the model's reply, so a dropped diagram doesn't move the others. A unit that becomes more than one block numbers the rest `{section_id}-block-{n}-{k}`, from `k` = 2.
- Hint checks: the cheap check looks for the answer in the hint (a number within tolerance, the expression, or the correct option). Integer answers below 10 are left to the small model, since they appear in ordinary working. A hint the small model doesn't rule on counts as failing.
- Each diagram's text layout is checked as the section is assembled, and a bad one is retried with the section, then dropped. See Diagrams in `lesson-format.md`.
- Hints, simulations, and verification run after the section content exists.
- See `lesson-format.md` for the output and `completion-and-verification.md` for verification.

## Reruns

- A rerun starts from a chosen stage and repeats every stage after it.
- A bad page is fixed by turning on force transcription for its file and rerunning from stage 1.
- A lesson extracted before options were captured separately shows a problem's options twice, in its text and as choices. Rerunning from stage 2 fixes it.
- A lesson generated before dissection keeps showing as it was, and has no saved `figures.json`, so it can be rerun only from stage 1. One with no reference can't be rerun, since a rerun can't add a file.
- A rerun's figures replace the lesson's only when it succeeds, with the lesson JSON.
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
