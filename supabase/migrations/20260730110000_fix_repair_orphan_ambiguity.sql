drop function if exists public.repair_extension_orphaned_outreach(uuid, uuid, jsonb);
create function public.repair_extension_orphaned_outreach(p_user_id uuid, p_outreach_item_id uuid, p_metadata jsonb)
returns table(queue_id uuid, queue_item_id uuid, outreach_item_id uuid, queue_item_count integer, created_new_queue boolean, queue_status text)
language plpgsql security definer set search_path = '' as $$
declare q public.processing_queues; i public.processing_queue_items; o public.outreach_items;
begin
  perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtext(p_user_id::text));
  update public.outreach_items as oi set
    linkedin_post_url=coalesce(nullif(p_metadata->>'linkedin_post_url',''), oi.linkedin_post_url),
    linkedin_author_name=coalesce(nullif(p_metadata->>'author_name',''), oi.linkedin_author_name),
    linkedin_author_profile_url=coalesce(nullif(p_metadata->>'author_profile_url',''), oi.linkedin_author_profile_url),
    linkedin_post_text=coalesce(nullif(p_metadata->>'linkedin_post_text',''), oi.linkedin_post_text),
    job_description_url=coalesce(nullif(p_metadata->>'job_description_url',''), oi.job_description_url),
    job_description_text=coalesce(nullif(p_metadata->>'job_description_text',''), oi.job_description_text)
  where oi.id=p_outreach_item_id and oi.user_id=p_user_id returning oi.* into o;
  if not found then return; end if;
  if exists (select 1 from public.processing_queue_items as pqi where pqi.outreach_item_id=o.id)
     or exists (select 1 from public.generated_drafts as gd where gd.outreach_item_id=o.id) then return; end if;
  select * into q from public.processing_queues as pq where pq.user_id=p_user_id and pq.status in ('draft','running','paused') and pq.total_items < 10 order by pq.updated_at desc for update limit 1;
  created_new_queue := not found;
  if created_new_queue then insert into public.processing_queues(user_id,status,total_items) values(p_user_id,'draft',0) returning * into q; end if;
  insert into public.processing_queue_items(queue_id,user_id,position,input_payload,outreach_item_id,source_linkedin_post_url,source_author_name,source_author_profile_url,source_linkedin_post_text,source_job_description_url,source_job_description_text,capture_source,captured_at)
  values(q.id,p_user_id,q.total_items,p_metadata,o.id,o.linkedin_post_url,o.linkedin_author_name,o.linkedin_author_profile_url,o.linkedin_post_text,o.job_description_url,o.job_description_text,coalesce(p_metadata->>'capture_source','browser_extension'),(p_metadata->>'captured_at')::timestamptz) returning * into i;
  update public.processing_queues as pq set total_items=pq.total_items+1 where pq.id=q.id returning pq.status,pq.total_items into queue_status,queue_item_count;
  queue_id:=q.id; queue_item_id:=i.id; outreach_item_id:=o.id; return next;
end; $$;
revoke all on function public.repair_extension_orphaned_outreach(uuid,uuid,jsonb) from public, anon, authenticated;
grant execute on function public.repair_extension_orphaned_outreach(uuid,uuid,jsonb) to service_role;
notify pgrst, 'reload schema';
