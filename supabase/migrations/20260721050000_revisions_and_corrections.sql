-- Milestone 3: revisions, fixed sections, corrections, screenshots.

create type public.revision_status as enum ('draft', 'published');
create type public.review_section_key as enum (
  'scan',
  'rider_form',
  'segmentation',
  'scapula',
  'glenoid_landmark',
  'humeral_landmark',
  'humeral_implant',
  'glenoid_implant'
);
create type public.correction_severity as enum ('minor', 'major');
create type public.correction_status as enum ('open', 'resolved');

create table public.revisions (
  id uuid primary key default gen_random_uuid(),
  case_id uuid not null references public.cases(id) on delete cascade,
  revision_no integer not null check (revision_no >= 1),
  status public.revision_status not null default 'draft',
  created_by uuid references auth.users(id) on delete set null,
  published_by uuid references auth.users(id) on delete set null,
  published_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (case_id, revision_no)
);

create unique index one_draft_revision_per_case_idx
  on public.revisions (case_id)
  where status = 'draft';

create table public.revision_sections (
  id uuid primary key default gen_random_uuid(),
  revision_id uuid not null references public.revisions(id) on delete cascade,
  section_key public.review_section_key not null,
  sort_order integer not null check (sort_order between 1 and 8),
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (revision_id, section_key),
  unique (revision_id, sort_order)
);

