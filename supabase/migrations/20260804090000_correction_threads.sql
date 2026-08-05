-- Feature 2 (v2): thread-based corrections model.
-- One thread per issue with a status; revision touchpoints are timeline
-- events under the thread. Lives alongside the existing per-revision
-- corrections tables; nothing is dropped or altered here.

create table public.corrections_threads (
  id uuid primary key default gen_random_uuid(),
  case_id uuid not null references public.cases(id) on delete cascade,
  section text not null check (
    section in (
      'scan',
      'rider_form',
      'segmentation',
      'scapula',
      'glenoid_landmark',
      'humeral_landmark',
      'humeral_implant',
      'glenoid_implant'
    )
  ),
  status text not null default 'open' check (status in ('open', 'resolved')),
  created_at timestamptz not null default now(),
  resolved_at timestamptz,
  resolved_in_revision_id uuid references public.revisions(id) on delete set null
);

create table public.correction_events (
  id uuid primary key default gen_random_uuid(),
  thread_id uuid not null references public.corrections_threads(id) on delete cascade,
  revision_id uuid references public.revisions(id) on delete set null,
  event_type text not null check (
    event_type in ('raised', 'still_open', 'resolved', 'note')
  ),
  body text,
  created_at timestamptz not null default now()
);

-- Screenshots pasted on a thread (mirrors correction_screenshots without
-- touching the legacy table).
create table public.correction_thread_screenshots (
  id uuid primary key default gen_random_uuid(),
  thread_id uuid not null references public.corrections_threads(id) on delete cascade,
  storage_path text not null,
  original_filename text not null,
  mime_type text,
  size_bytes bigint,
  uploaded_by uuid references auth.users(id) on delete set null,
  created_at timestamptz not null default now()
);

create index corrections_threads_case_status_idx
  on public.corrections_threads (case_id, status);

create index correction_events_thread_idx
  on public.correction_events (thread_id);

create index correction_thread_screenshots_thread_idx
  on public.correction_thread_screenshots (thread_id);

alter table public.corrections_threads enable row level security;
alter table public.correction_events enable row level security;
alter table public.correction_thread_screenshots enable row level security;

-- Trainers manage everything; trainees read threads for their own cases once
-- the thread has touched a published revision (draft-only feedback stays
-- hidden, matching the legacy corrections policies).
create policy "corrections_threads_trainers_manage"
on public.corrections_threads for all to authenticated
using (private.is_trainer())
with check (private.is_trainer());

create policy "corrections_threads_trainees_read_published"
on public.corrections_threads for select to authenticated
using (
  private.trainee_owns_case(case_id)
  and exists (
    select 1
    from public.correction_events
    join public.revisions on revisions.id = correction_events.revision_id
    where correction_events.thread_id = corrections_threads.id
      and revisions.status = 'published'
  )
);

create policy "correction_events_trainers_manage"
on public.correction_events for all to authenticated
using (private.is_trainer())
with check (private.is_trainer());

create policy "correction_events_trainees_read_published"
on public.correction_events for select to authenticated
using (
  exists (
    select 1
    from public.corrections_threads
    where corrections_threads.id = correction_events.thread_id
      and private.trainee_owns_case(corrections_threads.case_id)
  )
  and (
    revision_id is null
    or exists (
      select 1
      from public.revisions
      where revisions.id = correction_events.revision_id
        and revisions.status = 'published'
    )
  )
);

create policy "correction_thread_screenshots_trainers_manage"
on public.correction_thread_screenshots for all to authenticated
using (private.is_trainer())
with check (private.is_trainer());

create policy "correction_thread_screenshots_trainees_read_published"
on public.correction_thread_screenshots for select to authenticated
using (
  exists (
    select 1
    from public.corrections_threads
    join public.correction_events
      on correction_events.thread_id = corrections_threads.id
    join public.revisions on revisions.id = correction_events.revision_id
    where corrections_threads.id = correction_thread_screenshots.thread_id
      and private.trainee_owns_case(corrections_threads.case_id)
      and revisions.status = 'published'
  )
);

