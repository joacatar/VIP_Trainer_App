-- Data-repair: realign case.status with homework_assignments after the
-- 20260823180000 revert.
--
-- 20260823180000 blanket-reverted every phase-2 case whose status was
-- 'assigned' back to 'not_started'. That was correct for the cases my
-- earlier (wrong) auto-assign migration had touched — but it did not
-- account for cases the trainer had *already assigned for real* through the
-- app in between: those already had a genuine, open `homework_assignments`
-- row (status 'sent'), and the blanket revert silently knocked their case
-- status back to 'not_started' without touching that row. The trainer's
-- inbox then showed those cases as needing assignment again, and clicking
-- "Assign case" hit `one_open_homework_per_case_idx` — a real assignment
-- already existed for that case.
--
-- `homework_assignments` is the source of truth for "has this case been
-- assigned" (that's exactly what the unique index enforces: at most one open
-- assignment per case). This restores `cases.status` to 'assigned' for any
-- case that has an open homework_assignments row but was left at
-- 'not_started' — a no-op everywhere this inconsistency doesn't exist.

update public.cases as c
set status = 'assigned'::public.case_status
from public.homework_assignments as h
where h.case_id = c.id
  and h.status not in ('completed', 'cancelled')
  and c.status = 'not_started';