create table public.corrections (
  id uuid primary key default gen_random_uuid(),
  section_id uuid not null references public.revision_sections(id) on delete cascade,
  body text not null check (length(trim(body)) > 0),
  severity public.correction_severity not null default 'minor',
  status public.correction_status not null default 'open',
  rolled_from_correction_id uuid references public.corrections(id) on delete set null,
  created_by uuid references auth.users(id) on delete set null,
  resolved_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index corrections_section_status_idx
  on public.corrections (section_id, status);

create table public.correction_screenshots (
  id uuid primary key default gen_random_uuid(),
  correction_id uuid not null references public.corrections(id) on delete cascade,
  storage_path text not null,
  original_filename text not null,
  mime_type text,
  size_bytes bigint,
  uploaded_by uuid references auth.users(id) on delete set null,
  created_at timestamptz not null default now()
);

create index correction_screenshots_correction_idx
  on public.correction_screenshots (correction_id);

create trigger revisions_set_updated_at
before update on public.revisions
for each row execute function private.set_updated_at();

create trigger revision_sections_set_updated_at
before update on public.revision_sections
for each row execute function private.set_updated_at();

create trigger corrections_set_updated_at
before update on public.corrections
for each row execute function private.set_updated_at();

alter table public.revisions enable row level security;
alter table public.revision_sections enable row level security;
alter table public.corrections enable row level security;
alter table public.correction_screenshots enable row level security;

create or replace function private.case_id_for_revision(target_revision_id uuid)
returns uuid
language sql
stable
security definer
set search_path = ''
as $$
  select case_id from public.revisions where id = target_revision_id;
$$;

create or replace function private.trainee_owns_case(target_case_id uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1
    from public.cases
    where cases.id = target_case_id
      and private.owns_trainee(cases.trainee_id)
  );
$$;

grant execute on function private.case_id_for_revision(uuid) to authenticated;
grant execute on function private.trainee_owns_case(uuid) to authenticated;

-- Trainers manage everything; trainees read published revision trees for own cases.
create policy "revisions_trainers_manage"
on public.revisions for all to authenticated
using (private.is_trainer())
with check (private.is_trainer());

create policy "revisions_trainees_read_published"
on public.revisions for select to authenticated
using (
  status = 'published'
  and private.trainee_owns_case(case_id)
);

create policy "revision_sections_trainers_manage"
on public.revision_sections for all to authenticated
using (private.is_trainer())
with check (private.is_trainer());

create policy "revision_sections_trainees_read_published"
on public.revision_sections for select to authenticated
using (
  exists (
    select 1
    from public.revisions
    where revisions.id = revision_sections.revision_id
      and revisions.status = 'published'
      and private.trainee_owns_case(revisions.case_id)
  )
);

create policy "corrections_trainers_manage"
on public.corrections for all to authenticated
using (private.is_trainer())
with check (private.is_trainer());

create policy "corrections_trainees_read_published"
on public.corrections for select to authenticated
using (
  exists (
    select 1
    from public.revision_sections
    join public.revisions on revisions.id = revision_sections.revision_id
    where revision_sections.id = corrections.section_id
      and revisions.status = 'published'
      and private.trainee_owns_case(revisions.case_id)
  )
);

create policy "correction_screenshots_trainers_manage"
on public.correction_screenshots for all to authenticated
using (private.is_trainer())
with check (private.is_trainer());

create policy "correction_screenshots_trainees_read_published"
on public.correction_screenshots for select to authenticated
using (
  exists (
    select 1
    from public.corrections
    join public.revision_sections on revision_sections.id = corrections.section_id
    join public.revisions on revisions.id = revision_sections.revision_id
    where corrections.id = correction_screenshots.correction_id
      and revisions.status = 'published'
      and private.trainee_owns_case(revisions.case_id)
  )
);

grant select, insert, update, delete
  on public.revisions,
     public.revision_sections,
     public.corrections,
     public.correction_screenshots
  to authenticated;

create or replace function public.create_revision(target_case_id uuid)
returns uuid
language plpgsql
security definer
set search_path = ''
as $$
declare
  case_row public.cases%rowtype;
  next_no integer;
  new_revision_id uuid;
  prior_revision_id uuid;
  section_def record;
  new_section_id uuid;
  prior_section_id uuid;
  open_correction record;
begin
  if not private.is_trainer() then
    raise exception 'Only trainers can create revisions';
  end if;

  select * into case_row
  from public.cases
  where id = target_case_id
  for update;

  if not found then
    raise exception 'Case not found';
  end if;

  if case_row.status not in ('in_review', 'corrections_sent') then
    raise exception 'Case must be in review or corrections_sent to start a revision';
  end if;

  if exists (
    select 1 from public.revisions
    where case_id = target_case_id and status = 'draft'
  ) then
    raise exception 'A draft revision already exists for this case';
  end if;

  select coalesce(max(revision_no), 0) + 1
  into next_no
  from public.revisions
  where case_id = target_case_id;

  insert into public.revisions (case_id, revision_no, status, created_by)
  values (target_case_id, next_no, 'draft', (select auth.uid()))
  returning id into new_revision_id;

  for section_def in
    select *
    from (
      values
        ('scan'::public.review_section_key, 1),
        ('rider_form'::public.review_section_key, 2),
        ('segmentation'::public.review_section_key, 3),
        ('scapula'::public.review_section_key, 4),
        ('glenoid_landmark'::public.review_section_key, 5),
        ('humeral_landmark'::public.review_section_key, 6),
        ('humeral_implant'::public.review_section_key, 7),
        ('glenoid_implant'::public.review_section_key, 8)
    ) as s(section_key, sort_order)
  loop
    insert into public.revision_sections (revision_id, section_key, sort_order)
    values (new_revision_id, section_def.section_key, section_def.sort_order)
    returning id into new_section_id;

    if next_no > 1 then
      select id into prior_revision_id
      from public.revisions
      where case_id = target_case_id
        and status = 'published'
      order by revision_no desc
      limit 1;

      if prior_revision_id is not null then
        select id into prior_section_id
        from public.revision_sections
        where revision_id = prior_revision_id
          and section_key = section_def.section_key;

        if prior_section_id is not null then
          for open_correction in
            select *
            from public.corrections
            where section_id = prior_section_id
              and status = 'open'
          loop
            insert into public.corrections (
              section_id,
              body,
              severity,
              status,
              rolled_from_correction_id,
              created_by
            )
            values (
              new_section_id,
              open_correction.body,
              open_correction.severity,
              'open',
              open_correction.id,
              (select auth.uid())
            );
          end loop;
        end if;
      end if;
    end if;
  end loop;

  insert into public.tracking_events (
    trainee_id, case_id, actor_user_id, event_type, event_data
  )
  values (
    case_row.trainee_id,
    target_case_id,
    (select auth.uid()),
    'revision_created',
    jsonb_build_object(
      'revision_id', new_revision_id,
      'revision_no', next_no
    )
  );

  return new_revision_id;
end;
$$;

create or replace function public.publish_revision(target_revision_id uuid)
returns void
language plpgsql
security definer
set search_path = ''
as $$
declare
  revision_row public.revisions%rowtype;
  case_row public.cases%rowtype;
begin
  if not private.is_trainer() then
    raise exception 'Only trainers can publish revisions';
  end if;

  select * into revision_row
  from public.revisions
  where id = target_revision_id
  for update;

  if not found then
    raise exception 'Revision not found';
  end if;

  if revision_row.status <> 'draft' then
    raise exception 'Only draft revisions can be published';
  end if;

  select * into case_row
  from public.cases
  where id = revision_row.case_id
  for update;

  update public.revisions
  set status = 'published',
      published_at = now(),
      published_by = (select auth.uid())
  where id = target_revision_id;

  update public.cases
  set status = 'corrections_sent'
  where id = revision_row.case_id
    and status not in ('approved', 'blocked');

  insert into public.tracking_events (
    trainee_id, case_id, actor_user_id, event_type, event_data
  )
  values (
    case_row.trainee_id,
    revision_row.case_id,
    (select auth.uid()),
    'revision_published',
    jsonb_build_object(
      'revision_id', target_revision_id,
      'revision_no', revision_row.revision_no
    )
  );
end;
$$;

create or replace function public.add_correction(
  target_section_id uuid,
  correction_body text,
  correction_severity public.correction_severity default 'minor'
)
returns uuid
language plpgsql
security definer
set search_path = ''
as $$
declare
  section_row public.revision_sections%rowtype;
  revision_row public.revisions%rowtype;
  correction_id uuid;
begin
  if not private.is_trainer() then
    raise exception 'Only trainers can add corrections';
  end if;

  if length(trim(correction_body)) = 0 then
    raise exception 'Correction body is required';
  end if;

  select * into section_row
  from public.revision_sections
  where id = target_section_id;

  if not found then
    raise exception 'Section not found';
  end if;

  select * into revision_row
  from public.revisions
  where id = section_row.revision_id;

  if revision_row.status <> 'draft' then
    raise exception 'Published revisions are immutable';
  end if;

  insert into public.corrections (
    section_id, body, severity, status, created_by
  )
  values (
    target_section_id,
    trim(correction_body),
    correction_severity,
    'open',
    (select auth.uid())
  )
  returning id into correction_id;

  return correction_id;
end;
$$;

create or replace function public.set_correction_status(
  target_correction_id uuid,
  next_status public.correction_status
)
returns void
language plpgsql
security definer
set search_path = ''
as $$
declare
  correction_row public.corrections%rowtype;
  revision_status public.revision_status;
begin
  if not private.is_trainer() then
    raise exception 'Only trainers can update corrections';
  end if;

  select c.* into correction_row
  from public.corrections as c
  where c.id = target_correction_id
  for update;

  if not found then
    raise exception 'Correction not found';
  end if;

  select r.status into revision_status
  from public.revision_sections as s
  join public.revisions as r on r.id = s.revision_id
  where s.id = correction_row.section_id;

  if revision_status <> 'draft' then
    raise exception 'Published revisions are immutable';
  end if;

  update public.corrections
  set status = next_status,
      resolved_at = case
        when next_status = 'resolved' then now()
        else null
      end
  where id = target_correction_id;
end;
$$;

revoke all on function public.create_revision(uuid) from public, anon;
revoke all on function public.publish_revision(uuid) from public, anon;
revoke all on function public.add_correction(uuid, text, public.correction_severity)
  from public, anon;
revoke all on function public.set_correction_status(uuid, public.correction_status)
  from public, anon;

grant execute on function public.create_revision(uuid) to authenticated;
grant execute on function public.publish_revision(uuid) to authenticated;
grant execute on function public.add_correction(uuid, text, public.correction_severity)
  to authenticated;
grant execute on function public.set_correction_status(uuid, public.correction_status)
  to authenticated;
