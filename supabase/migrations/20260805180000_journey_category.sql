-- Persist curriculum journey category on template + cases (Feature 8.2).
-- Categories are the named zones in each set's progress path.

alter table public.case_schedule_template
  add column if not exists journey_category text;

update public.case_schedule_template
set journey_category = case
  when case_no between 1 and 4 then 'Success Journey'
  when case_no between 5 and 6 then 'OV Adjusted'
  when case_no between 7 and 11 then 'Rejections'
  when case_no between 12 and 14 then 'Manual'
  when case_no = 15 then 'Duplicate'
  when case_no = 16 then 'Axial3D Case'
  else 'Success Journey'
end
where journey_category is null;

alter table public.case_schedule_template
  alter column journey_category set not null;

alter table public.cases
  add column if not exists journey_category text;

update public.cases as c
set journey_category = t.journey_category
from public.case_schedule_template as t
where t.set_no = c.set_no
  and t.case_no = c.case_no
  and (c.journey_category is null or c.journey_category = '');

-- Safety net if template join missed a row (should not happen).
update public.cases
set journey_category = case
  when case_no between 1 and 4 then 'Success Journey'
  when case_no between 5 and 6 then 'OV Adjusted'
  when case_no between 7 and 11 then 'Rejections'
  when case_no between 12 and 14 then 'Manual'
  when case_no = 15 then 'Duplicate'
  when case_no = 16 then 'Axial3D Case'
  else 'Success Journey'
end
where journey_category is null;

alter table public.cases
  alter column journey_category set not null;

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
    journey_category,
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
    template.journey_category,
    template.training_day,
    private.training_date(new.start_date, template.training_day),
    private.training_date(new.start_date, template.training_day)
  from public.case_schedule_template as template;
  return new;
end;
$$;
