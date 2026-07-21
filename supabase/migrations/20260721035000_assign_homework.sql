-- Assign homework and update the case state in one transaction.

create unique index one_open_homework_per_case_idx
  on public.homework_assignments (case_id)
  where status not in ('completed', 'cancelled');

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
begin
  if length(trim(homework_title)) = 0 then
    raise exception 'Homework title is required';
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

  return assignment_id;
end;
$$;

revoke all on function public.assign_homework(uuid, text, text, date, date)
  from public, anon;
grant execute on function public.assign_homework(uuid, text, text, date, date)
  to authenticated;
