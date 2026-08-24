# Project brain — index

This folder is the durable knowledge base for `vip_trainer_app`: architecture,
data model, domain rules, and the non-obvious traps found while building it.
`CLAUDE.md` at the repo root is the short, always-loaded summary; this folder
is where the depth lives. Read the specific file you need — you don't have to
read all of them.

| File | Read this for |
| --- | --- |
| [system-overview.md](system-overview.md) | What the app is, who uses it, the tech stack, how it's deployed (Dev/Prod), the page/route map |
| [application-layers.md](application-layers.md) | Module-by-module map of `src/ct_training_tracker/` — what lives where and why |
| [data-model.md](data-model.md) | Every table, enum, and relationship; the case status lifecycle; who owns which status (this one caused a real bug — read it before touching case status) |
| [phase-1.md](phase-1.md) | The 32-case catalog training: schedule, file requirements, review cycle, corrections |
| [phase-2.md](phase-2.md) | The 30-case simulated live-case phase: how it starts, the release schedule, and the corrected assignment model |
| [gotchas.md](gotchas.md) | Concrete traps found empirically — each one caused a real bug in this session. Read before making schema or status-transition changes |
| [react-remake.md](react-remake.md) | Standing note: the trainer wants to eventually replace the UI with React. Status, reasoning, what should carry over |

## How to use this as a future session

- Before changing anything about case status, assignment, or phase 2, read
  **data-model.md** and **gotchas.md** first — both.
- Before touching a specific view file, skim **application-layers.md** to see
  what already calls it and what it's not supposed to do (views never query
  the database directly — see that file).
- Migration history and the reasoning behind each phase-2 migration lives in
  [`docs/phase-2-implementation.md`](../../docs/phase-2-implementation.md) —
  more verbose and dated than this folder; this folder is the distilled,
  living version. When they conflict, this folder wins (it's kept current);
  `docs/phase-2-implementation.md` is the point-in-time implementation log.
- Domain vocabulary (fase 1, fase 2, "ciclo", live cases) is explained the
  way the trainer actually uses it, not just the schema names — see
  phase-1.md / phase-2.md.

## Keeping this current

This folder is only useful if it stays accurate. When a session learns
something non-obvious the hard way (a bug, a wrong assumption, a schema
surprise), add it to **gotchas.md** rather than letting it live only in a
conversation transcript. When the schema or a workflow changes, update the
relevant file in the same PR/session — don't let this drift from the code.
