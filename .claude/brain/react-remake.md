# Standing note: React remake

**Status: intent recorded, not started, no scope decided.** This is a note
to preserve the trainer's stated direction across sessions — not a plan, not
scheduled work. Don't start building a React app because this file exists;
raise it with the trainer first and confirm scope.

## What was said

2026-08-23, the trainer, after using the app through this session's work:

> "quiero que hagas una nota de que queremos hacer un remake de la app con
> react esta app esta horrible y no se ve nada bueno"

Translation: the trainer wants a full remake of the app in React. The stated
reason is purely visual/UX — "esta horrible y no se ve nada bueno" (it looks
horrible, nothing looks good) — not a functional or architectural complaint.
No specific screens, no specific complaints beyond general appearance were
named.

## Context that should inform this when it's picked up

- **This was already diagnosed, before this note existed.**
  `docs/implementation-plan.md`'s **Milestone 0** ("UI/UX foundation and flow
  redesign") is a fully-written, unstarted plan that names almost exactly
  this complaint — no deliberate theme, inconsistent density, weak
  orientation, uneven visual language, desktop-first layout — with a
  concrete page-by-page redesign plan for the *existing* Streamlit app. It
  was written before the trainer used the app enough to say "esta horrible,"
  which is itself informative: the diagnosis matches the trainer's own
  reaction, independently.
- **Earlier guidance given in this same session** (before this note was
  requested): don't rewrite in React for phase-2 work specifically — the
  backend (Supabase + RLS + repository layer) is almost entirely reusable
  work regardless of frontend choice, and Milestone 0 is a much smaller,
  faster path to "doesn't look bad" than a full rewrite. If a rewrite
  happens, take the trainee-facing surface first (highest traffic, smallest
  surface area) and keep Supabase/RLS as the backend rather than building a
  new API layer — RLS already does the authorization work a REST/GraphQL
  layer would otherwise have to reimplement.
- **This is a real, actively-used app** (see system-overview.md — "Dev" is
  functionally production, with real trainee progress). A rewrite is not a
  clean-slate greenfield decision; it has to account for migrating real,
  in-progress case data and not disrupting trainees mid-training.

## What a future session should do with this

When the trainer wants to move on this:

1. **Ask which they actually want**: the Milestone 0 redesign (same
   Streamlit app, systematic visual/UX pass, days not weeks, already fully
   scoped in `docs/implementation-plan.md`) vs. a genuine React rewrite
   (much larger, needs its own architecture decisions — API layer or direct
   Supabase JS client, auth flow, deployment, and a migration plan for real
   user data). Don't assume "React remake" rules out the cheaper option
   without confirming — the trainer's complaint (visual polish) is exactly
   what Milestone 0 targets, and "React" may be a proxy for "make it look
   professional" rather than a technology requirement per se. But this is
   the trainer's call, not something to talk them out of — surface the
   option, then follow their decision.
2. If it's a real rewrite: scope it explicitly (trainee-only first? both
   roles? which pages?), decide the backend integration approach up front,
   and write a migration/coexistence plan before writing any React code —
   don't start component-by-component with the DB story undecided.
3. Either way, `.claude/brain/data-model.md` and `phase-1.md`/`phase-2.md`
   describe the business rules and lifecycle a rewrite has to preserve
   exactly (especially the case-status ownership model in gotchas.md #1/#2 —
   a rewrite is exactly the kind of project that would silently reintroduce
   those bugs if it re-derives the rules from scratch instead of reading
   this brain first).
