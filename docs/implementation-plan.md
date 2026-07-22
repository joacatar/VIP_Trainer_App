# Step-by-step implementation plan

Each milestone should be usable and verified before starting the next one.
We implement and review one numbered milestone at a time; the MVP is not built in
one unreviewed batch.

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

Status: in progress — section checklists + free text + screenshots wired;
Ctrl+V paste and UI polish deferred

- Eight fixed review sections with Peer Review checklist templates
- Multiple checklist selections + free-text comments per section
- Screenshots attached primarily via Ctrl/Cmd+V paste (upload from disk is fallback)
- Status open/resolved; severity defaults to minor (hidden in UI)
- Publish a revision to the trainee portal
- Roll unresolved corrections into the next revision

Exit criteria:

- Previous revisions remain immutable and readable.
- A new revision starts with unresolved work and does not duplicate resolved work.
- Trainer can mark multiple checklist items plus free text per section.

## 4. Questions

Status: pending until milestone 3 is reviewed

- Case/revision/section-linked trainee question threads
- Trainer unanswered-question inbox
- Screenshot attachments and resolved status
- Notifications inside each portal

Exit criteria:

- Every question has an owner, timestamp, context, and response state.
- Questions cannot be lost inside free-form correction notes.

## 5. Metrics and forecasting

Status: pending until milestone 4 is reviewed

- First-pass file acceptance
- Revision and resubmission counts
- Trainer and trainee turnaround time
- Recurring corrections by section
- Planned versus actual dates
- Estimated phase completion using observed pace

Exit criteria:

- Metrics derive from timestamped events rather than mutable status alone.
- The dashboard explains the inputs behind each completion estimate.

## 6. Later features

Status: backlog

- Private trainee notebook
- APAC dashboard consolidation
- Email reminders
- Chat assistant over approved training material and trainer-reviewed answers
