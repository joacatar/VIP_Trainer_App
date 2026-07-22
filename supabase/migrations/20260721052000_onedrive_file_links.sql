-- Pivot case file slots from Storage uploads to OneDrive links + sent toggle.

alter table public.file_requirements
  add column if not exists external_url text;

comment on column public.file_requirements.external_url is
  'OneDrive (or other) share link for this file slot.';

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
  else
    -- All slots cleared / missing again after unmark.
    update public.cases
    set status = 'assigned'
    where id = target_case_id
      and status in ('submitted', 'awaiting_resubmission');
  end if;
end;
$$;

create or replace function public.mark_file_sent(
  target_requirement_id uuid,
  share_url text default null
)
returns void
language plpgsql
security definer
set search_path = ''
as $$
declare
  requirement_row public.file_requirements%rowtype;
  case_row public.cases%rowtype;
  cleaned_url text;
begin
  select * into requirement_row
  from public.file_requirements
  where id = target_requirement_id
  for update;

  if not found then
    raise exception 'File requirement not found';
  end if;

  if requirement_row.status = 'accepted' then
    raise exception 'Accepted files cannot be changed';
  end if;

  select * into case_row
  from public.cases
  where id = requirement_row.case_id;

  if not (
    private.is_trainer()
    or private.owns_trainee(case_row.trainee_id)
  ) then
    raise exception 'Not allowed to mark this file as sent';
  end if;

  if case_row.status not in (
    'assigned', 'submitted', 'awaiting_resubmission', 'in_review', 'corrections_sent'
  ) then
    raise exception 'Case is not ready for file submissions';
  end if;

  cleaned_url := nullif(trim(share_url), '');
  if cleaned_url is null then
    cleaned_url := requirement_row.external_url;
  end if;

  update public.file_requirements
  set status = 'submitted',
      external_url = cleaned_url
  where id = target_requirement_id;

  perform private.refresh_case_file_status(requirement_row.case_id);

  insert into public.tracking_events (
    trainee_id, case_id, actor_user_id, event_type, event_data
  )
  values (
    case_row.trainee_id,
    case_row.id,
    (select auth.uid()),
    'file_marked_sent',
    jsonb_build_object(
      'requirement_id', target_requirement_id,
      'kind', requirement_row.kind,
      'has_url', cleaned_url is not null
    )
  );
end;
$$;

create or replace function public.unmark_file_sent(target_requirement_id uuid)
returns void
language plpgsql
security definer
set search_path = ''
as $$
declare
  requirement_row public.file_requirements%rowtype;
  case_row public.cases%rowtype;
  next_status public.file_requirement_status;
begin
  select * into requirement_row
  from public.file_requirements
  where id = target_requirement_id
  for update;

  if not found then
    raise exception 'File requirement not found';
  end if;

  if requirement_row.status = 'accepted' then
    raise exception 'Accepted files cannot be unmarked';
  end if;

  if requirement_row.status not in ('submitted', 'under_review') then
    raise exception 'Only sent files can be unmarked';
  end if;

  select * into case_row
  from public.cases
  where id = requirement_row.case_id;

  if not (
    private.is_trainer()
    or private.owns_trainee(case_row.trainee_id)
  ) then
    raise exception 'Not allowed to unmark this file';
  end if;

  -- Keep URL for editing; restore replacement_requested when a note remains.
  if requirement_row.replacement_reason is not null then
    next_status := 'replacement_requested';
  else
    next_status := 'missing';
  end if;

  update public.file_requirements
  set status = next_status
  where id = target_requirement_id;

  perform private.refresh_case_file_status(requirement_row.case_id);

  insert into public.tracking_events (
    trainee_id, case_id, actor_user_id, event_type, event_data
  )
  values (
    case_row.trainee_id,
    case_row.id,
    (select auth.uid()),
    'file_unmarked_sent',
    jsonb_build_object(
      'requirement_id', target_requirement_id,
      'kind', requirement_row.kind,
      'next_status', next_status
    )
  );
end;
$$;

-- Allow trainers to clear replacement and set URL when reviewing via link.
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

create or replace function public.review_file_requirement(
  target_requirement_id uuid,
  decision text,
  decision_note text default null
)
returns void
language plpgsql
security definer
set search_path = ''
as $$
declare
  requirement_row public.file_requirements%rowtype;
begin
  if not private.is_trainer() then
    raise exception 'Only trainers can review files';
  end if;

  if decision not in ('accepted', 'rejected') then
    raise exception 'Decision must be accepted or rejected';
  end if;

  select * into requirement_row
  from public.file_requirements
  where id = target_requirement_id
  for update;

  if not found then
    raise exception 'File requirement not found';
  end if;

  if requirement_row.status not in ('submitted', 'under_review', 'replacement_requested')
     and not (decision = 'accepted' and requirement_row.status = 'accepted') then
    if requirement_row.status = 'missing' then
      raise exception 'Nothing sent to review yet';
    end if;
  end if;

  if decision = 'accepted' then
    update public.file_requirements
    set status = 'accepted',
        replacement_reason = null,
        accepted_at = now()
    where id = target_requirement_id;
  else
    update public.file_requirements
    set status = 'replacement_requested',
        replacement_reason = nullif(trim(decision_note), ''),
        accepted_at = null
    where id = target_requirement_id;
  end if;

  perform private.refresh_case_file_status(requirement_row.case_id);

  insert into public.tracking_events (
    trainee_id, case_id, actor_user_id, event_type, event_data
  )
  select
    cases.trainee_id,
    cases.id,
    (select auth.uid()),
    'file_requirement_reviewed',
    jsonb_build_object(
      'requirement_id', target_requirement_id,
      'kind', requirement_row.kind,
      'decision', decision
    )
  from public.cases
  where cases.id = requirement_row.case_id;
end;
$$;

revoke all on function public.mark_file_sent(uuid, text) from public, anon;
revoke all on function public.unmark_file_sent(uuid) from public, anon;
revoke all on function public.review_file_requirement(uuid, text, text)
  from public, anon;

grant execute on function public.mark_file_sent(uuid, text) to authenticated;
grant execute on function public.unmark_file_sent(uuid) to authenticated;
grant execute on function public.review_file_requirement(uuid, text, text)
  to authenticated;
