# Step-by-step implementation plan

Each milestone should be usable and verified before starting the next one.
We implement and review one numbered milestone at a time; the MVP is not built in
one unreviewed batch.

## 0. UI/UX foundation and flow redesign

Status: planned — complete this milestone before adding metrics or later features.

### Audit: what is wrong today

The product flows work, but the UI is assembled widget by widget rather than from
a shared hierarchy and task model. This causes the two problems reported by users:

- **Uncomfortable night use.** There is no project theme configuration, so dark
  mode is not deliberately designed or tested. The custom screenshot/comment
  component needs to inherit the same semantic colors as the application.
- **Inconsistent density.** Full-width pages leave large empty areas on simple
  forms, while five-column KPI rows, nested columns, long radio labels, and
  per-file controls make action-heavy pages cramped.
- **Weak orientation.** Route captions such as `Path: /trainer` are developer
  information, not user guidance. Status, due date, next owner, and next action
  are not consistently presented as a single case header.
- **No explicit workflow.** File submission is spread across three cards and a
  final button without a persistent “step 1 of 3” explanation or a clear review
  state. Feedback and question workflows show many controls at once, including
  actions that are secondary to the user’s immediate task.
- **Uneven visual language.** Labels, messages, button priority, cards, metrics,
  empty states, and status presentation vary by page. Some success/info messages
  take more space than the decision or action they support.
- **Desktop-first layout.** Two fixed content columns and many small-column
  grids do not degrade well on a narrow laptop or tablet. `st.tabs` also renders
  all hidden content, which makes complex case pages feel heavier than necessary.
- **Legacy API cleanup is needed.** Image rendering still uses
  `use_container_width`; replace it with the supported width API during this
  work.

### Design principles and non-negotiable rules

1. **One task per visual region.** Every page begins with a concise title,
   outcome-oriented supporting text, and—where relevant—one primary action.
   Metadata is secondary; technical routes are never shown to end users.
2. **Actionable status.** Every case must state: current status, owner of the
   next action, due date, and the one action needed to move forward. Do not rely
   on color alone; pair status colors with text and Material Symbols icons.
3. **Comfortable density.** Use a constrained readable width for login and
   forms; use wide layout only for dashboards and case workspaces. Limit KPI rows
   to four items; group related controls in bordered containers and use small,
   intentional gaps rather than blank vertical space or repeated dividers.
4. **Predictable actions.** One primary button per section, clear secondary
   actions, confirmations for irreversible actions, and immediate toast/success
   feedback after saved changes. Disabled/unavailable actions explain why.
5. **Accessible by default.** Sentence-case labels, visible labels (or an
   accessible collapsed label), keyboard-operable controls, descriptive errors,
   WCAG AA contrast, and semantic status text are mandatory.
6. **Native Streamlit first.** Use native containers, forms, dialogs, badges,
   `segmented_control`, `pills`, and theme configuration. Do not add global CSS
   for visual styling; keep the existing custom component only where its pasted
   image interaction is needed.

### Visual system: implement once, consume everywhere

1. Create `.streamlit/config.toml` with paired `[theme.light]` and
   `[theme.dark]` definitions so the Streamlit settings menu offers both modes.
   Use a neutral clinical palette: calm blue primary, green success, amber
   attention, red blocking error, and high-contrast charcoal/slate surfaces.
   Set matching main, secondary, sidebar, border, dataframe, and semantic status
   colors; use an Inter-like sans-serif font, 8px base radius, visible widget
   borders, and a clear sidebar boundary.
2. Test both modes against button text, inputs, badges, tables, screenshots,
   expanders, navigation, empty states, and custom `comment_box` states. The
   component must use Streamlit theme variables only and must not hard-code a
   light surface or low-contrast text.
3. Add shared view helpers (for page header, case header, status badge, next-step
   callout, empty state, metrics row, and action bar) rather than copying layouts
   into each view. Helpers must preserve the existing repository and business
   APIs.
4. Establish component rules: `st.container(border=True)` for a meaningful
   group, up to four metrics in a row, `st.container(horizontal=True)` for action
   groups, `st.form` for multi-input commits, `st.dialog` for focused destructive
   or confirm-before-submit decisions, and `width="stretch"`/`width="content"`
   rather than deprecated sizing options.

### Page-by-page redesign

#### Sign in (`views/login.py`)

- Replace the bare full-width form with a centered, readable sign-in card:
  product mark/name, one-line value statement, and a short privacy/support note.
- Keep email and password labels visible, add appropriate autocomplete support
  if available, make **Sign in** the single full-width primary action, and place
  authentication errors inside the card in user-friendly language (without
  exposing raw provider exceptions).
- Retain password visibility/accessibility behavior and show a busy state while
  authenticating. Validate empty email/password before making the request.

#### Shared navigation and identity (`application.py`)

- Replace the minimal sidebar text with a compact signed-in identity block,
  role label, and a clearly separated sign-out action. Keep navigation in the
  top bar and app-level account controls in the sidebar only.
