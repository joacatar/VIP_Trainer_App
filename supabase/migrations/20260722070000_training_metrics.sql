-- Milestone 5: event-derived training metrics views.
-- Also emit homework_assigned so assignment timestamps stay in the event stream.

create or replace function public.assign_homework(
  target_case_id uuid,
  homework_title text,
  homework_instructions text,
  scheduled_due date,
  assigned_due date
)
returns uuid
language plpgsql
security invoker
set search_path = ''
as $$
declare
  assignment_id uuid;
  case_row public.cases%rowtype;
begin
  if length(trim(homework_title)) = 0 then
    raise exception 'Homework title is required';
  end if;

  select * into case_row
  from public.cases
  where id = target_case_id
  for update;

  if not found then
    raise exception 'Case not found';
  end if;

  insert into public.homework_assignments (
    case_id,
    assigned_by,
    title,
    instructions,
    status,
    schedule_due_date,
    due_date,
    estimated_due_date,
    sent_at
  )
  values (
    target_case_id,
    (select auth.uid()),
    trim(homework_title),
    nullif(trim(homework_instructions), ''),
    'sent',
    scheduled_due,
    assigned_due,
    assigned_due,
    now()
  )
  returning id into assignment_id;

  update public.cases
  set status = 'assigned',
      due_date = assigned_due,
      estimated_completion_date = assigned_due
  where id = target_case_id;

  insert into public.tracking_events (
    trainee_id, case_id, actor_user_id, event_type, event_data
  )
  values (
    case_row.trainee_id,
    target_case_id,
    (select auth.uid()),
    'homework_assigned',
    jsonb_build_object(
      'assignment_id', assignment_id,
      'due_date', assigned_due
    )
  );

  return assignment_id;
end;
$$;

create or replace view public.case_training_metrics
with (security_invoker = true)
as
select
  cases.id as case_id,
  cases.trainee_id,
  trainees.full_name as trainee_name,
  cases.set_no,
  cases.case_no,
  cases.status::text as status,
  cases.schedule_due_date,
  cases.due_date,
  cases.approved_at,
  homework.sent_at as assigned_at,
  (
    select min(e.occurred_at)
    from public.tracking_events as e
    where e.case_id = cases.id
      and e.event_type = 'case_submitted_for_review'
  ) as first_submitted_at,
  (
    select count(*)::integer
    from public.tracking_events as e
    where e.case_id = cases.id
      and e.event_type = 'case_submitted_for_review'
  ) as submit_count,
  (
    select count(*)::integer
    from public.tracking_events as e
    where e.case_id = cases.id
      and e.event_type = 'revision_published'
  ) as revision_publish_count,
  (
    select count(*)::integer
    from public.tracking_events as e
    where e.case_id = cases.id
      and e.event_type = 'file_requirement_reviewed'
      and coalesce(e.event_data ->> 'decision', '') = 'rejected'
  ) as replacement_request_count,
  (
    select min(e.occurred_at)
    from public.tracking_events as e
    where e.case_id = cases.id
      and e.event_type in (
        'revision_published',
        'case_review_published',
        'case_approved'
      )
  ) as first_trainer_response_at
from public.cases
join public.trainees on trainees.id = cases.trainee_id
left join lateral (
  select homework_assignments.sent_at
  from public.homework_assignments
  where homework_assignments.case_id = cases.id
    and homework_assignments.status <> 'cancelled'
  order by homework_assignments.created_at
  limit 1
) as homework on true;

create or replace view public.correction_section_stats
with (security_invoker = true)
as
select
  revision_sections.section_key::text as section_key,
  count(*)::integer as correction_count,
  count(*) filter (
    where corrections.status = 'open'
  )::integer as open_count,
  count(*) filter (
    where corrections.rolled_from_correction_id is not null
  )::integer as rolled_forward_count
from public.corrections
join public.revision_sections
  on revision_sections.id = corrections.section_id
join public.revisions
  on revisions.id = revision_sections.revision_id
where revisions.status = 'published'
group by revision_sections.section_key;

grant select on public.case_training_metrics to authenticated;
grant select on public.correction_section_stats to authenticated;
