# Data model

Schema lives entirely in `supabase/migrations/*.sql`, one file per change,
named `YYYYMMDDHHMMSS_description.sql`. **Never edit an applied migration —
add a new one.** RLS policies ship with the migration that adds the table.

## Core tables

| Table | Purpose |
| --- | --- |
| `profiles` | `role` (`trainer`\|`trainee`) + `full_name`, one row per `auth.users` row. New accounts default to `trainee`; promotion to `trainer` is a manual SQL step. |
| `trainees` | One row per person. `start_date` drives the phase-1 schedule. `current_phase` (`ct_disposition`\|`ct_planning`) is largely vestigial — see below. `phase_2_started_on` (nullable date) is the real phase-2 marker. `is_test` hides practice accounts from trainer views by default. |
| `case_schedule_template` | The catalog: one row per `(phase_no, set_no, case_no)` defining `training_day`, `catalog_label`, `order_number`, `source_order_number`, `journey_category`, `instruction`. `create_trainee_cases()` and `start_phase_2()` both `SELECT` from this table to generate a trainee's actual `cases` rows. Edit this table (not `cases`) to change the catalog for future trainees. |
| `cases` | One row per trainee per case. See "Case lifecycle" below — this is the table everything else hangs off. |
| `file_requirements` | 3 per case (`pdf_primary`, `pdf_secondary`, `ov`), created by trigger `on_case_created` the instant a `cases` row is inserted. |
| `homework_assignments` | The assignment record: title, instructions, `schedule_due_date` vs overridable `due_date`, `status`. **This table, not `cases.status`, is the source of truth for "has this case been assigned."** See "The ownership model" below — this is the single most important thing to understand before touching case status. |
| `case_resources` | Trainer-curated or system-suggested links/files/notes attached to a case (`created_by`: `system`\|`trainer`). Trainee-readable, trainer-writable. |
| `revisions` / correction threads | The review record: 8 fixed sections (`revisions.py:REVIEW_SECTIONS`), `correction_threads` + `correction_events` that roll forward across revisions until resolved. |
| `questions` (name may vary by migration) | Trainee↔trainer per-case Q&A threads, open/answered/resolved lifecycle. |
| `tracking_events` | Append-only audit log (`trainee_id`, `case_id`, `actor_user_id`, `event_type`, `event_data` jsonb). Metrics/analytics derive from this, not from mutable `status`, specifically so history survives status changes. |
| `holidays` | Dates `private.training_date()` skips, alongside weekends. |

## Case lifecycle — the ownership model

**This is the part that caused two real bugs in one session (see
gotchas.md). Read it before changing any case-status logic.**

`cases.status` (enum `case_status`):
`not_started → assigned → submitted → in_review → corrections_sent → awaiting_resubmission → approved`
(`blocked` is an escape hatch from anywhere).

Every status is **owned** by exactly one role — who must act next — defined
in `metrics.py`:

```python
TRAINEE_OWNED_STATUSES = {"assigned", "submitted", "awaiting_resubmission"}
TRAINER_OWNED_STATUSES = {"not_started", "in_review", "corrections_sent"}
```

**`not_started` is trainer-owned.** A trainee never sees a `not_started` case
as "needs you" or as their next case — the dashboard shows "Waiting for
assignment," and it's excluded from every trainee-facing actionable filter.
It only becomes trainee-visible once the trainer explicitly assigns it.

**The only way a case leaves `not_started` is the trainer's "Assign case"
action** (`_assign_case()` in `views/trainer.py`, backed by the
`assign_homework()` repository call → `homework_assignments` insert +
`cases.status = 'assigned'`, in one transaction via the `assign_homework` RPC).
There is no other legitimate path to `assigned` — not a date, not a trigger,
not a bulk operation. This applies identically to phase 1 and phase 2; phase
2 does **not** get an automatic-assignment shortcut (see phase-2.md — this was
tried and explicitly reverted).

A **unique partial index** enforces one open assignment per case:

```sql
create unique index one_open_homework_per_case_idx
  on public.homework_assignments (case_id)
  where status not in ('completed', 'cancelled');
```

This is `homework_assignments`' way of saying "a case is either assigned or
it isn't" — and it is the thing that will loudly reject any attempt to
directly set `cases.status = 'assigned'` (or revert it) without going through
`assign_homework()`, if a homework row already/still exists. See gotchas.md
for exactly how this bit a real data-repair attempt.

## RLS shape

Every trainee-facing table has a trainee-scoped SELECT policy (via a
`private.trainee_owns_case(case_id)`-style helper) and a trainer-full-access
policy (`private.is_trainer()`). A trainee reads only their own rows; a
trainer reads all. `case_resources`, `correction_threads`, `questions`, etc.
all follow this same pattern — check the migration that introduced the table
for its exact policy names rather than assuming they're identical everywhere.

## `training_day` / date math

`private.training_date(start, day_offset)` walks forward from `start`,
skipping weekends and `holidays`, until it has advanced `day_offset` working
days, and returns that date. It always looks strictly *after* `start` (day
offset 1 = the next working day, not `start` itself). Both phase-1 case due
dates and phase-2 release/due dates are computed with this function — but
from **different anchors**: phase 1 uses `trainees.start_date`; phase 2 uses
`trainees.phase_2_started_on`. Same column meaning (`training_day` on the
template), two different anchor columns depending on `phase_no`.

## The `phase` vs `phase_no` split — don't confuse them

- `cases.phase` (enum `training_phase`: `ct_disposition` | `ct_planning`) —
  an older column, present since the very first migration. Every case, phase
  1 or phase 2, is created with `phase = 'ct_planning'`. `ct_disposition` is
  never actually used for a case row today (it's `trainees.current_phase`'s
  *default*, but nothing transitions a trainee out of it). Treat this column
  as legacy/mostly-decorative for now, not as the phase-2 discriminator.
- `cases.phase_no` (`smallint`, 1 or 2) — the real, current discriminator
  added for phase 2. **This is the column to filter/branch on.**

## Nullable columns to remember when writing new UI

`order_number` and `journey_category` are nullable on both `cases` and
`case_schedule_template` (they weren't originally, phase 2's migration
relaxed them). Any code reading them needs a fallback — `case_labels.py`
already provides one; don't duplicate the logic, call its functions.
`source_order_number` and `instruction` are phase-2-only concepts (always
null for phase-1 rows) — see phase-2.md for what they mean.
