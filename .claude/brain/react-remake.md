# React remake

**Status: in progress** (branch `feature/react-remake`). Full trainer + trainee
app in `web/`, Supabase JS client + RLS, coexisting with Streamlit until
cutover.

## Decisions locked (2026-08-25)

| Decision | Choice |
| --- | --- |
| Scope | Full app (trainer + trainee) |
| Backend | `@supabase/supabase-js` direct — no API layer |
| Coexistence | Streamlit stays live until React cutover |
| UI/UX | Milestone 0 principles ported to React design system |

## Layout

```
web/
  src/lib/api/          # TrainingRepository parity (Supabase calls)
  src/lib/domain/       # ownership, caseLabels, revisions (ported + tested)
  src/components/ui/    # PageHeader, CaseHeader, StatusBadge, …
  src/pages/trainer/    # dashboard, cases, case workspace, trainees
  src/pages/trainee/    # portal, case workspace, questions
```

## Local run

```bash
cd web
cp .env.example .env.local   # fill Dev publishable key
npm install && npm run dev
```

## What still needs hardening before cutover

- Screenshot paste/upload for correction threads — **done**: Jira-style
  `PasteCommentBox` (Ctrl+V / Cmd+V, upload, drag-drop) on raise + attach
  to existing open threads, same Storage layout as Streamlit.
- Bulk due-date editor UI (API helper exists).
- Analytics / section-stats screens (trainer).
- Deploy to Vercel + Auth redirect URLs + smoke with real Dev accounts —
  checklist in `web/CUTOVER.md`.
- Update `docs/environments.md` with the live React URL after first deploy.

## Original note (2026-08-23)

Trainer asked for a React remake because Streamlit "esta horrible y no se ve
nada bueno." Milestone 0 in `docs/implementation-plan.md` already diagnosed
the same UX issues for a Streamlit pass; the remake chose React instead.
Preserve brain rules in `gotchas.md` / `data-model.md` — especially ownership
and homework assignment — so the rewrite does not reintroduce those bugs.
