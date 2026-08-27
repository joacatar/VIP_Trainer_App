-- Corrections-only return path: publishing feedback always hands the case
-- back to the trainee as awaiting_resubmission (they fix work + resubmit).
-- No per-file replacement gate. Approve clears any leftover replacement marks.

create or replace function public.publish_case_review(
  target_case_id uuid,
  target_revision_id uuid default null,
  file_decisions jsonb default '[]'::jsonb,
  approve_package boolean default false
)
returns void
language plpgsql
security definer
set search_path = ''
as $$
declare
  case_row public.cases%rowtype;
  revision_row public.revisions%rowtype;
  decision_item jsonb;
  requirement_id uuid;
  decision text;
  decision_note text;
begin
  if not private.is_trainer() then
    raise exception 'Only trainers can publish a case review';
  end if;

  select * into case_row
  from public.cases
  where id = target_case_id
  for update;

  if not found then
    raise exception 'Case not found';
  end if;

  if case_row.status not in ('in_review', 'corrections_sent') then
    raise exception 'Case must be in review before publishing a review';
  end if;

  if jsonb_typeof(file_decisions) <> 'array' then
    raise exception 'file_decisions must be a JSON array';
  end if;

  -- Optional legacy file_decisions still applied if a client sends them.
  for decision_item in
    select value from jsonb_array_elements(file_decisions)
  loop
    requirement_id := nullif(decision_item ->> 'requirement_id', '')::uuid;
    decision := lower(coalesce(decision_item ->> 'decision', ''));
    decision_note := nullif(trim(coalesce(decision_item ->> 'note', '')), '');

    if requirement_id is null then
      raise exception 'Each file decision needs a requirement_id';
    end if;
    if decision not in ('accepted', 'rejected') then
      raise exception 'File decision must be accepted or rejected';
    end if;

    perform public.review_file_requirement(
      requirement_id,
      decision,
      decision_note
    );
  end loop;

  if target_revision_id is not null then
    select * into revision_row
    from public.revisions
    where id = target_revision_id
    for update;

    if not found then
      raise exception 'Revision not found';
    end if;
    if revision_row.case_id <> target_case_id then
      raise exception 'Revision does not belong to this case';
    end if;

    if revision_row.status = 'draft' then
      update public.revisions
      set status = 'published',
          published_at = now(),
          published_by = (select auth.uid())
      where id = target_revision_id;

      insert into public.tracking_events (
        trainee_id, case_id, actor_user_id, event_type, event_data
      )
      values (
        case_row.trainee_id,
        target_case_id,
        (select auth.uid()),
        'revision_published',
        jsonb_build_object(
          'revision_id', target_revision_id,
          'revision_no', revision_row.revision_no,
          'via', 'publish_case_review'
        )
      );
    end if;
  end if;

  if approve_package then
    -- Accept every deliverable; clear leftover replacement marks.
    update public.file_requirements
    set status = 'accepted',
        replacement_reason = null,
        accepted_at = coalesce(accepted_at, now())
    where case_id = target_case_id
      and status in (
        'submitted',
        'under_review',
        'accepted',
        'replacement_requested'
      );

    update public.corrections c
    set status = 'resolved',
        resolved_at = now()
    from public.revision_sections rs
    join public.revisions r on r.id = rs.revision_id
    where c.section_id = rs.id
      and r.case_id = target_case_id
      and c.status = 'open';

    update public.corrections_threads
    set status = 'resolved',
        resolved_at = coalesce(resolved_at, now())
    where case_id = target_case_id
      and status <> 'resolved';

    update public.cases
    set status = 'approved',
        approved_at = now()
    where id = target_case_id;

    insert into public.tracking_events (
      trainee_id, case_id, actor_user_id, event_type, event_data
    )
    values (
      case_row.trainee_id,
      target_case_id,
      (select auth.uid()),
      'case_approved',
      jsonb_build_object('via', 'publish_case_review')
    );
    return;
  end if;

  -- Feedback published → trainee owns the next action (fix + resubmit).
  -- Always awaiting_resubmission; per-file replacement is no longer required.
  if target_revision_id is not null then
    update public.cases
    set status = 'awaiting_resubmission'
    where id = target_case_id
      and status not in ('approved', 'blocked');
  end if;

  insert into public.tracking_events (
    trainee_id, case_id, actor_user_id, event_type, event_data
  )
  values (
    case_row.trainee_id,
    target_case_id,
    (select auth.uid()),
    'case_review_published',
    jsonb_build_object(
      'revision_id', target_revision_id,
      'approve_package', false,
      'return_mode', 'corrections_only'
    )
  );
end;
$$;

revoke all on function public.publish_case_review(uuid, uuid, jsonb, boolean)
  from public, anon;
grant execute on function public.publish_case_review(uuid, uuid, jsonb, boolean)
  to authenticated;
