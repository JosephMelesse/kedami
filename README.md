# Kedami architecture

Kedami is a desktop app that takes course material for a week, module, or exam and produces one interactive lesson. The lesson is sequenced so that completing it means the associated problem set is done. Lesson content is grounded in the material provided. The one outside source is LeetCodeDataset, imported by hand and used only for LeetCode problems' text and tests, never for lesson content.

## Scope

**In scope for MVP**
- Single user, running from source on one machine
- Math and physics
- Computer science, in domains that decide how a lesson is built. Data structures and algorithms: lessons with comprehension checks, where the student picks LeetCode problems by number or name, and each is solved in Kedami in Python and checked against tests imported from LeetCodeDataset, or solved on LeetCode and marked done if the dataset lacks it. SQL is the next domain on the roadmap
- General: any other course, such as computer architecture or chemistry, through the math and physics pipeline with no subject-specific rules
- Local storage; outbound traffic goes only to the Anthropic API
- Dark theme

**Out of scope for MVP**
- Running code outside the sandboxed runner, languages other than Python, and any LeetCode integration beyond opening a problem in the browser
- Accounts, sync, packaging, distribution

See `roadmap.md` for the backlog.

## Documents

| File | Covers |
|---|---|
| `architecture/system.md` | Processes, launch, model roles, usage log, run log, security |
| `architecture/pipeline.md` | Ingestion through lesson generation, reruns |
| `architecture/lesson-format.md` | Lesson structure, blocks, answers, hints, simulations |
| `architecture/completion-and-verification.md` | Part states, mark done, answer checking, verification |
| `architecture/code-problems.md` | LeetCode tests, the code editor, the sandboxed runner, test flags |
| `architecture/ui.md` | Design tokens, UI rules, screens, Pomodoro timer, music player, 2048 |
| `architecture/storage-and-api.md` | Files on disk, database tables, server API |
| `architecture/roadmap.md` | Build order and backlog |

## License

Copyright (c) 2026 Joseph Melesse. All rights reserved.
