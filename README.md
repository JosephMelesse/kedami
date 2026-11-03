# Kedami architecture

Kedami is a desktop app that takes course material for a week, module, or exam and produces one interactive lesson. The lesson is sequenced so that completing it means the associated problem set is done. It is built from the material itself: the problem set and the reference are both required, both appear word for word, and the model writes only what connects them.

## Scope

**In scope for MVP**
- Single user, running from source on one machine
- Math and physics
- General: any other course, such as computer science or chemistry, through the math and physics pipeline with no subject-specific rules
- Local storage; outbound traffic goes only to the Anthropic API
- A library of folders nested to any depth, each with an optional private note, lessons with optional due dates, and placeholders for lessons not yet generated
- Dark theme

**Out of scope for MVP**
- Running the student's code or queries, and any integration with sites such as LeetCode
- Accounts, sync, packaging, distribution
- System notifications, recurring deadlines, and folder-level deadlines

See `roadmap.md` for the backlog.

## Documents

| File | Covers |
|---|---|
| `architecture/system.md` | Processes, launch, model roles, usage log, run log, security |
| `architecture/pipeline.md` | Ingestion through lesson generation, reruns |
| `architecture/lesson-format.md` | Lesson structure, blocks, answers, hints, simulations |
| `architecture/completion-and-verification.md` | Part states, mark done, answer checking, verification |
| `architecture/ui.md` | Design tokens, UI rules, screens, Pomodoro timer, music player, 2048 |
| `architecture/storage-and-api.md` | Files on disk, database tables, server API |
| `architecture/roadmap.md` | Build order and backlog |

## License

MIT; see `LICENSE`. Copyright (c) 2026 Joseph Melesse.

Bundled fonts keep their own license, the SIL Open Font License: Inter and JetBrains Mono (through Fontsource), the two-glyph Noto Sans Symbols 2 subset (`app/src/renderer/src/assets/media-symbols-OFL.txt`), and the ፩ outline taken from Noto Sans Ethiopic for the app's mark.
