-- Step 5: explicit approval and atomically claimed Gmail sends.
alter table public.generated_drafts
    add column if not exists approved_at timestamptz,
    add column if not exists approved_content_hash text,
    add column if not exists send_status text not null default 'not_sent'
        check (send_status in ('not_sent', 'sending', 'failed', 'sent')),
    add column if not exists send_started_at timestamptz,
    add column if not exists sent_at timestamptz,
    add column if not exists gmail_sent_message_id text,
    add column if not exists send_error_code text;

alter table public.generated_drafts
    drop constraint if exists generated_drafts_draft_status_check;
alter table public.generated_drafts
    add constraint generated_drafts_draft_status_check
        check (draft_status in ('draft', 'ready_for_review', 'sent'));

create index if not exists generated_drafts_user_id_send_status_updated_at_idx
    on public.generated_drafts (user_id, send_status, updated_at desc);

-- The backend supplies a deterministic hash after loading the owned row. This
-- compare-and-set claim prevents a second concurrent request from calling Gmail.
create or replace function public.claim_approved_gmail_send(p_draft_id uuid, p_user_id uuid, p_content_hash text)
returns setof public.generated_drafts
language sql
security definer
set search_path = public
as $$
    update public.generated_drafts
       set send_status = 'sending', send_started_at = now(), send_error_code = null
     where id = p_draft_id
       and user_id = p_user_id
       and send_status in ('not_sent', 'failed')
       and approval_status = 'approved'
       and approved_content_hash = p_content_hash
       and gmail_draft_id is not null
       and gmail_sync_status = 'synced'
     returning *;
$$;

revoke all on function public.claim_approved_gmail_send(uuid, uuid, text) from public, anon, authenticated;
grant execute on function public.claim_approved_gmail_send(uuid, uuid, text) to service_role;
