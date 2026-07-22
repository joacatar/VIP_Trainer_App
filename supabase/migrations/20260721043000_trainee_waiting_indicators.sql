-- Add waiting-on-trainer / waiting-on-trainee counts to trainee progress.

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
    where cases.status in ('submitted', 'in_review')
  ) as waiting_on_trainer,
  count(distinct cases.id) filter (
    where cases.status in ('assigned', 'awaiting_resubmission')
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
