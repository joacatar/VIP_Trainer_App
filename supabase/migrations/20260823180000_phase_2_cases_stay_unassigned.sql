-- Revert 20260823170000: phase-2 cases do NOT auto-assign to the trainee.
--
-- Correction from the trainer: only case CREATION and the release/pacing
-- schedule are automatic. The trainer still assigns each phase-2 case
-- individually, exactly like phase 1 — the 30 cases sit in the trainer's
-- inbox as 'not_started' ("needs assignment"), and a trainee sees only what
-- the trainer has explicitly assigned via the existing "Assign case" flow.
-- `released_on`/`due_date` remain the *suggested* pacing shown when the
-- trainer assigns a case (same role schedule_due_date already plays in
-- phase 1's _assign_case()) — they are not a visibility gate.

create or replace function private.start_phase_2(
  p_trainee_id uuid,
  p_anchor date default null
)
returns void
language plpgsql
security definer
set search_path = ''
as $$
declare
  anchor date := coalesce(p_anchor, current_date);
begin
  -- Idempotent: a trainee only enters phase 2 once.
  update public.trainees
  set phase_2_started_on = anchor
  where id = p_trainee_id
    and phase_2_started_on is null;

  if not found then
    return;
  end if;

  insert into public.cases (
    trainee_id,
    phase,
    phase_no,
    set_no,
    case_no,
    catalog_label,
    order_number,
    source_order_number,
    journey_category,
    instruction,
    scheduled_training_day,
    schedule_due_date,
    due_date,
    released_on
  )
  select
    p_trainee_id,
    'ct_planning'::public.training_phase,
    2,
    template.set_no,
    template.case_no,
    template.catalog_label,
    template.order_number,
    template.source_order_number,
    template.journey_category,
    template.instruction,
    template.training_day,
    private.training_date(anchor, template.training_day + 1),
    private.training_date(anchor, template.training_day + 1),
    private.training_date(anchor, template.training_day)
    -- status omitted -> defaults to 'not_started', same as phase 1's
    -- create_trainee_cases(). The trainer assigns each one explicitly.
  from public.case_schedule_template as template
  where template.phase_no = 2
  on conflict (trainee_id, phase_no, set_no, case_no) do nothing;

  insert into public.tracking_events (
    trainee_id, case_id, actor_user_id, event_type, event_data
  )
  values (
    p_trainee_id,
    null,
    (select auth.uid()),
    'phase_2_started',
    jsonb_build_object('anchor', anchor, 'case_count', 30)
  );
end;
$$;

-- Revert the two trainees the previous (incorrect) migration touched. Safe:
-- these 60 rows were created minutes ago and nothing has interacted with
-- them (no files, no reviews) — reverting status loses no real work.
update public.cases
set status = 'not_started'::public.case_status
where phase_no = 2
  and status = 'assigned';
