-- Break RLS recursion between corrections_threads and correction_events.
-- The trainee SELECT policies previously queried each other under RLS, which
-- blew up on nested PostgREST selects (list_correction_threads).

create or replace function private.thread_case_id(target_thread_id uuid)
returns uuid
language sql
stable
security definer
set search_path = ''
as $$
  select case_id
  from public.corrections_threads
  where id = target_thread_id;
$$;

create or replace function private.thread_has_published_event(target_thread_id uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1
    from public.correction_events
    join public.revisions on revisions.id = correction_events.revision_id
    where correction_events.thread_id = target_thread_id
      and revisions.status = 'published'
  );
$$;

grant execute on function private.thread_case_id(uuid) to authenticated;
grant execute on function private.thread_has_published_event(uuid) to authenticated;

drop policy if exists "corrections_threads_trainees_read_published"
  on public.corrections_threads;
drop policy if exists "correction_events_trainees_read_published"
  on public.correction_events;
drop policy if exists "correction_thread_screenshots_trainees_read_published"
  on public.correction_thread_screenshots;

create policy "corrections_threads_trainees_read_published"
on public.corrections_threads for select to authenticated
using (
  private.trainee_owns_case(case_id)
  and private.thread_has_published_event(id)
);

create policy "correction_events_trainees_read_published"
on public.correction_events for select to authenticated
using (
  private.trainee_owns_case(private.thread_case_id(thread_id))
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

create policy "correction_thread_screenshots_trainees_read_published"
on public.correction_thread_screenshots for select to authenticated
using (
  private.trainee_owns_case(private.thread_case_id(thread_id))
  and private.thread_has_published_event(thread_id)
);
