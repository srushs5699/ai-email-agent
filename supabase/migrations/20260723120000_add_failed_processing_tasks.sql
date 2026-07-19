-- Step 8: keep failed processing work retryable without creating a second queue.
alter table public.processing_queue_items
    add column if not exists failure_status text,
    add column if not exists failure_reason text,
    add column if not exists retry_count integer not null default 0 check (retry_count >= 0),
    add column if not exists retry_started_at timestamptz,
    add column if not exists hidden_at timestamptz;

update public.processing_queue_items
set failure_status = 'failed',
    failure_reason = coalesce(error_code, 'This task could not be processed.')
where status = 'failed' and failure_status is null;

alter table public.processing_queue_items
    add constraint processing_queue_items_failure_status_check
    check (failure_status is null or failure_status in ('failed', 'duplicate', 'no_email_available'));

create index if not exists processing_queue_items_failed_tasks_idx
    on public.processing_queue_items (user_id, updated_at desc)
    where status = 'failed' and hidden_at is null;

create or replace function public.claim_failed_processing_queue_item(p_item_id uuid, p_user_id uuid)
returns setof public.processing_queue_items language plpgsql security definer set search_path = public as $$
declare v_item public.processing_queue_items;
begin
  update public.processing_queue_items set status='processing', retry_count=retry_count+1,
    retry_started_at=now(), started_at=now(), completed_at=null, processing_lease_expires_at=null
  where id=p_item_id and user_id=p_user_id and status='failed' and hidden_at is null
  returning * into v_item;
  if found then return next v_item; end if;
end; $$;
revoke all on function public.claim_failed_processing_queue_item(uuid,uuid) from public, anon, authenticated;
grant execute on function public.claim_failed_processing_queue_item(uuid,uuid) to service_role;

-- The existing owner policy remains the only RLS access path.  These columns
-- are deliberately kept on the user-owned processing queue item.
