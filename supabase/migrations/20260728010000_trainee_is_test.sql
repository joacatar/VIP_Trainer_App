-- Tag practice trainees so they can be hidden from the main trainer dashboard.

alter table public.trainees
  add column if not exists is_test boolean not null default false;

update public.trainees
set is_test = true
where lower(full_name) in (lower('JOAO T'), lower('Joao Tarira'))
   or lower(coalesce(email, '')) in (
     lower('Joao.TariraBarroso@arthrex.com'),
     lower('biovidassan@gmail.com')
   );

drop view if exists public.trainee_progress;

create view public.trainee_progress
with (security_invoker = true)
as
select
  trainee.id as trainee_id,
  trainee.full_name,
  trainee.current_phase,
  trainee.is_test,
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

drop view if exists public.case_training_metrics;

create view public.case_training_metrics
with (security_invoker = true)
as
select
  cases.id as case_id,
  cases.trainee_id,
  trainees.full_name as trainee_name,
  trainees.is_test as trainee_is_test,
  cases.set_no,
  cases.case_no,
  cases.catalog_label,
  cases.order_number,
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

grant select on public.case_training_metrics to authenticated;
