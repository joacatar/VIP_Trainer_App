-- Track when a trainee has actually opened an answered question so the
-- app can show an "unread answer" indicator instead of relying on the
-- trainee remembering to revisit every case's Questions tab.

alter table public.questions
  add column trainee_viewed_at timestamptz;

create or replace function public.mark_question_viewed(
  target_question_id uuid
)
returns void
language plpgsql
security definer
set search_path = ''
as $$
declare
  question_row public.questions%rowtype;
  case_row public.cases%rowtype;
begin
  select * into question_row
  from public.questions
  where id = target_question_id
  for update;

  if not found then
    raise exception 'Question not found';
  end if;

  select * into case_row
  from public.cases
  where id = question_row.case_id;

  if not (
    private.is_trainer()
    or private.owns_trainee(case_row.trainee_id)
  ) then
    raise exception 'Not allowed to view this question';
  end if;

  update public.questions
  set trainee_viewed_at = now()
  where id = target_question_id;
end;
$$;

revoke all on function public.mark_question_viewed(uuid) from public, anon;
grant execute on function public.mark_question_viewed(uuid) to authenticated;

-- One cheap round trip for a trainee's "unread answers" badge, instead of
-- pulling every question row just to count client-side.
create or replace function public.count_unread_question_answers(
  target_trainee_id uuid default null
)
returns integer
language plpgsql
security definer
set search_path = ''
as $$
declare
  resolved_trainee_id uuid;
  unread_count integer;
begin
  if private.is_trainer() then
    resolved_trainee_id := target_trainee_id;
  else
    select id into resolved_trainee_id
    from public.trainees
    where auth_user_id = (select auth.uid());
  end if;

  if resolved_trainee_id is null then
    return 0;
  end if;

  select count(*)
  into unread_count
  from public.questions q
  join public.cases c on c.id = q.case_id
  where c.trainee_id = resolved_trainee_id
    and q.status = 'answered'
    and (
      q.trainee_viewed_at is null
      or q.trainee_viewed_at < q.answered_at
    );

  return coalesce(unread_count, 0);
end;
$$;

revoke all on function public.count_unread_question_answers(uuid)
  from public, anon;
grant execute on function public.count_unread_question_answers(uuid)
  to authenticated;
