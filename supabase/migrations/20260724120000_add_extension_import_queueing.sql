-- Step 10: server-side LinkedIn capture import.  Source data is retained on
-- the existing queue-item record; failed imports use a terminal queue and do
-- not consume a slot in an active processing queue.
alter table public.processing_queue_items
  add column if not exists source_linkedin_post_url text,
  add column if not exists source_author_name text,
  add column if not exists source_author_profile_url text,
  add column if not exists source_linkedin_post_text text,
  add column if not exists source_job_description_url text,
  add column if not exists source_job_description_text text,
  add column if not exists capture_source text,
  add column if not exists captured_at timestamptz,
  add column if not exists failure_stage text;

create index if not exists processing_queue_items_extension_source_idx
  on public.processing_queue_items(user_id, source_linkedin_post_url)
  where source_linkedin_post_url is not null and hidden_at is null;

create or replace function public.append_extension_processing_queue_item(
  p_user_id uuid, p_metadata jsonb
) returns table(queue_id uuid, queue_item_id uuid, queue_item_count integer,
                created_new_queue boolean, queue_status text)
language plpgsql security definer set search_path = public as $$
declare q public.processing_queues; i public.processing_queue_items;
begin
  -- One advisory lock per owner makes the capacity test and insert atomic,
  -- including the no-current-queue case.
  perform pg_advisory_xact_lock(hashtext(p_user_id::text));
  select * into q from public.processing_queues
   where user_id=p_user_id and status in ('draft','running','paused') and total_items < 10
   order by updated_at desc for update limit 1;
  created_new_queue := not found;
  if created_new_queue then
    insert into public.processing_queues(user_id, status, total_items)
      values (p_user_id, 'draft', 0) returning * into q;
  end if;
  insert into public.processing_queue_items(
    queue_id,user_id,position,input_payload,
    source_linkedin_post_url,source_author_name,source_author_profile_url,
    source_linkedin_post_text,source_job_description_url,source_job_description_text,
    capture_source,captured_at
  ) values (
    q.id,p_user_id,q.total_items,p_metadata,
    p_metadata->>'linkedin_post_url',p_metadata->>'author_name',p_metadata->>'author_profile_url',
    p_metadata->>'linkedin_post_text',p_metadata->>'job_description_url',p_metadata->>'job_description_text',
    coalesce(p_metadata->>'capture_source','browser_extension'),(p_metadata->>'captured_at')::timestamptz
  ) returning * into i;
  update public.processing_queues set total_items=total_items+1 where id=q.id returning status,total_items into queue_status,queue_item_count;
  queue_id := q.id; queue_item_id := i.id; return next;
end; $$;

create or replace function public.create_extension_failed_task(
  p_user_id uuid, p_metadata jsonb, p_reason text, p_stage text
) returns setof public.processing_queue_items
language plpgsql security definer set search_path = public as $$
declare q public.processing_queues; i public.processing_queue_items;
begin
  insert into public.processing_queues(user_id,status,total_items,failed_items,completed_at)
    values(p_user_id,'completed_with_failures',0,1,now()) returning * into q;
  insert into public.processing_queue_items(
    queue_id,user_id,position,status,input_payload,failure_status,failure_reason,failure_stage,completed_at,
    source_linkedin_post_url,source_author_name,source_author_profile_url,
    source_linkedin_post_text,source_job_description_url,source_job_description_text,capture_source,captured_at
  ) values (
    q.id,p_user_id,0,'failed',p_metadata,'failed',p_reason,p_stage,now(),
    p_metadata->>'linkedin_post_url',p_metadata->>'author_name',p_metadata->>'author_profile_url',
    p_metadata->>'linkedin_post_text',p_metadata->>'job_description_url',p_metadata->>'job_description_text',
    coalesce(p_metadata->>'capture_source','browser_extension'),(p_metadata->>'captured_at')::timestamptz
  ) returning * into i;
  return next i;
end; $$;

revoke all on function public.append_extension_processing_queue_item(uuid,jsonb), public.create_extension_failed_task(uuid,jsonb,text,text) from public, anon, authenticated;
grant execute on function public.append_extension_processing_queue_item(uuid,jsonb), public.create_extension_failed_task(uuid,jsonb,text,text) to service_role;