- Use consistent Material Symbols and sentence-case labels. Add a logo only if a
  real branded asset is supplied; do not use decorative emoji as the primary
  product identity.

#### Trainer dashboard (`views/trainer.py:render_dashboard`)

- Reframe as **Today’s training work**: a short summary plus at most four
  decision KPIs (needs review, overdue, awaiting trainee, open questions).
  Move all-time completion to a secondary progress card/table to remove the
  current five-column squeeze.
- Make **Needs attention** the first actionable area. Render compact priority
  cards ordered by overdue/review/question urgency; each card shows trainee,
  case count, reason, next action, and one contextual CTA—not a generic list.
- Convert the question inbox into an urgent, count-badged queue with snippets
  and one **Answer** CTA. Keep the trainee progress table below it as a scannable
  management view with useful column configuration and an explicit empty state.

#### Add trainee (`views/trainer.py:render_trainees`)

- Use a narrow form card rather than three equal desktop columns. Group identity
  (name, email) and schedule (start date, timezone), explain that 32 cases and
  96 file requirements will be created, and make this consequence visible before
  submit.
- Validate email format and required fields inline; retain submitted values on a
  recoverable error. After success, show the created trainee and offer a direct
  **Open trainee cases** CTA instead of only rerunning.

#### Case workspace and assignment (`views/trainer.py:render_cases`,
`views/trainee.py`, `views/case_board.py`)

- Create one shared case-workspace header for both roles: breadcrumb-like
  trainee/set/case context, status badge, due date, file progress, next owner,
  and one role-specific next-step callout. Remove route captions.
- Replace long, dense case radio labels with a compact selectable case list that
  exposes set switching through a `segmented_control` and shows status/due/file
  metadata in rows. Persist the existing URL selection behavior.
- On desktop, retain a responsive master-detail layout; on narrow widths, make
  the case selector precede the detail in one column. Avoid nesting multiple
  column grids inside the narrow selector rail.
- For an unstarted case, use an assignment card with schedule-derived due date,
  optional instructions, clear consequences, and one **Assign case** CTA. Use a
  confirmation dialog only if assignment becomes non-reversible.
- Keep Files, Feedback/Review, and Questions as peer task areas, but lazy-render
  the selected area or replace eager tabs with a segmented control so hidden
  screenshot/revision work is not computed unnecessarily.

#### Trainee case overview (`views/trainee.py`)

- Replace “Welcome” plus a loose KPI row with a task-first overview: **Your next
  case**, its due date/status, what to do next, and compact totals for to do,
  with trainer, and approved. Use the selected case as the source of truth for
  the right panel.
- Do not show a metric row inside every file tab unless it changes a decision;
  show concise package progress in the case header and per-slot progress where
  the action happens.

#### File submission and trainer file review (`views/case_files.py`)

- Turn the three file links into an explicit three-step checklist. Each slot card
  contains file name, status, replacement reason if applicable, one link field,
  and a single state-appropriate action. Show “1 of 3 ready” prominently and
  keep accepted slots visually compact.
- Put package submission in a final sticky-looking action region after the
  checklist: explain the lock/review consequence, disable it until all slots are
  ready, and use a confirmation dialog before **Submit for review**.
- In the trainee waiting state, replace editable-looking cards with a calm
  read-only timeline and the reviewer name. In the trainer view, separate
  **Open file** from the secondary **Request replacement** action; require a
  reason when requesting replacement and show exactly what the trainee will see.
- Ensure labels distinguish link saving, marking ready, submitting the package,
  reviewing files, and sending a replacement request; these are currently easy
  to confuse.

#### Trainer feedback and trainee feedback consumption (`views/revisions.py`)

- Make review a guided flow: start review → select section → record findings →
  review summary → publish. Show draft/published state and unsaved/open counts
  persistently in the header; use **Publish feedback** only as the final primary
  action.
- In each section, make the checklist the first control, put optional narrative
  and screenshots in a clearly labelled evidence area, and reduce simultaneous
  controls. Keep screenshot upload available but collapsed until needed.
- Replace the trainee’s broad “Review feedback” presentation with a clear result
  summary: what needs fixing now, what is already correct, attached evidence,
  and the next action. Open only relevant correction groups by default; resolved
  or older items remain discoverable but visually quiet.
- Before publish, validate that feedback is intentional (including an explicit
  “all sections OK” path) and show a confirmation summary so blank drafts cannot
  be mistaken for a completed review.

#### Questions and answers (`views/questions.py`)

- Present the trainee question composer as a focused mini-form: optional context
  selector, question text, optional screenshot evidence, and one **Send
  question** action. Put conversation history below the composer, ordered and
  labelled as a thread rather than a collection of large expanders.
- Give each question a visible lifecycle: open → answered → resolved, including
  author/time, context, answer, and only the next relevant action. Reopen is a
  secondary action with an explanation.
