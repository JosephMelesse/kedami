# UI

## Design tokens

```css
:root[data-theme="dark"] {
  --bg: #1A1B22;
  --surface: #22242C;
  --surface-raised: #2C2F38;
  --border: #343743;
  --text: #E4E6EB;
  --text-muted: #A0A4AE;
  --accent: #7AA2F7;
  --correct: #81C995;
  --retry: #F28B82;
  --in-progress: #E5C07B;
  --syntax-keyword: #C099FF;
  --syntax-string: #C3E88D;
  --syntax-number: #FF9E64;
  --syntax-name: #4FD6BE;
}
```

Dark is the only theme in the MVP. All colors come from these tokens so a light theme can be added later.

The syntax tokens color code and nothing else. Each reads at 5.9:1 or more on `--surface-raised`, and none shares a hue with the accent or the feedback colors, so code never looks like a link or a result.

## Rules

- **Accent:** only for the primary action, links, and progress indicators, including the music player's track name while it plays, and the 2048 tiles. Everything else stays neutral.
- **Active lessons:** a done problem's box in the Active card fills with `--correct`. It is the one progress indicator that isn't the accent; see Active lessons.
- **Depth:** three surface levels and a 1px border do all the layering. No shadows or gradients.
- **Type:** Inter in regular and medium weights. Body text is 16px with a line height of 1.6.
- **Shape and spacing:** 12px radius on cards, 10px on controls; spacing in multiples of 8px.
- **Feedback:** color the border and a short label, never the whole card. See part states in `completion-and-verification.md`.
- **Motion:** fades of 150 to 200ms at most.

## Consistency

- Inter, KaTeX, and JetBrains Mono (for code, with ligatures off so code shows as typed) fonts are bundled with the app.
- The music player's ▶ and ⏸ come from `app/src/renderer/src/assets/media-symbols.woff2`, a two-glyph subset of Noto Sans Symbols2 (SIL OFL, license alongside it), so both symbols match in size.
- Code in lesson blocks is highlighted in Python on `--surface-raised`: keywords in `--syntax-keyword`, strings in `--syntax-string`, numbers and constants (such as `True` and `None`) in `--syntax-number`, the names of functions and classes and built-ins in `--syntax-name`, comments in `--text-muted` italic, and everything else in `--text`.
- Plots, diagrams, and simulations take their colors from the tokens.
- The app icon is ፩ (U+1369, Ethiopic digit one) in `--accent` on a `--bg` rounded square, rendered from Noto Sans Ethiopic Medium to `app/resources/icon.png`. The same glyph, as an inline SVG outline in `--accent`, sits before "Kedami" in the app header.

## Screens

| Screen | Contents |
|---|---|
| Library | The start screen. The Active card first, on the home page only (see Active lessons), then folder tiles, then the lessons in no folder, oldest first, with status and problem progress, then a New lesson tile that opens Upload. A New folder button creates a folder, and a New placeholder button plans a lesson; see Placeholder lessons. Opening a folder shows its subfolders, then its lessons, then a New lesson tile that creates the lesson in that folder; see Folders. Each ready lesson tile has an Active checkbox in its top right corner, beside an options menu to rename it, move it to a folder or home, or delete it after a confirmation; a generating lesson can't be deleted, and a renamed lesson keeps its name through reruns |
| Upload | Opened from the New lesson tile, or from a placeholder, which it fills in and whose name it shows as its heading. A subject choice and a file drop, with a role tag and force-transcription toggle per file |
| Generating | Current pipeline stage, with a 2048 game below it while the lesson generates; a failed lesson shows the reason and a Rerun button |
| Lesson | Sections and blocks in order, with a progress indicator in the accent color. A Rerun button opens a dialog with the start stage and force-transcription toggles; a failed rerun shows its reason above the lesson. A Days button splits the lesson into days; see Finish lines. Opening a lesson returns to the block last read; see Reading position |

The app header is visible on every screen and holds the music player and the Pomodoro timer. Clicking Kedami in it opens the Library home page from any screen, including from inside a folder. Back on the Upload screen returns to the folder it was opened from.

## Folders

Folders organize lessons in the Library, and nest to any depth.

