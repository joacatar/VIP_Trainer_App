# Gotchas

Concrete traps, every one of them found by actually hitting the bug — not
theoretical. Read this before touching case status, phase-2 data, or the
pandas-backed case list. Each entry: what looks reasonable, why it's wrong,
and how to avoid it.

## 1. `not_started` belongs to the trainer, not the trainee

**Looks reasonable:** "Once a case is created and its release date arrives,
the trainee should be able to see it."

**Is wrong:** `not_started` is in `TRAINER_OWNED_STATUSES`
(`metrics.py`). Every trainee-facing filter (`apply_case_filter(...,
"needs_you", role="trainee")`, `pick_next_case`, the dashboard's next-up
card) excludes it. A `not_started` case is invisible to the trainee no
matter what its dates say — visibility is **entirely** status-driven. The
only legitimate way out of `not_started` is the trainer's explicit "Assign
case" action.

**What actually happened:** phase-2's `start_phase_2()` originally created
cases already `'assigned'`, on the theory that release-day = visible. That
made every phase-2 case bypass the trainer's explicit control entirely — the
opposite of what was wanted ("solo deben ver los 5 que asigne yo"). Reverted
same day. See phase-2.md.

**Rule:** never invent a second, date-based visibility mechanism alongside
the status-based one. If a case needs to become trainee-visible, that means
assigning it (`assign_homework()`), full stop.

## 2. `homework_assignments` is the actual source of truth for "is this case assigned" — not `cases.status` alone

**Looks reasonable:** "I need to fix a batch of cases' assignment state,
I'll just `UPDATE cases SET status = ...` directly."

**Is wrong:** `homework_assignments` has a unique partial index —
`one_open_homework_per_case_idx` — enforcing at most one *open* (not
completed/cancelled) row per `case_id`. If a case already has a real,
trainer-created assignment row and you flip `cases.status` back to
`not_started` out from under it (without touching `homework_assignments`),
the case row and the assignment row disagree: the trainer's UI shows "needs
assignment" again (because it reads `status`), but clicking "Assign case"
tries to insert a second open row for that `case_id` → `duplicate key value
violates unique constraint "one_open_homework_per_case_idx"`.

**What actually happened:** a blanket revert
(`update cases set status = 'not_started' where phase_no = 2 and status =
'assigned'`) correctly undid a bug-introduced auto-assignment for 50 cases,
but also clobbered 10 cases the trainer had *legitimately* assigned through
the real UI in the meantime — same `status = 'assigned'` value, no way to
tell them apart by status alone. Fixed by treating `homework_assignments` as
ground truth: `UPDATE cases SET status = 'assigned' FROM homework_assignments
WHERE ... AND homework_status NOT IN ('completed','cancelled') AND
cases.status = 'not_started'`.

**Rule:** any time you're about to bulk-mutate `cases.status` outside the
app's own RPCs, first check whether `homework_assignments` (or any other
table with an invariant tied to status) already has rows for those cases,
and preserve that invariant rather than only looking at `cases` in
isolation.

## 3. A `None` in a pandas object/string column round-trips as `NaN` — and `NaN` is truthy

**Looks reasonable:** `"instruction": case.get("instruction")` in a dict fed
to `pd.DataFrame(rows)`, then later `if case.get("instruction"): st.warning(...)`.

**Is wrong:** once that dict list goes through `enrich_cases()` → a pandas
DataFrame → `.iloc[i].to_dict()`, a `None` that shared a column with real
string values can come back out as `float('nan')`, not `None`. `bool(float
('nan'))` is `True`. The `if case.get("instruction"):` check then fires for
*every* case without an instruction, rendering a warning box with the literal
text `"nan"`.

**Caught by:** feeding real Dev data (not hand-built single-row dicts —
those never trigger the dtype coercion) through `enrich_cases()` and printing
the actual `repr()` of the round-tripped value.

**Rule, already the established convention:** any optional string field
going into a row dict built for `enrich_cases()`/pandas must default to
`""`, never bare `None` — see how `notes` already does it:
`(assignment or {}).get("instructions") or ""`. Match that pattern for any
new optional field. When adding a test for this class of bug, build a
DataFrame with **two rows** (one `None`, one real value) in the same column
— a single-row dict never reproduces it.

## 4. Phase-2 cases reuse `set_no = 1` — any "Set N" code path needs a `phase_no` gate

**Looks reasonable:** existing Set 1/2 UI (`select_case_from_list`'s
segmented control, `"Set {set_no}"` captions) should "just work" once
`phase_no` is added to the row.

**Is wrong:** phase-2's 30 cases all carry `set_no = 1` (there's no Set
concept in phase 2 — `catalog_label` `L01`–`L30` replaces it). Any code that
groups/filters by `set_no` without also checking `phase_no` will silently
merge phase-2 cases into phase-1's "Set 1," interleaving unrelated
`catalog_label`s (`6A` next to `L06`) in one list.

**Rule:** every place that branches on `set_no` for display must also branch
on `case_phase_no(row)` first. `case_labels.py`, `components/ui.py`'s
`render_compact_review_header`, and `case_board.py`'s
`select_case_from_list` all do this already — copy their pattern rather than
adding a new "Set" branch from scratch.

## 5. `case_order_number()`'s phase-1 fallback map must never apply to phase-2 rows

**Looks reasonable:** `case_order_number()` already has a `(set_no,
case_no)` → VIP-number fallback map for legacy rows missing
`order_number` — reuse it unconditionally.

**Is wrong:** phase-2 rows share `(set_no=1, case_no)` keys with phase-1 Set
1 rows (case 1–16 overlap directly). Falling back to the phase-1 map for a
phase-2 row with a null `order_number` hands back an unrelated phase-1 case's
real VIP number. `case_order_number()` explicitly checks `case_phase_no(row)
!= 1` and returns `None` instead of consulting the fallback map in that case
— don't remove that guard, and don't add a new phase-1-shaped fallback
elsewhere without the same guard.

## 6. `released_on` is not a hard gate — don't build one around it

Directly related to #1: after the auto-assign revert, a leftover
release-date guard was also removed from the trainee case workspace (it
would have *blocked* a case the trainer explicitly assigned early, before its
suggested release date — the opposite of the trainer's intent). If a
date-based guard on case visibility ever seems necessary again, stop and
re-read #1 first — the answer is almost certainly "no, status already
handles this."

## 7. Blanket `UPDATE`s via the Supabase MCP need a pre-verification pass

Every one of the bugs above involved a direct SQL statement (via the
Supabase MCP) that was correct for the case it was designed for, but too
broad for the actual current state of the table. Before running any
non-trivial `UPDATE`/backfill against Dev:

1. `SELECT` the affected rows first and actually read them.
2. Ask "what other table has a constraint or invariant tied to this column?"
   (Grep migrations for `unique`, `check`, trigger definitions on the target
   table.)
3. Prefer a `WHERE` clause specific enough that re-running it twice is a
   no-op (idempotent), and say so in the migration's own comment.
4. After running it, re-`SELECT` and diff against what you expected — don't
   assume success from the absence of an error.

This is slower per-step but is what caught #2 before it reached a second
round of user-facing breakage.
