# Roadmap

## Build order

1. Design tokens, lesson format, and renderer, using a hand-written lesson with a multi-part problem
2. Answer checking, hints, part states, mark done, and saved progress
3. Stages 2 to 4 from pasted text
4. Verification pass
5. Ingestion with page routing, reruns, and progress carry-over
6. Simulations
7. Pomodoro timer
8. Music player
9. Step-by-step solutions on request
10. General subject
11. Reading position
12. Rest screen
13. Finish lines
14. 2048
15. Usage log
16. Run log
17. Active lessons
18. Code problems for computer science lessons
19. Computer science domains and the DSA problem picker
20. SQL lessons
21. SQL lessons by chapter: the bundled book, recommended problems, pgexercises links, and the course database slot
22. LeetCode test fixes for the NeetCode 150: dropped tests, comparisons that accept every answer LeetCode accepts, and lessons served the import's current tests
23. Diagram layout check: monospace diagram text, measured by the server, with clipped and overlapping text sent back to the model

Steps 1 and 2 prove the lesson format is good to study from. Step 3 proves the sequencing. Each later step is independent of the ones after it.

## Backlog

- **Jev (TypeSafe AI):** use it for page routing and yes/no checks once access is available, in place of the small Claude model.
- **Practice problem generation:** a popup with number of questions, difficulty, and type mix (free response, multiple choice, selection), for lessons with no problem set or when more problems are requested. This also removes the requirement that every lesson has a problem set.
- **Similar-problem generation:** replace or supplement problems whose stored answer is unverified.
- **Per-page re-transcribe:** a page review screen with a control to re-transcribe a single page.
- **Short text answers:** an answer kind for a term or name, matched against a list of accepted answers ignoring case and spacing, in place of a self check for questions such as "Which flag is set on unsigned overflow?"
- **Light theme:** same token names, same accent, feedback, and syntax hues, darkened to reach at least 4.5:1 contrast on white.
- **Workspace panes:** draggable dividers between the panes, and previous and next problem buttons.
- **More SQL:** solutions for query parts on request, showing a database's tables beside the lesson's explanations, flagging a bank exercise as broken, and Spider's three databases over 5 MB.
- **More code problems:** design problems (a class tested by a sequence of calls), problems that change their input in place, and fixes for problems outside the NeetCode 150, such as by checking every test against the limits in its description at import.
- **Packaging and distribution:** bundling the Python server, plus key handling for other users.