- **Names:** unique within the same parent, ignoring case, so two courses can each have a "Week 1". The check folds only ASCII letters, as it always has. A name is at most 80 characters.
- **Folder page:** a breadcrumb of the folders above it, starting from Lessons, which is the home page; the folder's name; and New folder, Rename, Move, and Delete folder buttons. Then its subfolders, by name, its lessons, oldest first, and the New lesson tile.
- **Folder tile:** the folder's name and how many lessons it holds, counting those in its subfolders at any depth.
- **Moving:** Move on a folder page, or on a lesson's options menu, opens a dialog listing Lessons and every folder by its full path, such as "Physics / Week 1". The current location can't be picked, and for a folder neither can the folder itself or anything inside it. The server refuses a move into itself or a descendant. A move into a parent that already has a folder of that name is refused with a message, as a rename is, since the student can rename and try again.
- **Deleting:** a confirmation names what moves and where. The folder's lessons and subfolders move up to its parent, and the student lands on the parent's page. A subfolder whose name is taken there gets the lowest free number, as in `Week 1 (2)`, as a music file does, and a notice afterward says what was renamed. The deleted folder's own name doesn't count as taken, so a "Week 1" inside a "Week 1" keeps its name. Folders are never merged.

## Folder notes

Each folder has one optional plain-text note, for the student's own reminders. The home page has no note.

- **Placement:** a text box at the top of the folder's page, above its subfolders and lessons, with a muted "Notes for this folder" placeholder. Line breaks are kept; nothing is rendered as Markdown.
- **Saving:** on the server, one second after typing stops and when the student leaves the page. There is no button. A failed save shows a short message by the box and keeps the text. The library's background refresh never replaces what is in the box.
- **Limit:** 20,000 characters. A note of only spaces and line breaks counts as empty.
- **Moving and deleting:** a note moves with its folder. Deleting a folder deletes its note, and the confirmation says so when the note isn't empty. A subfolder that moves up keeps its own note.
- **Privacy:** notes never go to the model or into any lesson material.

## Active lessons

The student marks the lessons they are working through as active, and the home page shows how many problems each one has left.

- **Marking:** a ready lesson's tile has an Active checkbox in its top right corner, left of the options button. Checking or unchecking it doesn't open the lesson. A generating lesson, or a new lesson that failed, has none.
- **Card:** at the top of the home page, one card spanning the width of the library, on `--bg` with a 1px `--border` and the usual card radius. It holds an "Active" heading over a row per active lesson from any folder, oldest first. With no active lesson there is no card. Folders don't show it.
- **Rows:** each row has the lesson title in 14px, then its boxes side by side, wrapping as needed, then "3 problems left" in `--text-muted`, or "All problems done" once none are, then its due date if it has one (see Deadlines). While the lesson reruns, "Generating" shows in place of the boxes. Clicking a row opens the lesson.
- **Boxes:** one fills for each done problem, from the left, in `--correct`. The rest are `--surface-raised` with a 1px `--border`. A problem is done as defined in `completion-and-verification.md`, so undoing a mark done empties a box again.
- **Persistence:** whether a lesson is active is saved on the server. New lessons start inactive, a rerun keeps it, and deleting the lesson removes it.

## Deadlines

A lesson can have one optional due date: a date with no time, in local time.

- **Setting:** Set due date, or Change due date, on a lesson's options menu opens a dialog with a date field, Save, Cancel, and, when it has one, Clear. Any lesson can have one, whatever its status. A date in the past is allowed and shows as overdue at once.
- **Overdue:** a lesson is overdue when its date has passed and it isn't done (see Completion in `completion-and-verification.md`). On the date itself it isn't overdue yet. A done lesson never shows as overdue, including while it reruns. A page left open past midnight updates the next time the library loads.
- **Dates:** shown as "Due Nov 3", with the year when it isn't the current year.
- **Tiles and rows:** lesson tiles and Active card rows show the due date. An overdue lesson adds a short "Overdue" label in `--retry`, and its tile has a `--retry` border. Rows have no border of their own, so only the label is colored.
- **Upcoming card:** on the home page, below the Active card and styled like it, an "Upcoming" heading over a row per unfinished lesson with a due date, from any folder, soonest first, so overdue lessons come first. Each row has the title, the folder's full path in `--text-muted` if it is in one, and the due date. Clicking a row opens the lesson. With none, there is no card. Folders don't show it.
- **Folder tile:** shows "Next due Nov 3", the soonest due date among unfinished lessons inside it, including its subfolders, with the Overdue label and border when that date has passed.
- **Persistence:** saved on the server. A rerun or a move keeps it, and deleting the lesson removes it.
- **Not included:** system notifications, recurring deadlines, and folder-level deadlines.

