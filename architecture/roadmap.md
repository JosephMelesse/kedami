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
24. Agent routes: the `builder` column, the draft lesson, and every `/agent/` route, tested without Claude Code
25. MCP server and the plugin the server writes: build one lesson with `claude --plugin-dir` against a server started by hand
26. Builder choice on the Upload screen, the waiting state and Cancel on the Generating screen, and `/capabilities`
27. Terminal panel: its own view, node-pty in main, Start Claude Code and Open a shell
28. Remove the API: Claude Code builds every lesson and writes every solution and simulation, through `/kedami:solution` and `/kedami:simulation`. Reruns, the usage log, the run log, and creating computer science lessons go
29. Computer science lessons made earlier are no longer opened. The code editor, runner, SQL checker, and their imports go

Steps 1 and 2 prove the lesson format is good to study from. Step 3 proves the sequencing. Each later step is independent of the ones after it. Steps 24 to 28 move lesson building to Claude Code (see `agent-mode.md`); step 25 proves it before any UI exists. Step 29 stops opening computer science lessons.

## Backlog

- **Practice problem generation:** a Claude Code command with number of questions, difficulty, and type mix (free response, multiple choice, selection), for lessons with no problem set or when more problems are requested. This also removes the requirement that every lesson has a problem set.
- **Similar-problem generation:** replace or supplement problems whose stored answer is unverified.
- **Short text answers:** an answer kind for a term or name, matched against a list of accepted answers ignoring case and spacing, in place of a self check for questions such as "Which flag is set on unsigned overflow?"
- **Light theme:** same token names, same accent, feedback, and syntax hues, darkened to reach at least 4.5:1 contrast on white.
- **Packaging and distribution:** bundling the Python server.
- **Computer science lessons through Claude Code:** DSA with the LeetCode lookup, and SQL with recommendations and course databases, as tools.
- **Changing a ready lesson from the Terminal panel:** asking Claude Code for a change to a section, in place of reruns, with progress carried over.
- **Codex**, and **Claude Code sessions started outside the Terminal panel**.
