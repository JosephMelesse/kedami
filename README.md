# Kedami architecture

Kedami is a desktop app that takes course material for a week, module, or exam and turns it into one interactive lesson. The lesson is sequenced so that completing it means the associated problem set is done. Lesson content is grounded in the material provided. The student's own Claude Code session builds each lesson from Kedami's Terminal panel; Kedami itself makes no model calls and holds no API key.

## Scope

**In scope for MVP**
- Single user, running from source on one machine
- Math and physics
- General: any other course, such as computer architecture or chemistry, with no subject-specific rules
- Lessons built by the student's Claude Code session in the Terminal panel, on their own Claude plan (see `architecture/agent-mode.md`)
- Computer science lessons (DSA with LeetCode, and SQL) made earlier by the old API pipeline still open and work; new ones can't be created
- Local storage; Kedami itself sends nothing over the network. Programs the student runs in the Terminal panel, Claude Code included, are their own
- Dark theme

**Out of scope for MVP**
- Running code outside the sandboxed runner, languages other than Python, and any LeetCode integration beyond opening a problem in the browser
- Accounts, sync, packaging, distribution
- Creating computer science lessons, reruns, and agents other than Claude Code

See `roadmap.md` for the backlog.

## Documents

| File | Covers |
|---|---|
| `architecture/system.md` | Processes, launch, models, security |
| `architecture/agent-mode.md` | Building lessons with Claude Code: uploading, the stages, the Terminal panel, the plugin, the MCP server, agent routes |
| `architecture/lesson-format.md` | Lesson structure, blocks, answers, hints, simulations |
| `architecture/completion-and-verification.md` | Part states, mark done, answer checking, verification |
| `architecture/code-problems.md` | DSA lessons made earlier: LeetCode tests, the code editor, the sandboxed runner, test flags |
| `architecture/sql-lessons.md` | SQL lessons made earlier: the exercise bank, course databases, query answers and checking, running SQL safely |
| `architecture/ui.md` | Design tokens, UI rules, screens, Pomodoro timer, music player, 2048 |
| `architecture/storage-and-api.md` | Files on disk, database tables, server API |
| `architecture/roadmap.md` | Build order and backlog |

## License

Copyright (c) 2026 Joseph Melesse. All rights reserved.
