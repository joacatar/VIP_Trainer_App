-- Backfill: start phase 2 for trainees who already had all 32 phase-1 cases
-- approved before the auto-start trigger (on_case_approved_start_phase_2,
-- migration 20260823140000) existed.
--
-- The trigger only fires on a fresh transition into 'approved'. A trainee
-- whose 32nd case was approved before the trigger existed never produced
-- that transition afterwards, so they were silently stuck outside phase 2
-- even though they satisfy the rule ("automatic once all 32 are approved").
-- This runs the same check the trigger runs, once, for every trainee who
-- currently qualifies. private.start_phase_2() is idempotent (it no-ops if
-- phase_2_started_on is already set), so this is safe to re-run and safe to
-- apply on top of environments where the trigger has already handled
-- everyone correctly (Prod, once it reaches this point).

do $$
declare
  candidate record;
begin
  for candidate in
    select t.id
    from public.trainees as t
    where t.phase_2_started_on is null
      and not exists (
        select 1
        from public.cases as c
        where c.trainee_id = t.id
          and c.phase_no = 1
          and c.status <> 'approved'
      )
      and exists (
        select 1
        from public.cases as c
        where c.trainee_id = t.id
          and c.phase_no = 1
      )
  loop
    perform private.start_phase_2(candidate.id, current_date);
  end loop;
end;
$$;
