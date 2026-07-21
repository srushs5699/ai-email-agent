-- Step 10: repair an interrupted extension import without duplicating its
-- existing outreach record.  The queue insert and capacity update are atomic.
create function public.repair_extension_orphaned_outreach(
  p_user_id uuid, p_outreach_item_id uuid, p_metadata jsonb
) returns table(queue_id uuid, queue_item_id uuid, outreach_item_id uuid,
                queue_item_count integer, created_new_queue boolean, queue_status text)
language plpgsql security definer set search_path = public as $$
declare q public.processing_queues; i public.processing_queue_items; o public.outreach_items;
begin
  perform pg_advisory_xact_lock(hashtext(p_user_id::text));
  select * into o from public.outreach_items
   where id=p_outreach_item_id and user_id=p_user_id for update;
  if not found then raise exception 'Extension outreach record was not found'; end if;
  if exists (select 1 from public.processing_queue_items where outreach_item_id=o.id) then
    raise exception 'Extension outreach record already has a queue item';
  end if;
  if exists (select 1 from public.generated_drafts where outreach_item_id=o.id) then
    raise exception 'Extension outreach record has downstream work';
  end if;
  select * into q from public.processing_queues
   where user_id=p_user_id and status in ('draft','running','paused') and total_items < 10
   order by updated_at desc for update limit 1;
  created_new_queue := not found;
  if created_new_queue then
    insert into public.processing_queues(user_id,status,total_items) values(p_user_id,'draft',0) returning * into q;
  end if;
  insert into public.processing_queue_items(
    queue_id,user_id,position,input_payload,outreach_item_id,
    source_linkedin_post_url,source_author_name,source_author_profile_url,
    source_linkedin_post_text,source_job_description_url,source_job_description_text,capture_source,captured_at
  ) values (
    q.id,p_user_id,q.total_items,p_metadata,o.id,
    o.linkedin_post_url,o.linkedin_author_name,o.linkedin_author_profile_url,
    o.linkedin_post_text,o.job_description_url,o.job_description_text,
    coalesce(p_metadata->>'capture_source','browser_extension'),(p_metadata->>'captured_at')::timestamptz
  ) returning * into i;
  update public.processing_queues set total_items=total_items+1 where id=q.id
    returning status,total_items into queue_status,queue_item_count;
  queue_id := q.id; queue_item_id := i.id; outreach_item_id := o.id; return next;
end; $$;

revoke all on function public.repair_extension_orphaned_outreach(uuid, uuid, jsonb)
  from public, anon, authenticated;
grant execute on function public.repair_extension_orphaned_outreach(uuid, uuid, jsonb)
  to service_role;
