# Phase 2 — simulated live cases

Status: shipped 2026-08-23, in real use by real trainees on Dev (AARON FONG,
Max Pentecost have both started phase 2 as of that date). The full,
blow-by-blow implementation and bug history lives in
[`docs/phase-2-implementation.md`](../../docs/phase-2-implementation.md) —
this file is the distilled, corrected mental model to actually build against.

## What it simulates, and why

In production, a trainee who finishes phase 1 moves on to real production
cases: they work a real case, send it to the trainer, and get corrections
back. These trainees don't get production access, so phase 2 **simulates**
that with 30 fixed cases and a curated catalog — same review mechanics as
phase 1, different case source.

"Cycle" in this codebase always means **the review cycle**
(`submitted → in_review → corrections_sent → awaiting_resubmission →
approved`) — not batching, not one-case-at-a-time. A trainee can have several
phase-2 cases open at once; there is no sequential gate between cases.

## What's automatic, and what is very much not

This distinction is the single thing to get right — getting it wrong is what
produced two real, user-facing bugs on launch day (full story in
gotchas.md):

| Automatic | Manual — the trainer does this |
| --- | --- |
| Phase 2 **starting** (creating the 30 cases) once all 32 phase-1 cases are `approved` | **Assigning** each phase-2 case to the trainee — identical to phase 1's "Assign case" button, one case at a time |
| The 5-per-working-day **pacing plan** (`released_on`, suggested `due_date`) | Deciding when to actually click Assign — the plan is guidance, not a gate |

Concretely: `private.start_phase_2()` creates all 30 cases at once, all
`status = 'not_started'` (the default — same as phase 1's
`create_trainee_cases()`), all sitting in the trainer's Cases → Inbox →
"Live cases" tab as "needs assignment." Nothing about a case becomes visible
to the trainee until the trainer explicitly assigns it, same mechanism as
phase 1, same `_assign_case()` code path, no phase-2-specific shortcut.
**Do not reintroduce an auto-assign path** — it was built, shipped, and
reverted the same day (`20260823170000` → `20260823180000` in
`docs/phase-2-implementation.md`).

## How it starts

Trigger `on_case_approved_start_phase_2` on `cases`, fires
`after update of status ... when (new.status = 'approved' and old.status is
distinct from new.status)` → `private.maybe_start_phase_2()` → counts the
trainee's open (non-approved) phase-1 cases; if zero, calls
`private.start_phase_2(trainee_id, current_date)`.

**This only fires on a fresh transition into `approved`.** A trainee whose
32nd case was approved *before* this trigger existed will never trip it
retroactively — that's exactly what happened to two real trainees on
migration day, fixed with a one-time backfill
(`20260823160000_phase_2_backfill_completed_trainees.sql`) that runs the
trigger's own qualifying check once against existing data. If phase 2 is
ever ported to Prod (or any environment where trainees may have finished
phase 1 before the phase-2 migrations land), **run that backfill migration
too** — it's idempotent and a no-op wherever the trigger already caught
everyone.

`start_phase_2()` itself is idempotent (`update trainees set
phase_2_started_on = anchor where phase_2_started_on is null`, then `return`
if that update matched nothing) — calling it twice for the same trainee is
always safe.

## The release schedule

5 cases per working day, 6 days, computed with `private.training_date()`
from `trainees.phase_2_started_on` as the anchor (not `start_date` — a
different anchor than phase 1 uses for the same `training_day` column
concept). A case's `due_date`/`schedule_due_date` is the working day *after*
its `released_on`. These are **suggested pacing shown to the trainer when
they assign a case** (the same role `schedule_due_date` already plays in
phase 1's assign form, overridable there) — not a mechanism that makes a case
visible on its own. See data-model.md's ownership model for why.

## The catalog

30 cases, `phase_no = 2`, `set_no` always `1` (no Set 1/2 split in phase 2 —
`catalog_label` is `L01`–`L30` instead), each with:

- `order_number` — the training-order VIP number the trainee opens (real
  numbers supplied by the trainer, `12-26-07-*` range).
- `source_order_number` — the real production case it mirrors
  (`12-26-05/06-*` range). **Trainer reference only — never surface this to
  a trainee.** `repository.list_cases()`/`get_case()` gate it behind an
  explicit `include_source=True` param, off by default, precisely so a
  trainee-facing call site can't leak it by accident.
- `journey_category` — reused from phase 1's column, but only two values
  here: `Success` (25 cases) or `Manual` (5 cases: L06, L12, L18, L24, L30 —
  every sixth one).
- `instruction` — a mandatory per-case note, non-null on exactly 8 cases: 5
  "Reject and plan manually for practice" (the Manual ones) + 3 "Plan only"
  (L16, L22, L23). Rendered as a `st.warning` (not the optional `notes`
  `st.info`) in `components/ui.py:render_case_header` — a warning, not a
  suggestion, because the trainee must not miss it.

## Preloaded case material

The trainer explicitly does **not** need to preload anything right now — the
trainees will supply their own source material/links later, on their own
schedule. Do not build or ask for a `case_resources` pipeline for phase-2
source material unless asked again. (An earlier plan for this — matching
`resource_rules.py` on `phase_no` — is on hold, not scheduled.)

## UI surface

- Trainer: Cases → Inbox gets a **Phase 1 / Live cases** segmented control
  (`views/trainer.py:_render_cases_inbox`), shown only when the selected
  trainee has any phase-2 rows. `views/case_board.py:select_case_from_list`
  takes `phase_no` and branches: phase 1 keeps its Set 1/2 toggle, phase 2 is
  a flat list of up to 30 with no Set toggle (phase-2 rows all carry
  `set_no = 1`, so mixing phases in the Set toggle would silently merge
  unrelated cases — see gotchas.md).
- Kanban board (the trainer's default landing view) already pools every case
  regardless of phase — no phase filter needed there, only a caption fix
  (`Live case` instead of a meaningless `Set 1`).
- Trainee: no date-based visibility gate — a `not_started` phase-2 case is
  already invisible via the ownership model, so the dashboard doesn't need
  (and doesn't have) a separate release-date check. When nothing is
  actionable, `views/trainee.py:_render_all_caught_up()` shows a "🎉
  Congratulations — you finished phase 1 / your trainer will start assigning
  live cases soon" card — deliberately without naming a date, since
  assignment timing is the trainer's call, not a promise the schedule can
  make on their behalf.
- Progress journey visual: phase-1 only (`views/trainee.py` explicitly
  filters to `phase_no == 1` before calling it). **No phase-2 equivalent
  visual exists yet** — a flat 30-case strip is the natural shape, not built.

## Open / deferred work

- 30 preloaded OneDrive source links — deferred, trainees supply their own
  (see above).
- A phase-2 equivalent of the progress-journey visual.
- Applying all of this to Prod, once Prod has real trainees. Every migration
  listed here (`20260823140000` through `20260823190000`) needs to run
  there in order; the pre-flight constraint-name check in
  `docs/phase-2-implementation.md` §2 matters more on a fresh environment
  than it did on Dev.
