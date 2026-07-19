-- Step 6: persistent, user-owned sequential processing queues.
create table public.processing_queues (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    status text not null default 'draft'
        check (status in ('draft', 'running', 'paused', 'completed', 'completed_with_failures')),
    total_items integer not null default 0 check (total_items between 0 and 10),
    completed_items integer not null default 0 check (completed_items >= 0),
    failed_items integer not null default 0 check (failed_items >= 0),
    created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
    started_at timestamptz, paused_at timestamptz, completed_at timestamptz
);
create table public.processing_queue_items (
    id uuid primary key default gen_random_uuid(),
    queue_id uuid not null references public.processing_queues(id) on delete cascade,
    user_id uuid not null references auth.users(id) on delete cascade,
    position integer not null check (position >= 0),
    status text not null default 'pending' check (status in ('pending', 'processing', 'completed', 'failed')),
    input_payload jsonb not null,
    generated_draft_id uuid references public.generated_drafts(id) on delete restrict,
    error_code text, created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
    started_at timestamptz, completed_at timestamptz, processing_lease_expires_at timestamptz,
    unique(queue_id, position)
);
create index processing_queues_user_status_updated_idx on public.processing_queues(user_id, status, updated_at desc);
create index processing_queue_items_queue_position_idx on public.processing_queue_items(queue_id, position);

create trigger processing_queues_set_updated_at before update on public.processing_queues for each row execute function public.set_updated_at();
create trigger processing_queue_items_set_updated_at before update on public.processing_queue_items for each row execute function public.set_updated_at();

alter table public.processing_queues enable row level security;
alter table public.processing_queue_items enable row level security;
create policy processing_queues_owner on public.processing_queues for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy processing_queue_items_owner on public.processing_queue_items for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- Claims one ordered item only while the queue is running. The lease makes a
-- backend interruption recoverable after five minutes without duplicate work.
create or replace function public.claim_next_processing_queue_item(p_queue_id uuid, p_user_id uuid)
returns setof public.processing_queue_items language plpgsql security definer set search_path = public as $$
declare v_item public.processing_queue_items;
begin
  select i.* into v_item from public.processing_queue_items i join public.processing_queues q on q.id=i.queue_id
   where i.queue_id=p_queue_id and i.user_id=p_user_id and q.user_id=p_user_id and q.status='running' and i.status='pending'
   order by i.position for update skip locked limit 1;
  if not found then return; end if;
  update public.processing_queue_items set status='processing', started_at=now(), processing_lease_expires_at=now()+interval '5 minutes', error_code=null where id=v_item.id returning * into v_item;
  return next v_item;
end; $$;

create or replace function public.recover_stale_processing_queue_items(p_queue_id uuid, p_user_id uuid)
returns void language plpgsql security definer set search_path = public as $$
begin
 update public.processing_queue_items i set status=case when exists (select 1 from public.generated_drafts d where d.id=i.generated_draft_id and d.user_id=p_user_id) then 'completed' else 'pending' end,
  completed_at=case when exists (select 1 from public.generated_drafts d where d.id=i.generated_draft_id and d.user_id=p_user_id) then now() else null end, processing_lease_expires_at=null
 where i.queue_id=p_queue_id and i.user_id=p_user_id and i.status='processing' and i.processing_lease_expires_at < now();
end; $$;
revoke all on function public.claim_next_processing_queue_item(uuid,uuid), public.recover_stale_processing_queue_items(uuid,uuid) from public, anon, authenticated;
grant execute on function public.claim_next_processing_queue_item(uuid,uuid), public.recover_stale_processing_queue_items(uuid,uuid) to service_role;
