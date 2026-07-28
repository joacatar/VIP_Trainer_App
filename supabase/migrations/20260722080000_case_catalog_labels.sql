-- Add APAC catalog labels (1A–16A / 1B–16B) to the schedule template and cases.

alter table public.case_schedule_template
  add column if not exists catalog_label text;

update public.case_schedule_template
set catalog_label = case_no::text || case when set_no = 1 then 'A' else 'B' end
where catalog_label is null;

alter table public.case_schedule_template
  alter column catalog_label set not null;

alter table public.cases
  add column if not exists catalog_label text;

update public.cases as c
set catalog_label = t.catalog_label
from public.case_schedule_template as t
where t.set_no = c.set_no
  and t.case_no = c.case_no
  and (c.catalog_label is null or c.catalog_label = '');

alter table public.cases
  alter column catalog_label set not null;

create or replace function private.create_trainee_cases()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  insert into public.cases (
    trainee_id,
    phase,
    set_no,
    case_no,
    catalog_label,
    scheduled_training_day,
    schedule_due_date,
    due_date
  )
  select
    new.id,
    'ct_planning'::public.training_phase,
    template.set_no,
    template.case_no,
    template.catalog_label,
    template.training_day,
    private.training_date(new.start_date, template.training_day),
    private.training_date(new.start_date, template.training_day)
  from public.case_schedule_template as template;
  return new;
end;
$$;

-- Keep analytics view in sync with the new column (drop first so column
-- order can change safely).
drop view if exists public.case_training_metrics;

create view public.case_training_metrics
with (security_invoker = true)
as
select
  cases.id as case_id,
  cases.trainee_id,
  trainees.full_name as trainee_name,
  cases.set_no,
  cases.case_no,
  cases.catalog_label,
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
