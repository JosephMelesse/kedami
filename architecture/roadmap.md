# Roadmap

## Build order

1. Design tokens, lesson format, and renderer, using a hand-written lesson with a multi-part problem
2. Answer checking, hints, part states, mark done, and saved progress
3. Stages 2 to 4 from pasted text
4. Verification pass
5. Ingestion with page routing, reruns, and progress carry-over
6. Simulations
7. Pomodoro timer

Steps 1 and 2 prove the lesson format is good to study from. Step 3 proves the sequencing. Each later step is independent of the ones after it.

## Backlog

- **Jev (TypeSafe AI):** use it for page routing and yes/no checks once access is available, in place of the small Claude model.
- **Practice problem generation:** a popup with number of questions, difficulty, and type mix (free response, multiple choice, selection), for lessons with no problem set or when more problems are requested. This also removes the requirement that every lesson has a problem set.
- **Similar-problem generation:** replace or supplement problems whose stored answer is unverified.
- **Per-page re-transcribe:** a page review screen with a control to re-transcribe a single page.
- **Light theme:** same token names, same accent and feedback hues, darkened to reach at least 4.5:1 contrast on white.
- **Checked code for CS lessons:** run solutions to LeetCode problems instead of marking them done, either locally (a sandboxed Python runner with a test harness for LeetCode's types, design problems, and special judges) or through LeetCode's Run and Submit. Computer science lessons currently ask the student to solve each problem on LeetCode and mark it done.
- **Packaging and distribution:** bundling the Python server, plus key handling for other users.
