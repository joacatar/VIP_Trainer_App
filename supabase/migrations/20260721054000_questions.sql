-- Milestone 4: trainee questions with trainer answers and screenshots.

create type public.question_status as enum ('open', 'answered', 'resolved');

create table public.questions (
  id uuid primary key default gen_random_uuid(),
  case_id uuid not null references public.cases(id) on delete cascade,
  section_key public.review_section_key,
  body text not null check (length(trim(body)) > 0),
  status public.question_status not null default 'open',
  asked_by uuid references auth.users(id) on delete set null,
  answer_body text,
  answered_by uuid references auth.users(id) on delete set null,
  answered_at timestamptz,
  resolved_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index questions_case_status_idx
  on public.questions (case_id, status);

create index questions_status_created_idx
  on public.questions (status, created_at desc);

create table public.question_screenshots (
  id uuid primary key default gen_random_uuid(),
  question_id uuid not null references public.questions(id) on delete cascade,
  storage_path text not null,
  original_filename text not null,
  mime_type text,
  size_bytes bigint,
  uploaded_by uuid references auth.users(id) on delete set null,
  created_at timestamptz not null default now()
);

create index question_screenshots_question_idx
  on public.question_screenshots (question_id);

create trigger questions_set_updated_at
before update on public.questions
for each row execute function private.set_updated_at();

alter table public.questions enable row level security;
alter table public.question_screenshots enable row level security;

create policy "questions_trainers_manage"
on public.questions for all to authenticated
using (private.is_trainer())
with check (private.is_trainer());

create policy "questions_trainees_read_own"
on public.questions for select to authenticated
using (private.trainee_owns_case(case_id));

create policy "questions_trainees_insert_own"
on public.questions for insert to authenticated
with check (private.trainee_owns_case(case_id));

create policy "question_screenshots_trainers_manage"
on public.question_screenshots for all to authenticated
using (private.is_trainer())
with check (private.is_trainer());

create policy "question_screenshots_trainees_read_own"
on public.question_screenshots for select to authenticated
using (
  exists (
    select 1
    from public.questions
    where questions.id = question_screenshots.question_id
      and private.trainee_owns_case(questions.case_id)
  )
);

create policy "question_screenshots_trainees_insert_own"
on public.question_screenshots for insert to authenticated
with check (
  exists (
    select 1
    from public.questions
    where questions.id = question_screenshots.question_id
      and private.trainee_owns_case(questions.case_id)
  )
);

grant select, insert, update, delete
  on public.questions, public.question_screenshots
  to authenticated;

create or replace function public.ask_question(
  target_case_id uuid,
  question_body text,
  target_section_key public.review_section_key default null
)
returns uuid
language plpgsql
security definer
set search_path = ''
as $$
declare
  case_row public.cases%rowtype;
  cleaned text;
  new_id uuid;
begin
  cleaned := nullif(trim(question_body), '');
  if cleaned is null then
    raise exception 'Question cannot be empty';
  end if;

  select * into case_row
  from public.cases
  where id = target_case_id
  for update;

  if not found then
    raise exception 'Case not found';
  end if;

  if not (
    private.is_trainer()
    or private.owns_trainee(case_row.trainee_id)
  ) then
    raise exception 'Not allowed to ask on this case';
  end if;

  if case_row.status = 'not_started' then
    raise exception 'Assign the case before asking questions';
  end if;

  insert into public.questions (
    case_id, section_key, body, status, asked_by
  )
  values (
    target_case_id,
    target_section_key,
    cleaned,
    'open',
    (select auth.uid())
  )
  returning id into new_id;

  insert into public.tracking_events (
    trainee_id, case_id, actor_user_id, event_type, event_data
  )
  values (
    case_row.trainee_id,
    case_row.id,
    (select auth.uid()),
    'question_asked',
    jsonb_build_object(
      'question_id', new_id,
      'section_key', target_section_key
    )
  );

  return new_id;
end;
$$;

create or replace function public.answer_question(
  target_question_id uuid,
  response_body text
)
returns void
language plpgsql
security definer
set search_path = ''
as $$
declare
  question_row public.questions%rowtype;
  case_row public.cases%rowtype;
  cleaned text;
begin
  if not private.is_trainer() then
    raise exception 'Only trainers can answer questions';
  end if;

  cleaned := nullif(trim(response_body), '');
  if cleaned is null then
    raise exception 'Answer cannot be empty';
  end if;

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

  update public.questions
  set status = 'answered',
      answer_body = cleaned,
      answered_by = (select auth.uid()),
      answered_at = now(),
      resolved_at = null
  where id = target_question_id;

  insert into public.tracking_events (
    trainee_id, case_id, actor_user_id, event_type, event_data
  )
  values (
    case_row.trainee_id,
    case_row.id,
    (select auth.uid()),
    'question_answered',
    jsonb_build_object('question_id', target_question_id)
  );
end;
$$;

create or replace function public.set_question_status(
  target_question_id uuid,
  next_status public.question_status
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
  if next_status not in ('open', 'answered', 'resolved') then
    raise exception 'Invalid question status';
  end if;

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
    raise exception 'Not allowed to update this question';
  end if;

  -- Trainees may only resolve / reopen answered questions on their cases.
  if not private.is_trainer() then
    if next_status = 'resolved' and question_row.status not in ('answered', 'resolved') then
      raise exception 'Only answered questions can be resolved';
    end if;
    if next_status = 'open' and question_row.status <> 'resolved' then
      raise exception 'Only resolved questions can be reopened by trainees';
    end if;
    if next_status = 'answered' then
      raise exception 'Trainees cannot mark questions as answered';
    end if;
  end if;

  update public.questions
  set status = next_status,
      resolved_at = case
        when next_status = 'resolved' then now()
        else null
      end
  where id = target_question_id;

  insert into public.tracking_events (
    trainee_id, case_id, actor_user_id, event_type, event_data
  )
  values (
    case_row.trainee_id,
    case_row.id,
    (select auth.uid()),
    'question_status_changed',
    jsonb_build_object(
      'question_id', target_question_id,
      'status', next_status
    )
  );
end;
$$;

revoke all on function public.ask_question(uuid, text, public.review_section_key)
  from public, anon;
revoke all on function public.answer_question(uuid, text) from public, anon;
revoke all on function public.set_question_status(uuid, public.question_status)
  from public, anon;

grant execute on function public.ask_question(uuid, text, public.review_section_key)
  to authenticated;
grant execute on function public.answer_question(uuid, text) to authenticated;
grant execute on function public.set_question_status(uuid, public.question_status)
  to authenticated;
