-- Phase 2 case catalog: real VIP order numbers, case type, and per-case
-- instructions.
--
-- The 30 simulated live cases each map to a training order (order_number, the
-- case the trainee opens in VIP) and the production case it mirrors
-- (source_order_number, trainer reference only — trainees see no detail beyond
-- their assigned case).
--
-- Five cases must be rejected and planned manually for practice, and three are
-- plan-only. That instruction has to reach the trainee automatically, so it is
-- a column on the case rather than a resource: resources render inside a
-- collapsed expander marked "suggested", which is too quiet for a mandatory
-- step.

alter table public.case_schedule_template
  add column if not exists source_order_number text;

alter table public.case_schedule_template
  add column if not exists instruction text;

alter table public.cases
  add column if not exists source_order_number text;

alter table public.cases
  add column if not exists instruction text;

-- 1. The catalog ------------------------------------------------------------

update public.case_schedule_template as t
set order_number        = v.order_number,
    source_order_number = v.source_order_number,
    journey_category    = v.case_type,
    instruction         = nullif(v.instruction, '')
from (values
  (1,  '12-26-07-0002', '12-26-06-3763', 'Success', ''),
  (2,  '12-26-07-0025', '12-26-06-3256', 'Success', ''),
  (3,  '12-26-07-0026', '12-26-06-3393', 'Success', ''),
  (4,  '12-26-07-0003', '12-26-06-3088', 'Success', ''),
  (5,  '12-26-07-0004', '12-26-06-3049', 'Success', ''),
  (6,  '12-26-07-0005', '12-26-06-3319', 'Manual',
       'Reject and plan manually for practice'),
  (7,  '12-26-07-0028', '12-26-05-1038', 'Success', ''),
  (8,  '12-26-07-0006', '12-26-06-2954', 'Success', ''),
  (9,  '12-26-07-0008', '12-26-06-2043', 'Success', ''),
  (10, '12-26-07-0010', '12-26-06-2645', 'Success', ''),
  (11, '12-26-07-0012', '12-26-06-2582', 'Success', ''),
  (12, '12-26-07-0014', '12-26-06-2787', 'Manual',
       'Reject and plan manually for practice'),
  (13, '12-26-07-0016', '12-26-06-2468', 'Success', ''),
  (14, '12-26-07-0018', '12-26-06-1843', 'Success', ''),
  (15, '12-26-07-0029', '12-26-05-0893', 'Success', ''),
  (16, '12-26-07-0031', '12-26-06-1646', 'Success', 'Plan only'),
  (17, '12-26-07-0032', '12-26-06-1608', 'Success', ''),
  (18, '12-26-07-0033', '12-26-06-1335', 'Manual',
       'Reject and plan manually for practice'),
  (19, '12-26-07-0034', '12-26-06-0773', 'Success', ''),
  (20, '12-26-07-0035', '12-26-06-0722', 'Success', ''),
  (21, '12-26-07-0036', '12-26-06-0336', 'Success', ''),
  (22, '12-26-07-0039', '12-26-05-1537', 'Success', 'Plan only'),
  (23, '12-26-07-0040', '12-26-06-0203', 'Success', 'Plan only'),
  (24, '12-26-07-0041', '12-26-05-3191', 'Manual',
       'Reject and plan manually for practice'),
  (25, '12-26-07-0042', '12-26-05-2644', 'Success', ''),
  (26, '12-26-07-0043', '12-26-05-2391', 'Success', ''),
  (27, '12-26-07-0044', '12-26-05-2304', 'Success', ''),
  (28, '12-26-07-0046', '12-26-05-1938', 'Success', ''),
  (29, '12-26-07-0047', '12-26-05-1230', 'Success', ''),
  (30, '12-26-07-0048', '12-26-05-3024', 'Manual',
       'Reject and plan manually for practice')
) as v(case_no, order_number, source_order_number, case_type, instruction)
where t.phase_no = 2
  and t.case_no = v.case_no;

-- 2. Backfill phase-2 cases already created -----------------------------------

update public.cases as c
set order_number        = t.order_number,
    source_order_number = t.source_order_number,
    journey_category    = t.journey_category,
    instruction         = t.instruction
from public.case_schedule_template as t
where t.phase_no = 2
  and c.phase_no = 2
  and t.set_no = c.set_no
  and t.case_no = c.case_no;

-- 3. Carry the new columns when cases are created ------------------------------

create or replace function private.create_trainee_cases()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
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
    new.id,
    'ct_planning'::public.training_phase,
    1,
    template.set_no,
    template.case_no,
    template.catalog_label,
    template.order_number,
    template.source_order_number,
    template.journey_category,
    template.instruction,
    template.training_day,
    private.training_date(new.start_date, template.training_day),
    private.training_date(new.start_date, template.training_day),
    new.start_date
  from public.case_schedule_template as template
  where template.phase_no = 1;
  return new;
end;
$$;

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
