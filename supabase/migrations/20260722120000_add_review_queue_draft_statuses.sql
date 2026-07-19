-- Step 7: retain rejected/deleted draft history while excluding it from review.
alter table public.generated_drafts
    drop constraint if exists generated_drafts_draft_status_check;
alter table public.generated_drafts
    add constraint generated_drafts_draft_status_check
        check (draft_status in ('draft', 'ready_for_review', 'sent', 'rejected', 'deleted'));