- In the trainer inbox, make the primary CTA **Answer question**, deep-link to
  the exact item, and show age/context before the full body. Within a case,
  render an answer form only for the focused/open item and group lower-priority
  answered/resolved threads separately to prevent visual overload.

### Delivery order

1. **Design tokens and shared primitives:** theme configuration, dark-mode
   verification, page/case/status/empty-state helpers, deprecated image-width
   cleanup.
2. **Access and orientation:** sign-in, navigation/account block, page headers,
   removal of route captions and standard empty/error states.
3. **Trainer work management:** dashboard, inbox priority cards, add-trainee
   form, case selector and assignment experience.
4. **Trainee execution:** task-first case overview and progressive file
   submission/replacement states.
5. **Collaboration:** trainer feedback composer/publish flow, trainee feedback
   reading flow, questions and answers.
6. **Responsive and polish pass:** test at narrow laptop/tablet width, keyboard
   navigation, screen reader labels, all statuses, light/dark mode, loading and
   error states; then run UAT with one trainer and one trainee.

### UI acceptance criteria

- Light and dark modes are both selectable, readable, and visually coherent;
  all text and interactive status treatments meet WCAG AA contrast targets.
- A first-time trainee can identify the current case, due date, next owner, and
  next action within five seconds without reading a URL or opening every tab.
- A trainee can paste three links and submit a package without ambiguity about
  whether a link was saved, marked ready, or sent for review.
- A trainer can identify the highest-priority case/question and reach the exact
  action in no more than two intentional clicks from the dashboard.
- Feedback publication and replacement requests state their effect before the
  change; no destructive or locking transition occurs accidentally.
- Pages remain usable at 1024px wide, avoid rows with more than four KPI cards,
  and do not present narrow action controls caused by unnecessary nested columns.
- Existing authorization, status transitions, repository calls, query-parameter
  deep links, and automated behavior tests continue to pass. Add focused view
  tests for the new state/validation helpers and perform manual visual regression
  checks in both themes.

## 1. Tracking foundation

Status: complete locally and applied to the `VIP Trainer` Supabase project

- Supabase Auth roles for trainer and trainee
- Trainee records and APAC-derived working-day schedule
- Automatic Set 1/2 × Case 1–16 creation
- Three independent file requirements per case
- Homework due-date records
- Immutable tracking-event foundation
- Trainer overview and trainee case-list shells
- Private Storage bucket and RLS policies

Exit criteria:

- Creating one trainee produces 32 cases and 96 file requirements.
- Dates follow the existing APAC case-day mapping and skip weekends/holidays.
- A trainee can only read their own data.
- A trainer can see all assigned trainee data.

## 2. Homework and file submissions

Status: complete pending UAT — assignment, OneDrive links, package submit for
review, routed case board, and waiting indicators

Implementation order:

1. Trainer account bootstrap and trainee invitation/linking.
2. Trainer homework form with schedule-derived, overridable due date.
3. Trainee case page with separate PDF 1, PDF 2, and OV slots (OneDrive link +
   mark ready; no binary upload for case files).
4. Versioned private Storage upload and download (legacy; case files now use links).
5. Trainee notifies trainer when the full package is ready (`in_review`).
6. Trainer opens links, starts revisions, or requests replacement (send-back).
7. Status transitions and “waiting on trainer/trainee” dashboard indicators.

- Trainer sends homework with suggested and overridable due dates.
- Trainee pastes OneDrive links and marks PDF 1 / PDF 2 / OV as ready (can undo
  until the package is submitted).
- Trainee clicks **Notify trainer for review** when all three slots are ready.
- While `in_review`, trainee sees “Submitted for review” and waits; edits are locked.
- Trainer opens links and can start a revision immediately, or request replacement
  to send a slot back (`awaiting_resubmission`).
- Case and assignment statuses update transactionally.
- Dashboard shows packages in review versus files still to send.

Exit criteria:

- A rejected file alone can be fixed and the package resubmitted.
- Every review decision remains in history.
- Dashboard accurately shows who is waiting on whom.
- Revisions unlock on package submit (not on per-file accept).

## 3. Revisions and corrections

Status: complete pending UAT — checklists, paste screenshots, package submit,
protocol OK vs needs-work

## 4. Questions

Status: complete pending UAT — ask/answer, inbox, screenshots, status lifecycle

## 5. Metrics and forecasting

Status: complete pending UAT — event-derived views + dashboard Performance section

- First-pass file/package acceptance rate
- Published revision and resubmission counts
- Trainer and trainee turnaround time from tracking events
- Recurring corrections by section (published revisions)
- Planned versus actual approval dates
- Estimated phase completion using observed assign→approve pace

Exit criteria:

- Metrics derive from timestamped events rather than mutable status alone.
- The dashboard explains the inputs behind each completion estimate.

## 6. Later features

Status: backlog

- Private trainee notebook
- APAC dashboard consolidation
- Email reminders
- Chat assistant over approved training material and trainer-reviewed answers
