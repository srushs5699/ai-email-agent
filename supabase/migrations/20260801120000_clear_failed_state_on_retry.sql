-- A claimed retry is active work, not an active Failed Tasks entry.  Clearing
-- the failure metadata keeps it visible with its real processing status.
create or replace function public.claim_failed_processing_queue_item(
  p_item_id uuid,
  p_user_id uuid
)
returns setof public.processing_queue_items language plpgsql security definer set search_path = public as $$
declare v_item public.processing_queue_items;
begin
  update public.processing_queue_items set
    status = 'processing',
    retry_count = retry_count + 1,
    retry_started_at = now(),
    started_at = now(),
    completed_at = null,
    processing_lease_expires_at = null,
    error_code = null,
    failure_status = null,
    failure_reason = null
  where id = p_item_id
    and user_id = p_user_id
    and status = 'failed'
    and hidden_at is null
  returning * into v_item;
  if found then return next v_item; end if;
end; $$;

revoke all on function public.claim_failed_processing_queue_item(uuid, uuid)
  from public, anon, authenticated;
grant execute on function public.claim_failed_processing_queue_item(uuid, uuid)
  to service_role;
