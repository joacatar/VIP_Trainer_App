-- Count waiting work by FILE slots (not whole cases), and raise storage limit.

update storage.buckets
set file_size_limit = 1073741824  -- 1 GiB
where id = 'case-files';

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
  -- Files the trainer still needs to review
  count(requirements.id) filter (
    where requirements.status in ('submitted', 'under_review')
  ) as waiting_on_trainer,
  -- Files the trainee still needs to upload/replace on active cases
  count(requirements.id) filter (
    where requirements.status in ('missing', 'replacement_requested')
      and cases.status in (
        'assigned',
        'submitted',
        'awaiting_resubmission',
        'in_review',
        'corrections_sent'
      )
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
