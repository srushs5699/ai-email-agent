-- Step 10 follow-up: an extension capture is a real, partial outreach record
-- before it has the recipient/resume information needed for generation.
alter table public.outreach_items
  alter column recipient_to drop not null,
  drop constraint if exists outreach_items_status_check;
alter table public.outreach_items add constraint outreach_items_status_check
  check (status in ('captured','draft','ready','generating','generated','approved','rejected','failed'));
alter table public.processing_queue_items
  add column if not exists outreach_item_id uuid references public.outreach_items(id) on delete restrict;

drop function if exists public.append_extension_processing_queue_item(uuid, jsonb);

create function public.append_extension_processing_queue_item(
  p_user_id uuid, p_metadata jsonb
) returns table(queue_id uuid, queue_item_id uuid, outreach_item_id uuid,
                queue_item_count integer, created_new_queue boolean, queue_status text)
language plpgsql security definer set search_path = public as $$
declare q public.processing_queues; i public.processing_queue_items; o public.outreach_items;
begin
  perform pg_advisory_xact_lock(hashtext(p_user_id::text));
  -- The two inserts are in this RPC transaction: an error rolls both back.
  insert into public.outreach_items(
    user_id, linkedin_post_url, linkedin_author_name, linkedin_author_profile_url,
    linkedin_post_text, job_description_url, job_description_text,
    no_job_description, status
  ) values (
    p_user_id, p_metadata->>'linkedin_post_url', p_metadata->>'author_name',
    nullif(p_metadata->>'author_profile_url',''), p_metadata->>'linkedin_post_text',
    p_metadata->>'job_description_url', p_metadata->>'job_description_text', false, 'captured'
  ) returning * into o;
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
    p_metadata->>'linkedin_post_url',p_metadata->>'author_name',p_metadata->>'author_profile_url',
    p_metadata->>'linkedin_post_text',p_metadata->>'job_description_url',p_metadata->>'job_description_text',
    coalesce(p_metadata->>'capture_source','browser_extension'),(p_metadata->>'captured_at')::timestamptz
  ) returning * into i;
  update public.processing_queues set total_items=total_items+1 where id=q.id
    returning status,total_items into queue_status,queue_item_count;
  queue_id := q.id; queue_item_id := i.id; outreach_item_id := o.id; return next;
end; $$;

revoke all on function public.append_extension_processing_queue_item(uuid, jsonb)
  from public, anon, authenticated;
grant execute on function public.append_extension_processing_queue_item(uuid, jsonb)
  to service_role;
