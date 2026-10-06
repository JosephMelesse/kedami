# Kedami architecture

Kedami is a desktop app that takes course material for a week, module, or exam and produces one interactive lesson. The lesson is sequenced so that completing it means the associated problem set is done. Lesson content is grounded in the material provided.

## Scope

**In scope for MVP**
- Single user, running from source on one machine
- Math and physics
- Computer science (data structures and algorithms): lessons with comprehension checks, where each assigned LeetCode problem is solved on LeetCode and marked done in Kedami
- General: any other course, such as computer architecture or chemistry, through the math and physics pipeline with no subject-specific rules
- Local storage; outbound traffic goes only to the Anthropic API
- Dark theme

**Out of scope for MVP**
- Running or checking code in Kedami, and any LeetCode integration beyond opening a problem in the browser
- Accounts, sync, packaging, distribution

See `roadmap.md` for the backlog.

## Documents

| File | Covers |
|---|---|
| `architecture/system.md` | Processes, launch, model roles, security |
| `architecture/pipeline.md` | Ingestion through lesson generation, reruns |
| `architecture/lesson-format.md` | Lesson structure, blocks, answers, hints, simulations |
| `architecture/completion-and-verification.md` | Part states, mark done, answer checking, verification |
| `architecture/ui.md` | Design tokens, UI rules, screens, Pomodoro timer, music player |
| `architecture/storage-and-api.md` | Files on disk, database tables, server API |
| `architecture/roadmap.md` | Build order and backlog |

## License

Copyright (c) 2026 Joseph Melesse. All rights reserved.
