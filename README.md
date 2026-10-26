# Kedami architecture

Kedami is a desktop app that takes course material for a week, module, or exam and turns it into one interactive lesson. The lesson is sequenced so that completing it means the associated problem set is done. Lesson content is grounded in the material provided. The student's own Claude Code builds each lesson, started from a button; Kedami itself makes no model calls and holds no API key.

## Scope

**In scope for MVP**
- Single user, running from source on one machine
- Math and physics
- General: any other course, such as computer architecture or chemistry, with no subject-specific rules
- Lessons built by the student's own Claude Code, run by Kedami in the background on their Claude plan (see `architecture/agent-mode.md`)
- Local storage; Kedami itself sends nothing over the network. Programs the student runs in the Terminal panel, Claude Code included, are their own
- Dark theme

**Out of scope for MVP**
- Computer science lessons. Ones made earlier are not opened, and new ones can't be created
- Accounts, sync, packaging, distribution
- Reruns, and agents other than Claude Code

See `roadmap.md` for the backlog.

## Documents

| File | Covers |
|---|---|
| `architecture/system.md` | Processes, launch, models, security |
| `architecture/agent-mode.md` | Building lessons with Claude Code: uploading, the stages, background jobs, selecting a block, the Terminal panel, the plugin, the MCP server, agent routes |
| `architecture/lesson-format.md` | Lesson structure, blocks, answers, hints, simulations |
| `architecture/completion-and-verification.md` | Part states, mark done, answer checking, verification |
| `architecture/ui.md` | Design tokens, UI rules, screens, Pomodoro timer, music player, 2048 |
| `architecture/storage-and-api.md` | Files on disk, database tables, server API |
| `architecture/roadmap.md` | Build order and backlog |

## License

Copyright (c) 2026 Joseph Melesse. All rights reserved.
