-- Phase 2: simulated live cases.
--
-- In production, trainees finish phase 1 (32 catalog cases) and move on to live
-- production cases. Trainees have no production access, so phase 2 is simulated
-- with 30 fixed cases whose source material is preloaded as case resources
-- (OneDrive links). Trainees still generate and submit PDF 1 / PDF 2 / OV, and
-- the review cycle (submit -> in_review -> corrections -> resubmit -> approved)
-- is unchanged from phase 1.
--
-- Release model: phase 2 starts automatically once all 32 phase-1 cases are
-- approved. Five cases are released per working day (six release days), and a
-- case is due the working day after it is released.

-- 1. Phase discriminator on the schedule template ---------------------------

alter table public.case_schedule_template
  add column if not exists phase_no smallint not null default 1;

alter table public.case_schedule_template
  drop constraint if exists case_schedule_template_pkey;

alter table public.case_schedule_template
  add constraint case_schedule_template_pkey
  primary key (phase_no, set_no, case_no);

alter table public.case_schedule_template
  drop constraint if exists case_schedule_template_case_no_check;

alter table public.case_schedule_template
  add constraint case_schedule_template_case_no_check
  check (case_no between 1 and 30);

alter table public.case_schedule_template
  drop constraint if exists case_schedule_template_phase_no_check;

alter table public.case_schedule_template
  add constraint case_schedule_template_phase_no_check
  check (phase_no between 1 and 2);

-- Phase-2 order numbers are not known yet and phase-2 cases have no journey
-- category, so both become optional.
alter table public.case_schedule_template
  alter column order_number drop not null;

alter table public.case_schedule_template
  alter column journey_category drop not null;

-- 2. Phase discriminator and release date on cases ---------------------------

alter table public.cases
  add column if not exists phase_no smallint not null default 1;

alter table public.cases
  add column if not exists released_on date;

alter table public.cases
  drop constraint if exists cases_case_no_check;

alter table public.cases
  add constraint cases_case_no_check check (case_no between 1 and 30);

alter table public.cases
  drop constraint if exists cases_phase_no_check;

alter table public.cases
  add constraint cases_phase_no_check check (phase_no between 1 and 2);

alter table public.cases
  drop constraint if exists cases_trainee_id_set_no_case_no_key;

alter table public.cases
  drop constraint if exists cases_trainee_phase_set_case_key;

alter table public.cases
  add constraint cases_trainee_phase_set_case_key
  unique (trainee_id, phase_no, set_no, case_no);

alter table public.cases
  alter column order_number drop not null;

alter table public.cases
  alter column journey_category drop not null;

-- Phase-1 cases are all available from day one.
update public.cases
set released_on = coalesce(released_on, created_at::date)
where phase_no = 1
  and released_on is null;

create index if not exists cases_trainee_phase_idx
  on public.cases (trainee_id, phase_no, released_on);

-- 3. Phase-2 anchor on the trainee -------------------------------------------

alter table public.trainees
  add column if not exists phase_2_started_on date;

-- 4. Phase-2 template rows ----------------------------------------------------
-- case_no 1..30, five per release day. For phase 2, training_day is the release
-- offset in working days from phase_2_started_on (not from trainees.start_date).
-- catalog_label L01..L30; order_number is backfilled once the real VIP numbers
-- are known.

insert into public.case_schedule_template (
  phase_no, set_no, case_no, training_day, catalog_label,
  order_number, journey_category
)
select
  2,
  1,
  case_no,
  ((case_no - 1) / 5) + 1,
  'L' || lpad(case_no::text, 2, '0'),
  null,
  null
from generate_series(1, 30) as cases(case_no)
on conflict (phase_no, set_no, case_no) do nothing;

-- 5. New trainees still start with phase 1 only -------------------------------

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
    journey_category,
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
    template.journey_category,
    template.training_day,
    private.training_date(new.start_date, template.training_day),
    private.training_date(new.start_date, template.training_day),
    new.start_date
  from public.case_schedule_template as template
  where template.phase_no = 1;
  return new;
end;
$$;

-- 6. Starting phase 2 ---------------------------------------------------------

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
    journey_category,
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
    template.journey_category,
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

-- 7. Automatic entry into phase 2 --------------------------------------------
-- Fires on any path that approves a case, not just publish_case_review.

create or replace function private.maybe_start_phase_2()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  phase_1_open integer;
  already_started date;
begin
  if new.phase_no <> 1 or new.status <> 'approved' then
    return new;
  end if;

  select phase_2_started_on into already_started
  from public.trainees
  where id = new.trainee_id;

  if already_started is not null then
    return new;
  end if;

  select count(*) into phase_1_open
  from public.cases
  where trainee_id = new.trainee_id
    and phase_no = 1
    and status <> 'approved';

  if phase_1_open = 0 then
    perform private.start_phase_2(new.trainee_id, current_date);
  end if;

  return new;
end;
$$;

drop trigger if exists on_case_approved_start_phase_2 on public.cases;

create trigger on_case_approved_start_phase_2
after update of status on public.cases
for each row
when (new.status = 'approved' and old.status is distinct from new.status)
execute function private.maybe_start_phase_2();

-- 8. Phase-aware progress view ------------------------------------------------
-- Existing columns keep their meaning across both phases. Unreleased phase-2
-- cases never count as overdue and never appear as waiting on the trainee.

drop view if exists public.trainee_progress;

create view public.trainee_progress
with (security_invoker = true)
as
select
  trainee.id as trainee_id,
  trainee.full_name,
  trainee.current_phase,
  trainee.is_test,
  trainee.phase_2_started_on,
  count(distinct cases.id) as total_cases,
  count(distinct cases.id) filter (where cases.status = 'approved') as approved_cases,
  count(distinct cases.id) filter (where cases.phase_no = 1) as phase_1_cases,
  count(distinct cases.id) filter (
    where cases.phase_no = 1 and cases.status = 'approved'
  ) as phase_1_approved,
  count(distinct cases.id) filter (where cases.phase_no = 2) as phase_2_cases,
  count(distinct cases.id) filter (
    where cases.phase_no = 2 and cases.status = 'approved'
  ) as phase_2_approved,
  count(distinct cases.id) filter (
    where cases.phase_no = 2 and cases.released_on > current_date
  ) as phase_2_unreleased,
  count(distinct cases.id) filter (
    where cases.status <> 'approved'
      and cases.due_date < current_date
      and coalesce(cases.released_on, current_date) <= current_date
  ) as overdue_cases,
  count(distinct cases.id) filter (
    where cases.status in ('in_review', 'corrections_sent')
  ) as waiting_on_trainer,
  count(requirements.id) filter (
    where requirements.status in ('missing', 'replacement_requested')
      and cases.status in ('assigned', 'submitted', 'awaiting_resubmission')
      and coalesce(cases.released_on, current_date) <= current_date
  ) as waiting_on_trainee,
  count(requirements.id) as total_files,
  count(requirements.id) filter (
    where requirements.status = 'accepted'
  ) as accepted_files,
  max(cases.estimated_completion_date) filter (
    where cases.status <> 'approved'
  ) as estimated_completion_date
from public.trainees as trainee
left join public.cases on cases.trainee_id = trainee.id
left join public.file_requirements as requirements on requirements.case_id = cases.id
group by trainee.id;

grant select on public.trainee_progress to authenticated;
