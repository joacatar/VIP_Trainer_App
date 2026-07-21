# Step-by-step implementation plan

Each milestone should be usable and verified before starting the next one.

## 1. Tracking foundation

Status: implemented locally; remote Supabase application pending

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

- Trainer sends homework with suggested and overridable due dates.
- Trainee uploads two PDFs and one OV into separate versioned slots.
- Trainer downloads, accepts, or requests replacement for each file separately.
- Accepted files stay accepted unless the trainer explicitly reopens them.
- Case and assignment statuses update transactionally.

Exit criteria:

- A rejected file alone can be resubmitted without resending accepted files.
- Every version and review decision remains in history.
- Dashboard accurately shows who is waiting on whom.

## 3. Revisions and corrections

- Eight fixed review sections
- Multiple corrections per section
- Severity, status, trainer notes, and pasted screenshots
- Publish a revision to the trainee portal
- Roll unresolved corrections into the next revision

Exit criteria:

- Previous revisions remain immutable and readable.
- A new revision starts with unresolved work and does not duplicate resolved work.

## 4. Questions

- Case/revision/section-linked trainee question threads
- Trainer unanswered-question inbox
- Screenshot attachments and resolved status
- Notifications inside each portal

Exit criteria:

- Every question has an owner, timestamp, context, and response state.
- Questions cannot be lost inside free-form correction notes.

## 5. Metrics and forecasting

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

- Private trainee notebook
- APAC dashboard consolidation
- Email reminders
- Chat assistant over approved training material and trainer-reviewed answers