grant select, insert, update, delete
  on public.corrections_threads,
     public.correction_events,
     public.correction_thread_screenshots
  to authenticated;

-- Atomic helpers so a thread and its first event (or a status change and its
-- event) can never drift apart.

create or replace function public.create_correction_thread(
  target_case_id uuid,
  target_section text,
  thread_body text,
  target_revision_id uuid
)
returns uuid
language plpgsql
security definer
set search_path = ''
as $$
declare
  new_thread_id uuid;
begin
  if not private.is_trainer() then
    raise exception 'Only trainers can add corrections';
  end if;

  if length(trim(thread_body)) = 0 then
    raise exception 'Correction body is required';
  end if;

  insert into public.corrections_threads (case_id, section)
  values (target_case_id, target_section)
  returning id into new_thread_id;

  insert into public.correction_events (thread_id, revision_id, event_type, body)
  values (new_thread_id, target_revision_id, 'raised', trim(thread_body));

  return new_thread_id;
end;
$$;

create or replace function public.resolve_correction_thread(
  target_thread_id uuid,
  target_revision_id uuid
)
returns void
language plpgsql
security definer
set search_path = ''
as $$
begin
  if not private.is_trainer() then
    raise exception 'Only trainers can resolve corrections';
  end if;

  update public.corrections_threads
  set status = 'resolved',
      resolved_at = now(),
      resolved_in_revision_id = target_revision_id
  where id = target_thread_id;

  if not found then
    raise exception 'Thread not found';
  end if;

  insert into public.correction_events (thread_id, revision_id, event_type)
  values (target_thread_id, target_revision_id, 'resolved');
end;
$$;

create or replace function public.reopen_correction_thread(
  target_thread_id uuid,
  target_revision_id uuid
)
returns void
language plpgsql
security definer
set search_path = ''
as $$
begin
  if not private.is_trainer() then
    raise exception 'Only trainers can reopen corrections';
  end if;

  update public.corrections_threads
  set status = 'open',
      resolved_at = null,
      resolved_in_revision_id = null
  where id = target_thread_id;

  if not found then
    raise exception 'Thread not found';
  end if;

  insert into public.correction_events (thread_id, revision_id, event_type)
  values (target_thread_id, target_revision_id, 'still_open');
end;
$$;

-- Called when a review is published while threads remain open: stamps each
-- open thread with a 'still_open' event on that revision (once per revision).
create or replace function public.mark_open_threads_still_open(
  target_case_id uuid,
  target_revision_id uuid
)
returns integer
language plpgsql
security definer
set search_path = ''
as $$
declare
  stamped integer;
begin
  if not private.is_trainer() then
    raise exception 'Only trainers can update corrections';
  end if;

  insert into public.correction_events (thread_id, revision_id, event_type)
  select threads.id, target_revision_id, 'still_open'
  from public.corrections_threads as threads
  where threads.case_id = target_case_id
    and threads.status = 'open'
    and not exists (
      select 1
      from public.correction_events as events
      where events.thread_id = threads.id
        and events.revision_id = target_revision_id
    );

  get diagnostics stamped = row_count;
  return stamped;
end;
$$;

revoke all on function public.create_correction_thread(uuid, text, text, uuid)
  from public, anon;
revoke all on function public.resolve_correction_thread(uuid, uuid)
  from public, anon;
revoke all on function public.reopen_correction_thread(uuid, uuid)
  from public, anon;
revoke all on function public.mark_open_threads_still_open(uuid, uuid)
  from public, anon;

grant execute on function public.create_correction_thread(uuid, text, text, uuid)
  to authenticated;
grant execute on function public.resolve_correction_thread(uuid, uuid)
  to authenticated;
grant execute on function public.reopen_correction_thread(uuid, uuid)
  to authenticated;
grant execute on function public.mark_open_threads_still_open(uuid, uuid)
  to authenticated;
