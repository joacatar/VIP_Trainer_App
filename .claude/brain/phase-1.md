# Phase 1 — the 32-case catalog

Status: shipped, in real use by real trainees on Dev.

## What it is

A fixed catalog of 32 training cases, identical for every trainee: Set 1
cases 1–16 (`catalog_label` `1A`–`16A`) and Set 2 cases 1–16 (`1B`–`16B`).
Creating a trainee (`views/trainer.py:render_trainees` →
`repository.create_trainee()`) fires trigger `on_trainee_created` →
`private.create_trainee_cases()`, which inserts all 32 rows from
`case_schedule_template` (`phase_no = 1`) in one shot, with due dates
computed from `trainees.start_date` via `private.training_date()`. Each case
immediately gets its 3 `file_requirements` via trigger `on_case_created` — 96
file requirements per trainee, all at creation time.

## Journey categories

Each phase-1 case belongs to one of six categories (`journey_category` on
both the template and the case row): `Success Journey`, `OV Adjusted`,
`Rejections`, `Manual`, `Duplicate`, `Axial3D Case`. These drive
`components/progress_journey.py`'s category-chip grouping — the visual map
trainees see of their Set 1/2 progress. Phase 2 has no equivalent categories
(see phase-2.md) and the journey component is intentionally scoped to
phase-1 rows only.

## Deliverables and review cycle

Every case needs three OneDrive links from the trainee: PDF 1
(`pdf_primary`), PDF 2 (`pdf_secondary`), OV (`ov`) — no binary upload, just a
pasted link + "mark ready" per slot (`views/case_files.py`). Once all three
are ready, the trainee clicks "Notify trainer for review," which submits the
whole package (`submit_case_for_review` RPC) and locks editing.

The trainer reviews against 8 fixed sections (`revisions.py:REVIEW_SECTIONS`:
scan, rider form, segmentation, scapula, glenoid landmark, humeral landmark,
humeral implant, glenoid implant), each with a checklist template
(`SECTION_CHECKLISTS`) plus optional narrative and pasted screenshots. A
correction on a section opens a `correction_threads` row; each subsequent
revision either resolves it or logs a `correction_events` "still open" entry
— threads roll forward across revisions until actually fixed, rather than
resetting each time.

Case status walks `assigned → submitted → in_review → corrections_sent →
awaiting_resubmission → approved` (see data-model.md for the full lifecycle
and who owns each status). The trainer can approve individual files
independently of the whole package; publishing a revision with zero open
corrections and every file accepted moves the case to `approved`.

## What triggers phase 2

**All 32 phase-1 cases reaching `approved`** — not "submitted," not
"in review" — is the sole condition. See phase-2.md for exactly how that
transition is detected and what it kicks off.

## Files worth knowing for phase-1 work

- `views/case_files.py` — the three-slot submission/review UI.
- `views/revisions.py` (1500+ lines, the largest view file) — the guided
  review flow: start review → select section → record findings → summary →
  publish.
- `revisions.py` (pure) — section definitions and checklist content; edit
  here to change what a section's checklist prompts for.
- `resource_rules.py` — a couple of phase-1-only rules exist today (e.g. a
  "getting started" link for Set 1 cases 1–4, a manual-planning reminder for
  cases 12–13). Match on `set_no`/`case_no_range`, not `phase_no` — adding a
  phase-2 rule here needs a `phase_no` match added to `_matches()` first (see
  phase-2.md's open work).
