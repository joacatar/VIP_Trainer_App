-- Legacy path: corrections without file replacements left cases in
-- corrections_sent, which hid them from the trainee Needs you queue.
-- Align with corrections-only publish: hand those cases back so the
-- trainee can fix open feedback and resubmit.

update public.cases c
set status = 'awaiting_resubmission'
where c.status = 'corrections_sent'
  and exists (
    select 1
    from public.corrections_threads t
    where t.case_id = c.id
      and t.status <> 'resolved'
  );
