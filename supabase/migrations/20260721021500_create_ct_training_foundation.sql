-- CT initial-training tracker foundation.
-- Roles are stored in public.profiles and protected by RLS. New users default
-- to trainee; promote the first trainer through the Supabase SQL editor.

create schema if not exists private;

create type public.app_role as enum ('trainer', 'trainee');
create type public.training_phase as enum ('ct_disposition', 'ct_planning');
create type public.case_status as enum (
  'not_started',
  'assigned',
  'submitted',
  'in_review',
  'corrections_sent',
  'awaiting_resubmission',
  'approved',
  'blocked'
);
create type public.file_kind as enum ('pdf_primary', 'pdf_secondary', 'ov');
create type public.file_requirement_status as enum (
  'missing',
  'submitted',
  'under_review',
  'replacement_requested',
  'accepted'
);
create type public.file_review_status as enum (
  'submitted',
  'accepted',
  'rejected',
  'superseded'
);
create type public.assignment_status as enum (
  'draft',
  'sent',
  'submitted',
  'completed',
  'cancelled'
);

create table public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  role public.app_role not null default 'trainee',
  full_name text not null default '',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.holidays (
  holiday_date date primary key,
  reason text not null,
  created_at timestamptz not null default now()
);

create table public.case_schedule_template (
  set_no smallint not null check (set_no between 1 and 2),
  case_no smallint not null check (case_no between 1 and 16),
  training_day smallint not null check (training_day >= 0),
  primary key (set_no, case_no)
);

insert into public.case_schedule_template (set_no, case_no, training_day)
select
  set_no,
  case_no,
  case
    when set_no = 1 and case_no between 1 and 2 then 5
    when set_no = 1 and case_no between 3 and 4 then 6
    when set_no = 1 and case_no between 5 and 8 then 7
    when set_no = 1 and case_no between 9 and 13 then 8
    when set_no = 1 and case_no between 14 and 16 then 9
    when set_no = 2 and case_no between 1 and 2 then 10
    when set_no = 2 and case_no between 3 and 4 then 11
    when set_no = 2 and case_no between 5 and 8 then 12
    when set_no = 2 and case_no between 9 and 13 then 13
    else 14
  end
from generate_series(1, 2) as sets(set_no)
cross join generate_series(1, 16) as cases(case_no);

