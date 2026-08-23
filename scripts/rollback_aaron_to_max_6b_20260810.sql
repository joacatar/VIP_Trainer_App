-- Rollback for private.migrate_aaron_to_max_6b_20260810
-- Restores Aaron Case 6B mistaken review after the Max transfer.
-- Safe only if Max 6B was not further edited after the migrate.
--
-- Usage (Supabase SQL editor / service role):
--   1) Run this file as a single transaction
--   2) If screenshot was copied with copy_migrated_screenshot.py, also revert
--      correction_thread_screenshots.storage_path to the old Aaron path
--      (meta.old_storage_path in the snapshot table)

begin;

-- Threads back to Aaron
update public.corrections_threads th
set case_id = 'bc3dd073-6740-41e2-9d2a-ee003486ab05'::uuid
from private.migrate_aaron_to_max_6b_20260810 s,
     jsonb_array_elements(s.payload) elem
where s.step = 'before_threads'
  and th.id = (elem->>'id')::uuid;

-- Revision back to Aaron
update public.revisions r
set case_id = 'bc3dd073-6740-41e2-9d2a-ee003486ab05'::uuid,
    updated_at = now()
where r.id = '4a901fd1-d7a8-498c-aa3a-1908a9964139'::uuid;

-- Tracking events: case_id + original event_data
update public.tracking_events te
set case_id = (elem->>'case_id')::uuid,
    event_data = elem->'event_data'
from private.migrate_aaron_to_max_6b_20260810 s,
     jsonb_array_elements(s.payload) elem
where s.step = 'before_tracking_events'
  and te.id = (elem->>'id')::bigint;

-- Case statuses from snapshot
update public.cases c
set status = (elem->>'status')::public.case_status,
    updated_at = now()
from private.migrate_aaron_to_max_6b_20260810 s,
     jsonb_array_elements(s.payload) elem
where s.step = 'before_cases'
  and c.id = (elem->>'id')::uuid;

-- File requirements from snapshot
update public.file_requirements fr
set status = (elem->>'status')::public.file_requirement_status,
    replacement_reason = nullif(elem->>'replacement_reason', ''),
    updated_at = now()
from private.migrate_aaron_to_max_6b_20260810 s,
     jsonb_array_elements(s.payload) elem
where s.step = 'before_file_requirements'
  and fr.id = (elem->>'id')::uuid;

-- Screenshot path from snapshot (if still pointing at Max after a storage copy)
update public.correction_thread_screenshots shot
set storage_path = elem->>'storage_path'
from private.migrate_aaron_to_max_6b_20260810 s,
     jsonb_array_elements(s.payload) elem
where s.step = 'before_screenshots'
  and shot.id = (elem->>'id')::uuid;

insert into private.migrate_aaron_to_max_6b_20260810 (step, payload)
values ('rolled_back', jsonb_build_object('ok', true, 'at', now()));

commit;
