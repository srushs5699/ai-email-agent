-- Step 10: terminal extension failures must be visible to Failed Tasks before
-- the import endpoint is allowed to report a failedTaskId.
drop function if exists public.create_extension_failed_task(uuid, jsonb, text, text);

create function public.create_extension_failed_task(
  p_user_id uuid, p_metadata jsonb, p_reason text, p_stage text
) returns table(id uuid, queue_id uuid, user_id uuid, status text,
                failure_status text, failure_reason text, failure_stage text,
                hidden_at timestamptz)
language plpgsql security definer set search_path = public as $$
declare q public.processing_queues; i public.processing_queue_items;
begin
  -- This function is a single transaction.  There is no exception handler:
  -- either both queue and failed item commit, or this function reports failure.
  insert into public.processing_queues(user_id,status,total_items,failed_items,completed_at)
    values(p_user_id,'completed_with_failures',1,1,now()) returning * into q;
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
  return query select i.id,i.queue_id,i.user_id,i.status,i.failure_status,i.failure_reason,i.failure_stage,i.hidden_at;
end; $$;

revoke all on function public.create_extension_failed_task(uuid, jsonb, text, text)
  from public, anon, authenticated;
grant execute on function public.create_extension_failed_task(uuid, jsonb, text, text)
  to service_role;
