-- Replace the earlier repair RPC, which returned no row whenever it found a
-- stale failed/hidden queue association.  Every successful repair returns one
-- explicit queue item; a missing owned outreach returns no row for safe fallback.
create or replace function public.repair_extension_orphaned_outreach(
  p_user_id uuid, p_outreach_item_id uuid, p_metadata jsonb
) returns table(queue_id uuid, queue_item_id uuid, outreach_item_id uuid,
                queue_item_count integer, created_new_queue boolean,
                queue_status text)
language plpgsql security definer set search_path = '' as $$
#variable_conflict error
declare
  v_outreach public.outreach_items;
  v_queue public.processing_queues;
  v_item public.processing_queue_items;
begin
  perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtext(p_user_id::text));
  select oi.* into v_outreach from public.outreach_items as oi
   where oi.id = p_outreach_item_id and oi.user_id = p_user_id for update;
  if not found then return; end if;

  -- A valid association may have been missed only because its URL metadata was
  -- incomplete. Return it instead of creating a second association.
  select pqi.* into v_item from public.processing_queue_items as pqi
   where pqi.outreach_item_id = v_outreach.id and pqi.user_id = p_user_id
   order by pqi.created_at desc for update limit 1;
  if found and v_item.status <> 'failed' and v_item.hidden_at is null then
    select pq.* into v_queue from public.processing_queues as pq where pq.id = v_item.queue_id;
    if found then
      update public.processing_queue_items as pqi set
        source_linkedin_post_url = coalesce(nullif(p_metadata->>'linkedin_post_url',''), pqi.source_linkedin_post_url),
        source_author_name = coalesce(nullif(p_metadata->>'author_name',''), pqi.source_author_name),
        source_author_profile_url = coalesce(nullif(p_metadata->>'author_profile_url',''), pqi.source_author_profile_url),
        source_linkedin_post_text = coalesce(nullif(p_metadata->>'linkedin_post_text',''), pqi.source_linkedin_post_text),
        source_job_description_url = coalesce(nullif(p_metadata->>'job_description_url',''), pqi.source_job_description_url),
        source_job_description_text = coalesce(nullif(p_metadata->>'job_description_text',''), pqi.source_job_description_text)
       where pqi.id = v_item.id;
      queue_id := v_queue.id; queue_item_id := v_item.id; outreach_item_id := v_outreach.id;
      queue_item_count := v_queue.total_items; created_new_queue := false; queue_status := v_queue.status; return next; return;
    end if;
  end if;

  -- Failed/hidden links are not active duplicates. Remove them before creating
  -- one clean association; this also removes stale duplicate-tracking state.
  if v_item.id is not null then
    delete from public.processing_queue_items as pqi where pqi.outreach_item_id = v_outreach.id and pqi.user_id = p_user_id;
    perform public.recalculate_processing_queue_counts(v_item.queue_id);
  end if;
  update public.outreach_items as oi set
    linkedin_post_url = coalesce(nullif(p_metadata->>'linkedin_post_url',''), oi.linkedin_post_url),
    linkedin_author_name = coalesce(nullif(p_metadata->>'author_name',''), oi.linkedin_author_name),
    linkedin_author_profile_url = coalesce(nullif(p_metadata->>'author_profile_url',''), oi.linkedin_author_profile_url),
    linkedin_post_text = coalesce(nullif(p_metadata->>'linkedin_post_text',''), oi.linkedin_post_text),
    job_description_url = coalesce(nullif(p_metadata->>'job_description_url',''), oi.job_description_url),
    job_description_text = coalesce(nullif(p_metadata->>'job_description_text',''), oi.job_description_text), status = 'captured'
   where oi.id = v_outreach.id and oi.user_id = p_user_id returning oi.* into v_outreach;
  select pq.* into v_queue from public.processing_queues as pq
   where pq.user_id = p_user_id and pq.status in ('draft','running','paused') and pq.total_items < 10
   order by pq.updated_at desc for update limit 1;
  created_new_queue := not found;
  if created_new_queue then
    insert into public.processing_queues(user_id,status,total_items) values(p_user_id,'draft',0) returning * into v_queue;
  end if;
  insert into public.processing_queue_items(queue_id,user_id,position,input_payload,outreach_item_id,
    source_linkedin_post_url,source_author_name,source_author_profile_url,source_linkedin_post_text,
    source_job_description_url,source_job_description_text,capture_source,captured_at)
  values(v_queue.id,p_user_id,v_queue.total_items,p_metadata,v_outreach.id,v_outreach.linkedin_post_url,
    v_outreach.linkedin_author_name,v_outreach.linkedin_author_profile_url,v_outreach.linkedin_post_text,
    v_outreach.job_description_url,v_outreach.job_description_text,coalesce(p_metadata->>'capture_source','browser_extension'),
    (p_metadata->>'captured_at')::timestamptz) returning * into v_item;
  update public.processing_queues as pq set total_items = pq.total_items + 1 where pq.id = v_queue.id
    returning pq.status,pq.total_items into queue_status,queue_item_count;
  queue_id := v_queue.id; queue_item_id := v_item.id; outreach_item_id := v_outreach.id; return next;
end;
$$;
revoke all on function public.repair_extension_orphaned_outreach(uuid,uuid,jsonb) from public, anon, authenticated;
grant execute on function public.repair_extension_orphaned_outreach(uuid,uuid,jsonb) to service_role;
notify pgrst, 'reload schema';
