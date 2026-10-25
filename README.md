# Kedami architecture

Kedami is a desktop app that takes course material for a week, module, or exam and produces one interactive lesson. The lesson is sequenced so that completing it means the associated problem set is done. Lesson content is grounded in the material provided. The one outside source is LeetCodeDataset, imported by hand and used only for LeetCode problems' text and tests, never for lesson content.

## Scope

**In scope for MVP**
- Single user, running from source on one machine
- Math and physics
- Computer science, in domains that decide how a lesson is built. Data structures and algorithms: lessons with comprehension checks, where the student picks LeetCode problems by number or name, and each is solved in Kedami in Python and checked against tests imported from LeetCodeDataset, or solved on LeetCode and marked done if the dataset lacks it. SQL: one chapter per lesson, with explanations drawn from a bundled open book and problems recommended from the Spider bank, or from pgexercises for chapters Spider lacks; or uploaded from the course with its own database; each query solved in Kedami and checked in SQLite against a reference query
- General: any other course, such as computer architecture or chemistry, through the math and physics pipeline with no subject-specific rules
- Two ways to build a lesson: the server's pipeline, using an API key, or agent mode, where the student's own Claude Code session builds it from Kedami's Terminal panel (math, physics, and general lessons; see `architecture/agent-mode.md`)
- Local storage; Kedami's own outbound traffic goes only to the Anthropic API. Programs the student runs in the Terminal panel, Claude Code included, are their own
- Dark theme

**Out of scope for MVP**
- Running code outside the sandboxed runner, languages other than Python, and any LeetCode integration beyond opening a problem in the browser
- Accounts, sync, packaging, distribution
- Agent mode for computer science lessons, reruns of agent lessons, and agents other than Claude Code

See `roadmap.md` for the backlog.

## Documents

| File | Covers |
|---|---|
| `architecture/system.md` | Processes, launch, model roles, usage log, run log, security |
| `architecture/pipeline.md` | Ingestion through lesson generation, reruns |
| `architecture/agent-mode.md` | Building lessons with Claude Code: the Terminal panel, the plugin, the MCP server, agent routes |
| `architecture/lesson-format.md` | Lesson structure, blocks, answers, hints, simulations |
| `architecture/completion-and-verification.md` | Part states, mark done, answer checking, verification |
| `architecture/code-problems.md` | LeetCode tests, the code editor, the sandboxed runner, test flags |
| `architecture/sql-lessons.md` | SQL lessons: the exercise bank, course databases, query answers and checking, running SQL safely |
| `architecture/ui.md` | Design tokens, UI rules, screens, Pomodoro timer, music player, 2048 |
| `architecture/storage-and-api.md` | Files on disk, database tables, server API |
| `architecture/roadmap.md` | Build order and backlog |

## License

Copyright (c) 2026 Joseph Melesse. All rights reserved.
