-- Feature 4 (v2): per-case resources (files, links, notes) for trainees.

create table public.case_resources (
  id uuid primary key default gen_random_uuid(),
  case_id uuid not null references public.cases(id) on delete cascade,
  resource_type text not null check (resource_type in ('file', 'link', 'note')),
  title text not null check (length(trim(title)) > 0),
  url text,
  body text,
  created_by text not null check (created_by in ('system', 'trainer')),
  sort_order integer not null default 0,
  created_at timestamptz not null default now()
);

create index case_resources_case_idx
  on public.case_resources (case_id, sort_order);

alter table public.case_resources enable row level security;

-- Trainers manage everything; trainees read resources for their own cases.
create policy "case_resources_trainers_manage"
on public.case_resources for all to authenticated
using (private.is_trainer())
with check (private.is_trainer());

create policy "case_resources_trainees_read_own"
on public.case_resources for select to authenticated
using (private.trainee_owns_case(case_id));

grant select, insert, update, delete on public.case_resources to authenticated;
