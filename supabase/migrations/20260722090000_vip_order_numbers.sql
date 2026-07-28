-- VIP order numbers for each Planning Training case slot.

alter table public.case_schedule_template
  add column if not exists order_number text;

update public.case_schedule_template as t
set order_number = v.order_number
from (
  values
    (1, 1, '12-26-02-0002'),
    (1, 2, '12-26-02-0004'),
    (1, 3, '12-26-02-0008'),
    (1, 4, '12-26-02-0010'),
    (1, 5, '12-26-02-0012'),
    (1, 6, '12-26-02-0014'),
    (1, 7, '12-26-02-0016'),
    (1, 8, '12-26-02-0018'),
    (1, 9, '12-26-02-0020'),
    (1, 10, '12-26-02-0022'),
    (1, 11, '12-26-02-0024'),
    (1, 12, '12-26-02-0028'),
    (1, 13, '12-26-02-0032'),
    (1, 14, '12-26-02-0034'),
    (1, 15, '12-26-02-0036'),
    (1, 16, '12-26-02-0038'),
    (2, 1, '12-26-02-0003'),
    (2, 2, '12-26-02-0005'),
    (2, 3, '12-26-02-0009'),
    (2, 4, '12-26-02-0011'),
    (2, 5, '12-26-02-0013'),
    (2, 6, '12-26-02-0015'),
    (2, 7, '12-26-02-0017'),
    (2, 8, '12-26-02-0019'),
    (2, 9, '12-26-02-0021'),
    (2, 10, '12-26-02-0023'),
    (2, 11, '12-26-02-0025'),
    (2, 12, '12-26-02-0029'),
    (2, 13, '12-26-02-0033'),
    (2, 14, '12-26-02-0035'),
    (2, 15, '12-26-02-0037'),
    (2, 16, '12-26-02-0039')
) as v(set_no, case_no, order_number)
where t.set_no = v.set_no
  and t.case_no = v.case_no;

alter table public.case_schedule_template
  alter column order_number set not null;

alter table public.cases
  add column if not exists order_number text;

update public.cases as c
set order_number = t.order_number
from public.case_schedule_template as t
where t.set_no = c.set_no
  and t.case_no = c.case_no
  and (c.order_number is null or c.order_number = '');

alter table public.cases
  alter column order_number set not null;

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
    order_number,
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
    template.order_number,
    template.training_day,
    private.training_date(new.start_date, template.training_day),
    private.training_date(new.start_date, template.training_day)
  from public.case_schedule_template as template;
  return new;
end;
$$;

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
