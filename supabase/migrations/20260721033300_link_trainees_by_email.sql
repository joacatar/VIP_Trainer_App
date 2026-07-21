-- Keep trainee records and Supabase Auth users linked by normalized email.

create unique index trainees_email_unique_idx
  on public.trainees (lower(email))
  where email is not null;

create or replace function private.assign_trainee_auth_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if new.auth_user_id is null and new.email is not null then
    select auth_user.id
    into new.auth_user_id
    from auth.users as auth_user
    where lower(auth_user.email) = lower(new.email)
    limit 1;
  end if;
  return new;
end;
$$;

create trigger assign_trainee_auth_user
before insert or update of email, auth_user_id on public.trainees
for each row execute function private.assign_trainee_auth_user();

create or replace function private.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  insert into public.profiles (id, full_name)
  values (new.id, coalesce(new.raw_user_meta_data ->> 'full_name', ''));

  update public.trainees
  set auth_user_id = new.id
  where auth_user_id is null
    and new.email is not null
    and lower(email) = lower(new.email);

  return new;
end;
$$;

update public.trainees as trainee
set auth_user_id = auth_user.id
from auth.users as auth_user
where trainee.auth_user_id is null
  and trainee.email is not null
  and lower(trainee.email) = lower(auth_user.email);

revoke execute on function private.assign_trainee_auth_user() from public;
