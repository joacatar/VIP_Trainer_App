# Application layers

## The rule that holds the codebase together

**Views never query the database.** Every data access goes through
`TrainingRepository` (`repository.py`, ~1140 lines, one class, one method per
query/RPC). Views call the repository; the repository calls Supabase. Pure
business logic (scoring, filtering, date math, label formatting) lives in
Streamlit-free modules so it stays unit-testable without mocking Streamlit.

When adding a feature: new query → add a method to `TrainingRepository`. New
business rule with no UI dependency → new function in the relevant pure
module (`metrics.py`, `case_board.py`'s pure helpers, `case_labels.py`, etc.),
with a test. New screen or interaction → a `views/*.py` function, wired into
an `app_pages/*.py` file.

## `src/ct_training_tracker/` — module map

**Core plumbing**
- `application.py` — the `run()` entry point: auth gate, profile load, role-based navigation.
- `runtime.py` — `AppRuntime` dataclass (client + repository + profile), built once per session.
- `auth.py` — Supabase Auth session handling, `clear_session()`.
- `config.py` — typed `SupabaseSettings` from `st.secrets`.
- `routing.py` — query-param helpers (`?trainee=&case=&view=`) for shareable deep links.
- `repository.py` — **the only module that talks to Supabase.** One class, `TrainingRepository`.
- `models.py` — `TypedDict`s for the shapes repository methods return (`Profile`, `Trainee`, `CorrectionThread`, `HomeworkAssignment`, ...).

**Pure business logic (no Streamlit, no Supabase — unit tested)**
- `metrics.py` (~900 lines) — the biggest pure module. Case ownership
  (`case_owner`, `owned_by_statuses`), `case_attention_state` (the single
  source of truth for kanban lane / dashboard bucket), `BoardCard` +
  `build_board_card`, dashboard/forecast math.
- `analytics.py` — event-derived training analytics (turnaround times,
  first-pass acceptance, recurring corrections) from `tracking_events`.
- `revisions.py` — the 8 fixed review sections, their checklists, section
  labels.
- `resource_rules.py` — rule-based `case_resources` suggestions (edit
  `RESOURCE_RULES` to change what gets attached to a new trainee's cases).
- `trainee_filters.py` — hiding `is_test` trainees from trainer views.
- `case_labels.py` — `case_title()`/`case_label()`/`case_catalog_label()`/
  `case_order_number()` — phase-aware display formatting. See gotchas.md for
  the VIP-order-number leak this module guards against.
- `files.py` — file-kind labels, extension validation, per-status editability
  sets used by the upload UI.
- `questions.py` — question status labels/counts.

**Streamlit-aware caching**
- `data_cache.py` — `st.session_state`-backed, 45s-TTL cache for
  trainer-side lookups (`cached_active_trainees`, `cached_trainee_cases`,
  `cached_homework_for_cases`). Call `invalidate_trainer_cache()` after any
  mutation. Trainee-side views do **not** use this cache — they fetch fresh
  every rerun (much smaller, less frequently viewed data).
- `storage_cache.py` — per-session cache for downloaded Storage bytes, so a
  screenshot/file isn't re-downloaded on every rerun.

**Components** (`components/`)
- `ui.py` — shared primitives: `render_page_header`, `render_case_header`
  (the full case header — status badge, due date, **mandatory instruction
  callout**), `render_compact_review_header` (one-line trainer review
  header), `render_empty_state`, `status_color`, `constrained_width`.
- `progress_journey.py` — the CCv2 "journey" visual (circles + category
  chips) for phase-1 Set 1/2. **Phase-1 only** — see gotchas.md.
- `paste_image.py` — the custom CCv2 component for pasting review
  screenshots.
- `ask_panel.py` — the floating case-context chat/question panel.

**Views** (`views/`) — one file per screen area, called from `app_pages/*.py`
- `trainer.py` (~660 lines) — dashboard, cases inbox/board host, add-trainee
  form, `_assign_case()` (the one homework-assignment flow, shared by phase 1
  and phase 2), trainer case workspace.
- `trainee.py` — trainee dashboard (next-up card, "all caught up" state,
  progress journey, corrections summary) and the trainee case workspace.
- `case_board.py` — shared pure-ish helpers used by both roles:
  `enrich_cases()` (raw case rows → a pandas DataFrame with display columns),
  `apply_case_filter`/`sort_case_rows`/`pick_next_case`,
  `select_case_from_list()` (the filterable case list/inbox widget — phase
  and Set 1/2 aware), `render_case_summary`.
- `kanban.py` — the trainer's default "Board" view: 4 lanes
  (Assigned / With trainee / Needs you / Approved), pooled across every case
  regardless of phase.
- `case_files.py` — the three-slot (PDF1/PDF2/OV) OneDrive-link submission
  UI, both trainee-editing and trainer-reviewing sides.
- `revisions.py` — the guided review flow: section checklists, correction
  threads, publish.
- `questions.py` — trainee↔trainer Q&A threads, both inboxes.
- `resources.py` — per-case `case_resources` editor (trainer) and read-only
  display (trainee).
- `bulk_due_dates.py` — multi-select + bulk due-date update across cases.
- `metrics.py` — the trainer's "Performance & forecast" tab.
- `login.py` — sign-in screen.

## `app_pages/*.py`

Thin route wrappers only: `require_runtime()` (or `create_client_or_none()`
for login) → role check → call the one `views/` function for that screen.
Business logic never lives here. If a page file starts doing anything beyond
that, it belongs in `views/` instead.

## Why this layering matters for future changes

Every non-obvious bug found in this session traced back to a place where a
change crossed a layer boundary without checking every consumer:

- Changing `case_label()`'s output format (case_labels.py, pure) rippled
  correctly into every UI that imports it — because nothing recomputes the
  label itself.
- Changing `cases.status` directly via SQL (bypassing the
  `assign_homework()` RPC / `homework_assignments` table) silently broke an
  invariant that only the RPC path knows to maintain. See gotchas.md.

**Rule of thumb:** if you need to change data outside the app's own RPCs
(e.g. via the Supabase MCP for a backfill), first grep for every other place
that reads or writes the same table, and check what invariants those RPCs
maintain that a raw `UPDATE` would not.
