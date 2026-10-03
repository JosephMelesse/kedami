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

- **Accent:** only for the primary action, links, and progress indicators. Everything else stays neutral.
- **Depth:** three surface levels and a 1px border do all the layering. No shadows or gradients.
- **Type:** Inter in regular and medium weights. Body text is 16px with a line height of 1.6.
- **Shape and spacing:** 12px radius on cards, 10px on controls; spacing in multiples of 8px.
- **Feedback:** color the border and a short label, never the whole card. See part states in `completion-and-verification.md`.
- **Motion:** fades of 150 to 200ms at most.

## Consistency

- Inter and KaTeX fonts are bundled with the app.
- Plots, diagrams, and simulations take their colors from the tokens.

## Screens

| Screen | Contents |
|---|---|
| Library | The start screen. Folder tiles first, then the lessons in no folder, oldest first, with status and problem progress, then a New lesson tile that opens Upload. A New folder button creates a folder. Folders are one level deep; opening one shows its lessons, a Delete folder button (its lessons move back home), and a New lesson tile that creates the lesson in that folder. Each lesson tile has an options menu to move it to a folder or home, or delete it after a confirmation; a generating lesson can't be deleted |
| Upload | File drop, role tag and force-transcription toggle per file |
| Generating | Current pipeline stage; a failed lesson shows the reason and a Rerun button |
| Lesson | Sections and blocks in order, with a progress indicator in the accent color. A Rerun button opens a dialog with the start stage and force-transcription toggles; a failed rerun shows its reason above the lesson |

The app header is visible on every screen and holds the Pomodoro timer.

## Pomodoro timer

A simple study and rest timer. It runs entirely in the renderer and has no server involvement.

- **Inputs:** study minutes and rest minutes, whole numbers. Defaults are 25 and 5.
- **Controls:** start, pause, reset.
- **Display:** the current phase ("Study" or "Rest") and the remaining time as minutes and seconds.
- **Cycle:** when a phase ends, the alarm plays and the other phase starts automatically. This repeats until paused or reset.
- **Alarm:** a short, conventional alarm jingle from a bundled audio file, played once at the end of each phase.
- **Accuracy:** remaining time is computed from the phase's end timestamp, so it stays correct when the window is in the background.
- **Persistence:** the two durations are saved locally. A running timer does not survive an app restart.
- Durations are whole minutes from 1 to 180, editable only while the timer is reset, so a running phase never changes length.
- If the window sleeps through several phase ends, the timer lands in the right phase and the alarm plays once.
- The window does not throttle background timers, so the alarm is on time when the app is hidden.
- The alarm is `app/src/renderer/src/assets/alarm.wav`, a short ascending chime synthesized for this project.
