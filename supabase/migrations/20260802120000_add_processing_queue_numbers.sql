-- Stable per-user display numbers; UUIDs remain the operational identifiers.
alter table public.processing_queues add column if not exists queue_number bigint;

with numbered as (
  select id, row_number() over (
    partition by user_id order by created_at asc, id asc
  ) as queue_number
  from public.processing_queues
)
update public.processing_queues queue
set queue_number = numbered.queue_number
from numbered
where queue.id = numbered.id and queue.queue_number is null;

create table if not exists public.processing_queue_number_counters (
  user_id uuid primary key references auth.users(id) on delete cascade,
  next_queue_number bigint not null check (next_queue_number > 0)
);

insert into public.processing_queue_number_counters(user_id, next_queue_number)
select user_id, coalesce(max(queue_number), 0) + 1
from public.processing_queues
group by user_id
on conflict (user_id) do update
set next_queue_number = greatest(
  public.processing_queue_number_counters.next_queue_number,
  excluded.next_queue_number
);

create or replace function public.assign_processing_queue_number()
returns trigger language plpgsql security definer set search_path = public as $$
declare allocated_number bigint;
begin
  if new.queue_number is not null then return new; end if;
  insert into public.processing_queue_number_counters(user_id, next_queue_number)
  values (new.user_id, 2)
  on conflict (user_id) do update
  set next_queue_number = public.processing_queue_number_counters.next_queue_number + 1
  returning next_queue_number - 1 into allocated_number;
  new.queue_number := allocated_number;
  return new;
end; $$;

drop trigger if exists processing_queues_assign_number on public.processing_queues;
create trigger processing_queues_assign_number
before insert on public.processing_queues
for each row execute function public.assign_processing_queue_number();

alter table public.processing_queues alter column queue_number set not null;
create unique index if not exists processing_queues_user_queue_number_key
  on public.processing_queues(user_id, queue_number);
