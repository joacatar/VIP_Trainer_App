-- Transactional case-file submit and review helpers.

create or replace function private.refresh_case_file_status(target_case_id uuid)
returns void
language plpgsql
security definer
set search_path = ''
as $$
declare
  accepted_count integer;
  open_replacements integer;
  submitted_count integer;
begin
  select
    count(*) filter (where status = 'accepted'),
    count(*) filter (where status = 'replacement_requested'),
    count(*) filter (
      where status in ('submitted', 'under_review', 'accepted')
    )
  into accepted_count, open_replacements, submitted_count
  from public.file_requirements
  where case_id = target_case_id;

  if open_replacements > 0 then
    update public.cases
    set status = 'awaiting_resubmission'
    where id = target_case_id
      and status not in ('approved', 'blocked');
  elsif accepted_count = 3 then
    update public.cases
    set status = 'in_review'
    where id = target_case_id
      and status not in ('approved', 'blocked', 'corrections_sent');
  elsif submitted_count > 0 then
    update public.cases
    set status = 'submitted'
    where id = target_case_id
      and status in ('assigned', 'awaiting_resubmission', 'submitted');
  end if;
end;
$$;

create or replace function public.register_case_file(
  target_requirement_id uuid,
  file_storage_path text,
  file_original_filename text,
  file_mime_type text,
  file_size_bytes bigint
)
returns uuid
language plpgsql
security definer
set search_path = ''
as $$
declare
  requirement_row public.file_requirements%rowtype;
  next_version integer;
  file_id uuid;
begin
  select *
  into requirement_row
  from public.file_requirements
  where id = target_requirement_id
  for update;

  if not found then
    raise exception 'File requirement not found';
  end if;

  if requirement_row.status = 'accepted' then
    raise exception 'Accepted files cannot be replaced';
  end if;

  if not (
    private.is_trainer()
    or exists (
      select 1
      from public.cases
      where cases.id = requirement_row.case_id
        and private.owns_trainee(cases.trainee_id)
    )
  ) then
    raise exception 'Not allowed to upload this file';
  end if;

  select coalesce(max(version_no), 0) + 1
  into next_version
  from public.case_files
  where requirement_id = target_requirement_id;

  update public.case_files
  set review_status = 'superseded'
  where requirement_id = target_requirement_id
    and review_status = 'submitted';

  insert into public.case_files (
    requirement_id,
    version_no,
    storage_path,
    original_filename,
    mime_type,
    size_bytes,
    uploaded_by,
    review_status
  )
  values (
    target_requirement_id,
    next_version,
    file_storage_path,
    file_original_filename,
    file_mime_type,
    file_size_bytes,
    (select auth.uid()),
    'submitted'
  )
  returning id into file_id;

  update public.file_requirements
  set status = 'submitted',
      replacement_reason = null
  where id = target_requirement_id;

  perform private.refresh_case_file_status(requirement_row.case_id);
  return file_id;
end;
$$;

create or replace function public.review_case_file(
  target_file_id uuid,
  decision text,
  decision_note text default null
)
returns void
language plpgsql
security definer
set search_path = ''
as $$
declare
  file_row public.case_files%rowtype;
  requirement_row public.file_requirements%rowtype;
begin
  if not private.is_trainer() then
    raise exception 'Only trainers can review files';
  end if;

  if decision not in ('accepted', 'rejected') then
    raise exception 'Decision must be accepted or rejected';
  end if;

  select *
  into file_row
  from public.case_files
  where id = target_file_id
  for update;

  if not found then
    raise exception 'File version not found';
  end if;

  select *
  into requirement_row
  from public.file_requirements
  where id = file_row.requirement_id
  for update;

  if decision = 'accepted' then
    update public.case_files
    set review_status = 'superseded'
    where requirement_id = file_row.requirement_id
      and id <> target_file_id
      and review_status = 'accepted';

    update public.case_files
    set review_status = 'accepted',
        review_note = nullif(trim(decision_note), ''),
        reviewed_by = (select auth.uid()),
        reviewed_at = now()
    where id = target_file_id;

    update public.file_requirements
    set status = 'accepted',
        replacement_reason = null,
        accepted_at = now()
    where id = requirement_row.id;
  else
    update public.case_files
    set review_status = 'rejected',
        review_note = nullif(trim(decision_note), ''),
        reviewed_by = (select auth.uid()),
        reviewed_at = now()
    where id = target_file_id;

    update public.file_requirements
    set status = 'replacement_requested',
        replacement_reason = nullif(trim(decision_note), ''),
        accepted_at = null
    where id = requirement_row.id;
  end if;

  perform private.refresh_case_file_status(requirement_row.case_id);
end;
$$;

revoke all on function private.refresh_case_file_status(uuid) from public;
revoke all on function public.register_case_file(uuid, text, text, text, bigint)
  from public, anon;
revoke all on function public.review_case_file(uuid, text, text)
  from public, anon;
grant execute on function public.register_case_file(uuid, text, text, text, bigint)
  to authenticated;
grant execute on function public.review_case_file(uuid, text, text)
  to authenticated;
