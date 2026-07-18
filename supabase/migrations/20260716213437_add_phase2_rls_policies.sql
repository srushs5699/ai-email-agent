-- Phase 2 ownership boundary. Browser clients use authenticated-role policies;
-- trusted backend work uses the Supabase service role and is never exposed to
-- frontend code.

alter table public.profiles enable row level security;
alter table public.resumes enable row level security;
alter table public.outreach_items enable row level security;
alter table public.generated_drafts enable row level security;
alter table public.ai_usage enable row level security;

-- Remove any default Data API access before granting only the required access.
revoke all on table public.profiles from public, anon, authenticated;
revoke all on table public.resumes from public, anon, authenticated;
revoke all on table public.outreach_items from public, anon, authenticated;
revoke all on table public.generated_drafts from public, anon, authenticated;
revoke all on table public.ai_usage from public, anon, authenticated;

grant select, insert, update, delete on table public.profiles to authenticated;
grant select, insert, update, delete on table public.resumes to authenticated;
grant select, insert, update, delete on table public.outreach_items to authenticated;
grant select, insert, update, delete on table public.generated_drafts to authenticated;
-- AI usage is written by trusted backend code only. Authenticated users may
-- inspect their own usage but cannot forge, alter, or remove audit records.
grant select on table public.ai_usage to authenticated;

-- Composite foreign keys make relationship ownership database-enforced rather
-- than relying on frontend filtering or RLS policy visibility alone.
alter table public.resumes
    add constraint resumes_id_user_id_key unique (id, user_id);

alter table public.outreach_items
    add constraint outreach_items_id_user_id_key unique (id, user_id),
    add constraint outreach_items_selected_resume_same_owner_fkey
        foreign key (selected_resume_id, user_id)
        references public.resumes (id, user_id) on delete restrict;

alter table public.generated_drafts
    add constraint generated_drafts_outreach_item_same_owner_fkey
        foreign key (outreach_item_id, user_id)
        references public.outreach_items (id, user_id) on delete cascade;

alter table public.ai_usage
    add constraint ai_usage_outreach_item_same_owner_fkey
        foreign key (outreach_item_id, user_id)
        references public.outreach_items (id, user_id) on delete restrict;

create policy profiles_select_own
on public.profiles
for select
to authenticated
using ((select auth.uid()) = id);

create policy profiles_insert_own
on public.profiles
for insert
to authenticated
with check ((select auth.uid()) = id);

create policy profiles_update_own
on public.profiles
for update
to authenticated
using ((select auth.uid()) = id)
with check ((select auth.uid()) = id);

create policy profiles_delete_own
on public.profiles
for delete
to authenticated
using ((select auth.uid()) = id);

create policy resumes_select_own
on public.resumes
for select
to authenticated
using ((select auth.uid()) = user_id);

create policy resumes_insert_own
on public.resumes
for insert
to authenticated
with check ((select auth.uid()) = user_id);

create policy resumes_update_own
on public.resumes
for update
to authenticated
using ((select auth.uid()) = user_id)
with check ((select auth.uid()) = user_id);

create policy resumes_delete_own
on public.resumes
for delete
to authenticated
using ((select auth.uid()) = user_id);

create policy outreach_items_select_own
on public.outreach_items
for select
to authenticated
using ((select auth.uid()) = user_id);

create policy outreach_items_insert_own
on public.outreach_items
for insert
to authenticated
with check ((select auth.uid()) = user_id);

create policy outreach_items_update_own
on public.outreach_items
for update
to authenticated
using ((select auth.uid()) = user_id)
with check ((select auth.uid()) = user_id);

create policy outreach_items_delete_own
on public.outreach_items
for delete
to authenticated
using ((select auth.uid()) = user_id);

create policy generated_drafts_select_own
on public.generated_drafts
for select
to authenticated
using ((select auth.uid()) = user_id);

create policy generated_drafts_insert_own
on public.generated_drafts
for insert
to authenticated
with check ((select auth.uid()) = user_id);

create policy generated_drafts_update_own
on public.generated_drafts
for update
to authenticated
using ((select auth.uid()) = user_id)
with check ((select auth.uid()) = user_id);

create policy generated_drafts_delete_own
on public.generated_drafts
for delete
to authenticated
using ((select auth.uid()) = user_id);

create policy ai_usage_select_own
on public.ai_usage
for select
to authenticated
using ((select auth.uid()) = user_id);
