-- Package-level submit for review: unlock revisions without per-file accept.

create or replace function private.refresh_case_file_status(target_case_id uuid)
returns void
language plpgsql
security definer
set search_path = ''
as $$
declare
  open_replacements integer;
  ready_count integer;
begin
  select
    count(*) filter (where status = 'replacement_requested'),
    count(*) filter (where status in ('submitted', 'under_review', 'accepted'))
  into open_replacements, ready_count
  from public.file_requirements
  where case_id = target_case_id;

  if open_replacements > 0 then
    update public.cases
    set status = 'awaiting_resubmission'
    where id = target_case_id
      and status not in ('approved', 'blocked');
  elsif ready_count = 0 then
    -- Cleared slots after unmark / send-back cleanup.
    update public.cases
    set status = 'assigned'
    where id = target_case_id
      and status in ('submitted', 'awaiting_resubmission');
  end if;
  -- in_review is owned by submit_case_for_review, not by accept-all / mark-sent.
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

  if case_row.status in ('in_review', 'corrections_sent') then
    raise exception 'Package is with the trainer — wait for send-back before editing';
  end if;

  if case_row.status not in ('assigned', 'submitted', 'awaiting_resubmission') then
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

  if case_row.status in ('in_review', 'corrections_sent') then
    raise exception 'Package is with the trainer — wait for send-back before editing';
  end if;

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

create or replace function public.submit_case_for_review(target_case_id uuid)
returns void
language plpgsql
security definer
set search_path = ''
as $$
declare
  case_row public.cases%rowtype;
  ready_count integer;
  open_replacements integer;
begin
  select * into case_row
  from public.cases
  where id = target_case_id
  for update;

  if not found then
    raise exception 'Case not found';
  end if;

  if not (
    private.is_trainer()
    or private.owns_trainee(case_row.trainee_id)
  ) then
    raise exception 'Not allowed to submit this case for review';
  end if;

  if case_row.status not in ('assigned', 'submitted', 'awaiting_resubmission') then
    raise exception 'Case cannot be submitted for review from status %', case_row.status;
  end if;

  select
    count(*) filter (where status in ('submitted', 'under_review')),
    count(*) filter (where status = 'replacement_requested')
  into ready_count, open_replacements
  from public.file_requirements
  where case_id = target_case_id;

  if open_replacements > 0 then
    raise exception 'Resolve replacement requests before submitting the package';
  end if;

  if ready_count < 3 then
    raise exception 'Mark all three file slots as sent before notifying the trainer';
  end if;

  update public.file_requirements
  set status = 'under_review'
  where case_id = target_case_id
    and status in ('submitted', 'under_review');

  update public.cases
  set status = 'in_review'
  where id = target_case_id;

  insert into public.tracking_events (
    trainee_id, case_id, actor_user_id, event_type, event_data
  )
  values (
    case_row.trainee_id,
    case_row.id,
    (select auth.uid()),
    'case_submitted_for_review',
    jsonb_build_object('case_id', target_case_id)
  );
end;
$$;

revoke all on function public.submit_case_for_review(uuid) from public, anon;
grant execute on function public.submit_case_for_review(uuid) to authenticated;

-- Waiting indicators: package-level for trainer; file-level to-send for trainee.
drop view if exists public.trainee_progress;

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
  count(distinct cases.id) filter (
    where cases.status in ('in_review', 'corrections_sent')
  ) as waiting_on_trainer,
  count(requirements.id) filter (
    where requirements.status in ('missing', 'replacement_requested')
      and cases.status in ('assigned', 'submitted', 'awaiting_resubmission')
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
