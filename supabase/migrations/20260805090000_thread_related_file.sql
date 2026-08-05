-- Feature 5.3: optional file tag on correction threads.

alter table public.corrections_threads
  add column if not exists related_file text
  check (related_file is null or related_file in ('pdf1', 'pdf2', 'ov'));

-- Recreate create_correction_thread with an optional related_file argument.
-- Drop both old (4-arg) and new signatures first so recreate is clean.
drop function if exists public.create_correction_thread(uuid, text, text, uuid);
drop function if exists public.create_correction_thread(uuid, text, text, uuid, text);

create or replace function public.create_correction_thread(
  target_case_id uuid,
  target_section text,
  thread_body text,
  target_revision_id uuid,
  target_related_file text default null
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

  if target_related_file is not null
     and target_related_file not in ('pdf1', 'pdf2', 'ov') then
    raise exception 'related_file must be pdf1, pdf2, ov, or null';
  end if;

  insert into public.corrections_threads (case_id, section, related_file)
  values (target_case_id, target_section, target_related_file)
  returning id into new_thread_id;

  insert into public.correction_events (thread_id, revision_id, event_type, body)
  values (new_thread_id, target_revision_id, 'raised', trim(thread_body));

  return new_thread_id;
end;
$$;

revoke all on function public.create_correction_thread(uuid, text, text, uuid, text)
  from public, anon;
grant execute on function public.create_correction_thread(uuid, text, text, uuid, text)
  to authenticated;
