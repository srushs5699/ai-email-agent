-- Queue rows are execution references only. Drafts and outreach items are not
-- children of processing queues and remain available in Review after cleanup.
create or replace function public.cleanup_completed_processing_queue(
  p_queue_id uuid,
  p_user_id uuid
) returns boolean language plpgsql security definer set search_path = public as $$
declare v_queue public.processing_queues;
begin
  select * into v_queue from public.processing_queues
  where id = p_queue_id and user_id = p_user_id for update;
  if not found then return false; end if;
  if exists (
    select 1 from public.processing_queue_items
    where queue_id = p_queue_id
      and (status <> 'completed' or generated_draft_id is null)
  ) then return false; end if;
  if not exists (select 1 from public.processing_queue_items where queue_id = p_queue_id) then
    return false;
  end if;
  delete from public.processing_queues where id = p_queue_id and user_id = p_user_id;
  return true;
end; $$;

revoke all on function public.cleanup_completed_processing_queue(uuid, uuid)
  from public, anon, authenticated;
grant execute on function public.cleanup_completed_processing_queue(uuid, uuid)
  to service_role;