## Placeholder lessons

A placeholder is a lesson the student has planned but not generated, so a folder and its deadlines can be set up before the material is in hand.

- **Creating:** New placeholder, on the home page or inside a folder, opens a dialog with a Name, at most 120 characters, and an optional Due date. It makes no model calls and needs no files.
- **Pasting a list:** a Paste a list button in that dialog takes one placeholder per line, as `Name` or `Name | YYYY-MM-DD`, at most 100. Preview shows what would be created before anything is. One line that can't be read rejects the whole list, and every such line is named with its number and why: a second `|`, a `|` with no date after it, no name, a name that is too long, or a date that isn't real, such as `2026-02-30`. Blank lines are skipped, and two placeholders may share a name, as lessons may. Changing the text means previewing again.
- **In the library:** a tile marked Placeholder where a lesson shows its subject, with a "Not generated" label. It can be renamed, moved, deleted, and given a due date like any lesson. It has no Active checkbox and no problem progress, and it counts toward its folder's lessons. Opening it goes to Upload.
- **Filling in:** Upload works as it does for a new lesson, except that it fills in this placeholder rather than making a second lesson. The placeholder keeps its ID, name, folder, and due date, and goes straight to generating. An upload that is refused leaves it as it was.
- **Deadlines:** a placeholder is never done, so it shows in the Upcoming card, counts toward folder due dates, and shows as overdue once its date passes.
- **If generation fails:** it behaves like any failed new lesson, and keeps its name, folder, and due date.

## Reading position

Kedami remembers where the student was reading in each lesson and reopens the lesson there. There is no button.

- The block being read is the topmost block still on screen: the first whose bottom edge is below the app header.
- It is saved when scrolling has stopped for one second and when the student leaves the lesson, only if it changed.
- On open, the lesson jumps to that block with no animation, its top just below the app header.
- Position is kept per block, not per pixel, so it holds when content above it changes height. Returning to a long block lands at its top.
- A lesson with no saved position, or whose saved block is gone after a rerun, opens at the top.

## Finish lines

The student can split a lesson into days. Each day ends at a finish line, and the background of the music player's track name in the app header fills as a progress bar toward the next one.

- **Splitting:** the Days button opens a dialog with the number of days, a whole number from 1 to 30 and at most the number of blocks, and a Split button. The renderer cuts the lesson as currently laid out at the block boundaries nearest to equal heights, giving each day at least one block. Splitting again replaces the lines, and 1 day removes them.
- **Lines:** a finish line is kept as the ID of the block that starts the next day, so it stays between the same blocks when content changes height, such as a revealed solution. Heights matter only at the moment of splitting.
- **In the lesson:** each line shows between its blocks as a 1px `--border` rule with a muted "End of day 1" label.
- **Bar:** while a lesson is open, the track name's background fills from left to right, stopping short of the play button, with `--accent` mixed to 20% over `--bg`. The reading point is the bottom edge of the window. The fill is how far it has moved from the previous line, or the lesson start, to the next line, or the lesson end. A lesson with no lines fills toward its end. On other screens the player shows no fill.
- **Reaching a line:** when the reading point passes a line while scrolling down, "Done for today" replaces the track name in `--accent` for 4 seconds, then the bar starts the next day empty. The end of a split lesson counts as its last line. Opening a lesson past a line, or scrolling back up across one, shows no note.
- **Persistence:** lines are saved on the server. A rerun keeps the lines whose blocks still exist.

## Pomodoro timer

A simple study and rest timer. It runs entirely in the renderer and has no server involvement.

