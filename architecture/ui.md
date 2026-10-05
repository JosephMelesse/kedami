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
}
```

Dark is the only theme in the MVP. All colors come from these tokens so a light theme can be added later.

## Rules

- **Accent:** only for the primary action, links, and progress indicators, including the music player's track name while it plays. Everything else stays neutral.
- **Depth:** three surface levels and a 1px border do all the layering. No shadows or gradients.
- **Type:** Inter in regular and medium weights. Body text is 16px with a line height of 1.6.
- **Shape and spacing:** 12px radius on cards, 10px on controls; spacing in multiples of 8px.
- **Feedback:** color the border and a short label, never the whole card. See part states in `completion-and-verification.md`.
- **Motion:** fades of 150 to 200ms at most.

## Consistency

- Inter, KaTeX, and JetBrains Mono (for code, with ligatures off so code shows as typed) fonts are bundled with the app.
- The music player's ▶ and ⏸ come from `app/src/renderer/src/assets/media-symbols.woff2`, a two-glyph subset of Noto Sans Symbols2 (SIL OFL, license alongside it), so both symbols match in size.
- Python code blocks are highlighted with neutral tokens only: keywords in medium weight, strings and comments in `--text-muted` (comments in italic), on `--surface-raised`.
- Plots, diagrams, and simulations take their colors from the tokens.
- The app icon is ፩ (U+1369, Ethiopic digit one) in `--accent` on a `--bg` rounded square, rendered from Noto Sans Ethiopic Medium to `app/resources/icon.png`. The same glyph, as an inline SVG outline in `--accent`, sits before "Kedami" in the app header.

## Screens

| Screen | Contents |
|---|---|
| Library | The start screen. Folder tiles first, then the lessons in no folder, oldest first, with status and problem progress, then a New lesson tile that opens Upload. A New folder button creates a folder. Folders are one level deep; opening one shows its lessons, a Rename button, a Delete folder button (its lessons move back home), and a New lesson tile that creates the lesson in that folder. Each lesson tile has an options menu to rename it, move it to a folder or home, or delete it after a confirmation; a generating lesson can't be deleted, and a renamed lesson keeps its name through reruns |
| Upload | File drop, role tag and force-transcription toggle per file |
| Generating | Current pipeline stage; a failed lesson shows the reason and a Rerun button |
| Lesson | Sections and blocks in order, with a progress indicator in the accent color. A Rerun button opens a dialog with the start stage and force-transcription toggles; a failed rerun shows its reason above the lesson. Opening a lesson returns to the block last read; see Reading position |

The app header is visible on every screen and holds the music player and the Pomodoro timer.

## Reading position

Kedami remembers where the student was reading in each lesson and reopens the lesson there. There is no button.

- The block being read is the topmost block still on screen: the first whose bottom edge is below the app header.
- It is saved when scrolling has stopped for one second and when the student leaves the lesson, only if it changed.
- On open, the lesson jumps to that block with no animation, its top just below the app header.
- Position is kept per block, not per pixel, so it holds when content above it changes height. Returning to a long block lands at its top.
- A lesson with no saved position, or whose saved block is gone after a rerun, opens at the top.

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
- **Rest screen:** during rest, running or paused, everything below the app header is replaced by a 404 page: a large "404" and the caption "You can go back to studying in 4:59", counting down with the timer. The screen underneath keeps its state and scroll position and returns when rest ends or the timer is stopped. The header stays usable, so pausing then Stop ends a break early. Rest pauses the music, and the play button stays disabled until study starts again; the music does not resume on its own.
- Durations are whole minutes from 1 to 180, editable only while the timer is reset, so a running phase never changes length.
- If the window sleeps through several phase ends, the timer lands in the right phase and the alarm plays once.
- The window does not throttle background timers, so the alarm is on time when the app is hidden.
- The alarm is `app/src/renderer/src/assets/alarm.wav`, a short ascending chime synthesized for this project.
- In a window 720px wide or less, the reset timer collapses to its study time. Clicking it opens the inputs and Start in a panel below the header; Escape or a click outside closes it. A running or paused timer is small enough not to collapse.

## Music player

A minimal player for audio files kept in the app data folder. It runs in the renderer, with main handling file access. There is no server involvement.

- **Placement:** in the middle of the app header, with the Pomodoro timer on the right.
- **Controls:** a dropdown of tracks with Add music as the last entry in its list, and a play/pause button showing ▶ (U+25B6) or ⏸ (U+23F8).
- **Adding:** Add music opens a file picker, and main copies the chosen files into `music/` in the app data folder. The first added file becomes the selected track; canceling keeps the current one. A name already taken gets a numbered suffix, as in `song (2).mp3`. The dropdown lists the files in `music/` by name; to remove a track, delete its file.
- **Formats:** MP3, M4A, FLAC, WAV, and OGG.
- **Playback:** the selected track repeats until paused or another track is picked. While it plays, its name is in `--accent`; paused, it is muted. Picking a track while playing switches to it and keeps playing. A track that fails to play stops the player.
- **File access:** main serves the files to the renderer through a custom protocol that only resolves plain file names inside `music/`, including through symlinks.
- **Alarm:** the Pomodoro alarm plays over the music.
- **Persistence:** the copied files stay in `music/`. The selected track and playback position do not survive an app restart.
- **Not included:** volume, next and previous, shuffle, playlists, artwork, metadata tags, and search.
