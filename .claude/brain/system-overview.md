# System overview

## What this is

A Streamlit + Supabase tool for Arthrex APAC **CT planning initial training**.
A trainer takes a new hire through two phases of training cases: a fixed
32-case catalog (phase 1), then 30 simulated "live" cases (phase 2). For every
case, the trainee produces three deliverables (PDF 1, PDF 2, OV) as OneDrive
links; the trainer reviews, raises corrections, and approves. There are
exactly two roles — `trainer` and `trainee` — and RLS enforces that a trainee
only ever reads their own rows.

This is an internal tool for a small number of real users, not a public
product. Two Supabase projects exist:

| Role | Name | Ref | Status as of 2026-08-23 |
| --- | --- | --- | --- |
| **Dev** | VIP Trainer | `pqwudxopjfkflpzgmvqk` | `ACTIVE_HEALTHY` — this is where the real trainer and real trainees currently work, despite the "Dev" name |
| **Prod** | CT-Tracker-Prod | `lbieleiwxkbtiqtjrjgd` | `INACTIVE` (paused), empty schema, zero user data |

**Practically: Dev is production right now.** Don't assume "Dev" means
low-stakes or disposable — real trainees' real progress lives there. See
`docs/environments.md` for the full Dev/Prod mapping and how to point local
Streamlit at each.

## Tech stack

- **Streamlit** (multipage app via `st.navigation`/`st.Page`), Python 3.11+ —
  currently the live client for real trainees on Dev.
- **React remake** in `web/` (Vite + TypeScript + Tailwind + Supabase JS) —
  in progress on `feature/react-remake`; coexists until cutover. See
  `react-remake.md`.
- **Supabase**: Postgres + Auth + Storage + RLS + Postgres functions (RPCs)
  for anything that must be transactional or `security definer`.
- A **Supabase MCP server** is available in this environment — it can run
  SQL and apply migrations directly against Dev. See gotchas.md for the
  discipline required when using it (pre-flight checks, idempotency).

## Entry point and routing

`streamlit_app.py` → `src/ct_training_tracker/application.py:run()`. Auth
gate first (redirects to `app_pages/login.py` if no session), then loads the
`profiles` row for the signed-in user and branches navigation by role:

**Trainer pages** (`url_path`):
- `trainer` — Dashboard (`views/trainer.py:render_dashboard`)
- `trainer-cases` — Cases: Board + Inbox tabs (`views/trainer.py:render_cases`)
- `trainer-case` — Review workspace for one case (`render_trainer_case_workspace`)
- `trainer-trainees` — Add trainee (`render_trainees`)

**Trainee pages**:
- `trainee` — My cases / dashboard (`views/trainee.py:render_trainee_portal`)
- `trainee-case` — Case workspace (`render_trainee_case_workspace`)
- `trainee-questions` — Question inbox

Deep links use query params (`?trainee=<id>&case=<id>&view=inbox`) via
`routing.py` — this is how the kanban board and dashboard cards jump straight
to a specific case.

## What is NOT part of this product

- `app.py`, `templates/` — a legacy Flask peer-feedback app. Don't touch
  unless explicitly asked.
- `APAC INTEGRATION/` — an older, separate schedule dashboard.

Do not let either of these leak into architecture decisions for the current
product; they're unrelated codebases sharing this repo.

## The two Supabase-project split, and getting real work done

Local `streamlit run` reads `.streamlit/secrets.toml` (gitignored) for which
project it talks to. As of this session, secrets there point at Dev. A
Supabase MCP server (see above) can run migrations/queries against Dev
directly from a Claude Code session — this is how the phase-2 work in this
session was applied and verified, without ever needing local Postgres/Docker
(neither is installed on this machine).

## Who works on this, and how

The trainer (project owner) works partly in Cursor, partly by talking to
Claude Code sessions like this one. Two implications:

1. Durable knowledge needs to live in the **repo** (`CLAUDE.md`, this
   `.claude/brain/` folder, `docs/`) — not only in a Claude session's private
   memory — because Cursor sessions and future Claude Code sessions both need
   to see it.
2. The trainer answers questions in Spanish colloquially and briefly; don't
   assume a short answer settled every edge case — verify against real data
   before shipping a behavior change (see gotchas.md for what happens when
   that verification is skipped).
