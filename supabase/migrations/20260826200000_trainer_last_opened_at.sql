-- Stamp when a trainer opens a case (Last checked in the Needs you queue).

alter table public.cases
  add column if not exists trainer_last_opened_at timestamptz;

comment on column public.cases.trainer_last_opened_at is
  'Last time a trainer opened the case workspace (React Needs you queue).';

create or replace function public.touch_case_opened(target_case_id uuid)
returns timestamptz
language plpgsql
security definer
set search_path = ''
as $$
declare
  stamped timestamptz;
begin
  if not private.is_trainer() then
    raise exception 'Only trainers can stamp case opened';
  end if;

  update public.cases
  set trainer_last_opened_at = now()
  where id = target_case_id
  returning trainer_last_opened_at into stamped;

  if stamped is null then
    raise exception 'Case not found';
  end if;

  return stamped;
end;
$$;

revoke all on function public.touch_case_opened(uuid)
  from public, anon;
grant execute on function public.touch_case_opened(uuid)
  to authenticated;