- **Inputs:** study minutes and rest minutes, whole numbers. Defaults are 25 and 5.
- **Reset:** shows the two inputs and Start.
- **Running:** shows only the current phase ("Study" or "Rest") and the remaining time as minutes and seconds. Clicking them pauses.
- **Paused:** shows the phase and the remaining time, muted, with Stop. Clicking them again resumes; Stop resets the timer to its inputs.
- **Cycle:** when a phase ends, the alarm plays and the other phase starts automatically. This repeats until paused or stopped.
- **Alarm:** a short, conventional alarm jingle from a bundled audio file, played once at the end of each phase.
- **Accuracy:** remaining time is computed from the phase's end timestamp, so it stays correct when the window is in the background.
- **Persistence:** the two durations are saved locally. A running timer does not survive an app restart.
- **Rest screen:** during rest, running or paused, everything below the app header is replaced by a 404 page: a large "404" and the caption "You can go back to studying in 4:59", counting down with the timer, centered horizontally at the top, with a 2048 game below them. The screen underneath keeps its state and scroll position and returns when rest ends or the timer is stopped. The header stays usable, so pausing then Stop ends a break early. Rest pauses the music, and the play button stays disabled until study starts again. When rest ends, music that was playing picks up where it paused, and music that was paused stays paused.
- Durations are whole minutes from 1 to 180, editable only while the timer is reset, so a running phase never changes length.
- If the window sleeps through several phase ends, the timer lands in the right phase and the alarm plays once.
- The window does not throttle background timers, so the alarm is on time when the app is hidden.
- The alarm is `app/src/renderer/src/assets/alarm.wav`, a short ascending chime synthesized for this project.
- In a window 720px wide or less, the reset timer collapses to its study time. Clicking it opens the inputs and Start in a panel below the header; Escape or a click outside closes it. A running or paused timer is small enough not to collapse.

## 2048

A simple 2048 game to pass the wait while a lesson generates and to fill a break. It runs entirely in the renderer and has no server involvement.

- **Placement:** centered below the stages on the Generating screen while the lesson generates, and below the caption on the rest screen.
- **Layout:** a card holding the 4 by 4 board, with the score and a New game button along its bottom.
- **Play:** the arrow keys slide every tile that way. Equal tiles that meet merge once per move, and the merged value is added to the score. A move that changes the board adds a 2, or a 4 one time in ten, in a random empty cell. When no move is left, "No moves left" shows beside the score; New game starts over.
- **Keys:** a game inside an inert screen, such as the Generating screen under the rest screen, ignores keys. So does every game while focus is in a text field or dropdown, so typing a duration or picking a track never moves tiles.
- **Tiles:** each tile is `--accent` mixed over `--surface-raised`, stronger as the value doubles, up to 2048. New tiles fade in; tiles do not slide.
- **Persistence:** both places share one game, kept for the app session. It does not survive an app restart.
- **Not included:** a best score, undo, a win screen, and touch or mouse controls.

## Music player

A minimal player for audio files kept in the app data folder. It runs in the renderer, with main handling file access. There is no server involvement.

- **Placement:** in the middle of the app header, with the Pomodoro timer on the right. In a lesson, the track name's background is the finish-line progress bar; see Finish lines.
- **Controls:** a dropdown of tracks with Add music as the last entry in its list, and a play/pause button showing ▶ (U+25B6) or ⏸ (U+23F8).
- **Adding:** Add music opens a file picker, and main copies the chosen files into `music/` in the app data folder. The first added file becomes the selected track; canceling keeps the current one. A name already taken gets a numbered suffix, as in `song (2).mp3`. The dropdown lists the files in `music/` by name; to remove a track, delete its file.
- **Formats:** MP3, M4A, FLAC, WAV, and OGG.
- **Playback:** the selected track repeats until paused or another track is picked. While it plays, its name is in `--accent`; paused, it is muted. Picking a track while playing switches to it and keeps playing. A track that fails to play stops the player.
- **File access:** main serves the files to the renderer through a custom protocol that only resolves plain file names inside `music/`, including through symlinks.
- **Alarm:** the Pomodoro alarm plays over the music.
- **Persistence:** the copied files stay in `music/`. The selected track and playback position do not survive an app restart.
- **Not included:** volume, next and previous, shuffle, playlists, artwork, metadata tags, and search.
