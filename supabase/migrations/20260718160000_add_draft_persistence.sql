-- Step 3 draft persistence. Add only fields needed by the existing workflow.
alter table public.outreach_items
    add column if not exists recipient_name text,
    add column if not exists company_name text;

alter table public.generated_drafts
    add column if not exists draft_status text not null default 'draft'
        check (draft_status in ('draft', 'ready_for_review'));

create index if not exists generated_drafts_user_id_draft_status_updated_at_idx
    on public.generated_drafts (user_id, draft_status, updated_at desc);
