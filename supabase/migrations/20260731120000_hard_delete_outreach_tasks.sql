-- A queue delete is a permanent workflow delete.  Keep it in one database
-- transaction so partially deleted captures can never block a later import.
create or replace function public.recalculate_processing_queue_counts(p_queue_id uuid)
returns void language plpgsql security definer set search_path = public as $$
declare v_total integer; v_completed integer; v_failed integer;
begin
  select count(*), count(*) filter (where status = 'completed'),
         count(*) filter (where status = 'failed')
    into v_total, v_completed, v_failed
    from public.processing_queue_items where queue_id = p_queue_id;
  update public.processing_queues
     set total_items = v_total,
         completed_items = v_completed,
         failed_items = v_failed,
         status = case when v_total = 0 and status in ('draft','running','paused') then 'completed' else status end,
         completed_at = case when v_total = 0 and status in ('draft','running','paused') then now() else completed_at end
   where id = p_queue_id;
end; $$;

create or replace function public.delete_outreach_item_permanently(
  p_user_id uuid, p_outreach_item_id uuid
) returns boolean language plpgsql security definer set search_path = public as $$
declare v_queue_ids uuid[];
begin
  -- The ownership predicate deliberately makes another user's id indistinguishable
  -- from a missing id to callers.
  if not exists (select 1 from public.outreach_items where id = p_outreach_item_id and user_id = p_user_id for update) then
    return false;
  end if;
  select array_agg(distinct queue_id) into v_queue_ids
    from public.processing_queue_items
   where outreach_item_id = p_outreach_item_id and user_id = p_user_id;

  -- Gmail IDs live on generated_drafts.  Removing that local metadata does not
  -- call Gmail and therefore does not delete a draft in the user's Gmail account.
  delete from public.ai_usage where outreach_item_id = p_outreach_item_id and user_id = p_user_id;
  delete from public.processing_queue_items where outreach_item_id = p_outreach_item_id and user_id = p_user_id;
  delete from public.outreach_items where id = p_outreach_item_id and user_id = p_user_id;

  if v_queue_ids is not null then
    perform public.recalculate_processing_queue_counts(queue_id) from unnest(v_queue_ids) as queue_id;
  end if;
  return true;
end; $$;

create or replace function public.delete_processing_queue_task_permanently(
  p_user_id uuid, p_queue_item_id uuid
) returns table(deleted boolean, outreach_item_id uuid, queue_id uuid, task_status text) language plpgsql security definer set search_path = public as $$
declare v_item public.processing_queue_items;
begin
  select * into v_item from public.processing_queue_items
   where id = p_queue_item_id and user_id = p_user_id for update;
  if not found then return; end if;
  queue_id := v_item.queue_id;
  task_status := v_item.status;
  outreach_item_id := v_item.outreach_item_id;
  if outreach_item_id is not null then
    deleted := public.delete_outreach_item_permanently(p_user_id, outreach_item_id);
  else
    delete from public.processing_queue_items where id = v_item.id and user_id = p_user_id;
    perform public.recalculate_processing_queue_counts(v_item.queue_id);
    deleted := true;
  end if;
  return next;
end; $$;

revoke all on function public.recalculate_processing_queue_counts(uuid), public.delete_outreach_item_permanently(uuid,uuid), public.delete_processing_queue_task_permanently(uuid,uuid) from public, anon, authenticated;
grant execute on function public.delete_outreach_item_permanently(uuid,uuid), public.delete_processing_queue_task_permanently(uuid,uuid) to service_role;