create table public.trainees (
  id uuid primary key default gen_random_uuid(),
  auth_user_id uuid unique references auth.users(id) on delete set null,
  full_name text not null,
  email text,
  timezone text not null default 'Australia/Sydney',
  start_date date not null,
  current_phase public.training_phase not null default 'ct_disposition',
  active boolean not null default true,
  created_by uuid references auth.users(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.cases (
  id uuid primary key default gen_random_uuid(),
  trainee_id uuid not null references public.trainees(id) on delete cascade,
  phase public.training_phase not null default 'ct_planning',
  set_no smallint not null check (set_no between 1 and 2),
  case_no smallint not null check (case_no between 1 and 16),
  scheduled_training_day smallint not null check (scheduled_training_day >= 0),
  schedule_due_date date not null,
  due_date date not null,
  estimated_completion_date date,
  status public.case_status not null default 'not_started',
  approved_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (trainee_id, set_no, case_no)
);

create index cases_trainee_status_idx on public.cases (trainee_id, status);
create index cases_due_date_open_idx
  on public.cases (due_date)
  where status <> 'approved';

create table public.file_requirements (
  id uuid primary key default gen_random_uuid(),
  case_id uuid not null references public.cases(id) on delete cascade,
  kind public.file_kind not null,
  status public.file_requirement_status not null default 'missing',
  replacement_reason text,
  accepted_at timestamptz,
  updated_at timestamptz not null default now(),
  unique (case_id, kind)
);

create index file_requirements_case_status_idx
  on public.file_requirements (case_id, status);

create table public.case_files (
  id uuid primary key default gen_random_uuid(),
  requirement_id uuid not null references public.file_requirements(id) on delete cascade,
  version_no integer not null check (version_no > 0),
  storage_path text not null unique,
  original_filename text not null,
  mime_type text,
  size_bytes bigint check (size_bytes is null or size_bytes >= 0),
  sha256 text,
  uploaded_by uuid not null references auth.users(id) on delete restrict,
  review_status public.file_review_status not null default 'submitted',
  review_note text,
  reviewed_by uuid references auth.users(id) on delete set null,
  uploaded_at timestamptz not null default now(),
  reviewed_at timestamptz,
  unique (requirement_id, version_no)
);

create unique index one_accepted_file_per_requirement_idx
  on public.case_files (requirement_id)
  where review_status = 'accepted';

create table public.homework_assignments (
  id uuid primary key default gen_random_uuid(),
  case_id uuid not null references public.cases(id) on delete cascade,
  assigned_by uuid references auth.users(id) on delete set null,
  title text not null,
  instructions text,
  status public.assignment_status not null default 'draft',
  schedule_due_date date not null,
  due_date date not null,
  estimated_due_date date,
  sent_at timestamptz,
  submitted_at timestamptz,
  completed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index homework_due_open_idx
  on public.homework_assignments (due_date, status)
  where status not in ('completed', 'cancelled');

create table public.tracking_events (
  id bigint generated always as identity primary key,
  trainee_id uuid references public.trainees(id) on delete cascade,
  case_id uuid references public.cases(id) on delete cascade,
  actor_user_id uuid references auth.users(id) on delete set null,
  event_type text not null,
  event_data jsonb not null default '{}'::jsonb,
  occurred_at timestamptz not null default now()
);

create index tracking_events_trainee_time_idx
  on public.tracking_events (trainee_id, occurred_at desc);
create index tracking_events_case_time_idx
  on public.tracking_events (case_id, occurred_at desc);

create or replace function private.set_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create trigger profiles_set_updated_at
before update on public.profiles
for each row execute function private.set_updated_at();

create trigger trainees_set_updated_at
before update on public.trainees
for each row execute function private.set_updated_at();

create trigger cases_set_updated_at
before update on public.cases
for each row execute function private.set_updated_at();

create trigger requirements_set_updated_at
before update on public.file_requirements
for each row execute function private.set_updated_at();

create trigger assignments_set_updated_at
before update on public.homework_assignments
for each row execute function private.set_updated_at();

create or replace function private.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  insert into public.profiles (id, full_name)
  values (new.id, coalesce(new.raw_user_meta_data ->> 'full_name', ''));
  return new;
end;
$$;

create trigger on_auth_user_created
after insert on auth.users
for each row execute function private.handle_new_user();

create or replace function private.is_trainer()
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1
    from public.profiles
    where id = (select auth.uid())
      and role = 'trainer'
  );
$$;

create or replace function private.owns_trainee(target_trainee_id uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1
    from public.trainees
    where id = target_trainee_id
      and auth_user_id = (select auth.uid())
  );
$$;

create or replace function private.training_date(
  training_start date,
  day_offset integer
)
returns date
language plpgsql
stable
security definer
set search_path = ''
as $$
declare
  result_date date := training_start;
  workdays integer := 0;
begin
  while workdays < day_offset loop
    result_date := result_date + 1;
    if extract(isodow from result_date) < 6
       and not exists (
         select 1
         from public.holidays
         where holiday_date = result_date
       ) then
      workdays := workdays + 1;
    end if;
  end loop;
  return result_date;
end;
$$;

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
    set_no,
    case_no,
    scheduled_training_day,
    schedule_due_date,
    due_date
  )
  select
    new.id,
    'ct_planning'::public.training_phase,
    template.set_no,
    template.case_no,
    template.training_day,
    private.training_date(new.start_date, template.training_day),
    private.training_date(new.start_date, template.training_day)
  from public.case_schedule_template as template;
  return new;
end;
$$;

create trigger on_trainee_created
after insert on public.trainees
for each row execute function private.create_trainee_cases();

create or replace function private.create_case_file_requirements()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  insert into public.file_requirements (case_id, kind)
  values
    (new.id, 'pdf_primary'::public.file_kind),
    (new.id, 'pdf_secondary'::public.file_kind),
    (new.id, 'ov'::public.file_kind);
  return new;
end;
$$;

create trigger on_case_created
after insert on public.cases
for each row execute function private.create_case_file_requirements();

revoke all on schema private from public;
revoke execute on all functions in schema private from public;
grant usage on schema private to authenticated;
grant execute on function private.is_trainer() to authenticated;
grant execute on function private.owns_trainee(uuid) to authenticated;

grant select, insert, update, delete
  on public.profiles,
     public.holidays,
     public.case_schedule_template,
     public.trainees,
     public.cases,
     public.file_requirements,
     public.case_files,
     public.homework_assignments,
     public.tracking_events
  to authenticated;
grant usage, select on sequence public.tracking_events_id_seq to authenticated;

alter table public.profiles enable row level security;
alter table public.holidays enable row level security;
alter table public.case_schedule_template enable row level security;
alter table public.trainees enable row level security;
alter table public.cases enable row level security;
alter table public.file_requirements enable row level security;
alter table public.case_files enable row level security;
alter table public.homework_assignments enable row level security;
alter table public.tracking_events enable row level security;

create policy "profiles_read_self_or_trainer"
on public.profiles for select to authenticated
using (id = (select auth.uid()) or private.is_trainer());

create policy "profiles_trainers_update"
on public.profiles for update to authenticated
using (private.is_trainer())
with check (private.is_trainer());

create policy "holidays_authenticated_read"
on public.holidays for select to authenticated
using (true);

create policy "holidays_trainers_manage"
on public.holidays for all to authenticated
using (private.is_trainer())
with check (private.is_trainer());

create policy "schedule_authenticated_read"
on public.case_schedule_template for select to authenticated
using (true);

create policy "schedule_trainers_manage"
on public.case_schedule_template for all to authenticated
using (private.is_trainer())
with check (private.is_trainer());

create policy "trainees_read_self_or_trainer"
on public.trainees for select to authenticated
using (auth_user_id = (select auth.uid()) or private.is_trainer());

create policy "trainees_trainers_manage"
on public.trainees for all to authenticated
using (private.is_trainer())
with check (private.is_trainer());

create policy "cases_read_owner_or_trainer"
on public.cases for select to authenticated
using (private.owns_trainee(trainee_id) or private.is_trainer());

create policy "cases_trainers_manage"
on public.cases for all to authenticated
using (private.is_trainer())
with check (private.is_trainer());

create policy "requirements_read_owner_or_trainer"
on public.file_requirements for select to authenticated
using (
  private.is_trainer()
  or exists (
    select 1
    from public.cases
    where cases.id = file_requirements.case_id
      and private.owns_trainee(cases.trainee_id)
  )
);

create policy "requirements_trainers_manage"
on public.file_requirements for all to authenticated
using (private.is_trainer())
with check (private.is_trainer());

create policy "case_files_read_owner_or_trainer"
on public.case_files for select to authenticated
using (
  private.is_trainer()
  or exists (
    select 1
    from public.file_requirements
    join public.cases on cases.id = file_requirements.case_id
    where file_requirements.id = case_files.requirement_id
      and private.owns_trainee(cases.trainee_id)
  )
);

create policy "case_files_trainees_submit"
on public.case_files for insert to authenticated
with check (
  uploaded_by = (select auth.uid())
  and review_status = 'submitted'
  and exists (
    select 1
    from public.file_requirements
    join public.cases on cases.id = file_requirements.case_id
    where file_requirements.id = case_files.requirement_id
      and file_requirements.status <> 'accepted'
      and private.owns_trainee(cases.trainee_id)
  )
);

create policy "case_files_trainers_manage"
on public.case_files for all to authenticated
using (private.is_trainer())
with check (private.is_trainer());

create policy "assignments_read_owner_or_trainer"
on public.homework_assignments for select to authenticated
using (
  private.is_trainer()
  or exists (
    select 1
    from public.cases
    where cases.id = homework_assignments.case_id
      and private.owns_trainee(cases.trainee_id)
  )
);

create policy "assignments_trainers_manage"
on public.homework_assignments for all to authenticated
using (private.is_trainer())
with check (private.is_trainer());

create policy "events_read_owner_or_trainer"
on public.tracking_events for select to authenticated
using (
  private.is_trainer()
  or (trainee_id is not null and private.owns_trainee(trainee_id))
);

create policy "events_insert_as_actor"
on public.tracking_events for insert to authenticated
with check (
  actor_user_id = (select auth.uid())
  and (
    private.is_trainer()
    or (trainee_id is not null and private.owns_trainee(trainee_id))
  )
);

create view public.trainee_progress
with (security_invoker = true)
as
select
  trainee.id as trainee_id,
  trainee.full_name,
  trainee.current_phase,
  count(distinct cases.id) as total_cases,
  count(distinct cases.id) filter (where cases.status = 'approved') as approved_cases,
  count(distinct cases.id) filter (
    where cases.status <> 'approved' and cases.due_date < current_date
  ) as overdue_cases,
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

insert into storage.buckets (id, name, public)
values ('case-files', 'case-files', false)
on conflict (id) do update set public = false;

create policy "case_files_storage_read"
on storage.objects for select to authenticated
using (
  bucket_id = 'case-files'
  and (
    private.is_trainer()
    or (storage.foldername(name))[1] = (select auth.uid())::text
  )
);

create policy "case_files_storage_insert"
on storage.objects for insert to authenticated
with check (
  bucket_id = 'case-files'
  and (storage.foldername(name))[1] = (select auth.uid())::text
);

create policy "case_files_storage_trainers_manage"
on storage.objects for all to authenticated
using (bucket_id = 'case-files' and private.is_trainer())
with check (bucket_id = 'case-files' and private.is_trainer());
