-- Fix: phase-2 live cases were created with the default status
-- ('not_started'), which is trainer-owned — the trainee never sees a
-- not_started case (owned_by_statuses('trainee') doesn't include it; the
-- trainee dashboard shows "Waiting for assignment" and hides it from
-- "needs you"). Phase 1 clears this gate through an explicit trainer
-- "Assign case" action; phase 2 has no such step by design (release IS the
-- trigger), so start_phase_2() must create cases already 'assigned',
-- trainee-owned from the moment they're released.
--
-- Without this fix, every phase-2 case for every trainee is invisible to the
-- trainee forever unless the trainer manually assigns all 30 of them one by
-- one — exactly the manual step phase 2 was designed to avoid.

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
    released_on,
    status
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
    private.training_date(anchor, template.training_day),
    'assigned'::public.case_status
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

-- Backfill: any phase-2 cases already created by the buggy version (still
-- 'not_started', never touched by a trainee or trainer) become 'assigned'.
update public.cases
set status = 'assigned'::public.case_status
where phase_no = 2
  and status = 'not_started';
