-- Phase 2 foundation schema. Row Level Security and ownership policies are
-- intentionally deferred to the next dedicated migration.

create extension if not exists pgcrypto;

create table public.profiles (
    id uuid primary key references auth.users (id) on delete cascade,
    email text not null unique,
    display_name text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table public.resumes (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users (id) on delete cascade,
    name text not null,
    storage_path text not null,
    mime_type text not null,
    file_size_bytes bigint not null check (file_size_bytes >= 0),
    extracted_text text,
    parse_status text not null default 'pending'
        check (parse_status in ('pending', 'processing', 'completed', 'failed')),
    parse_error text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index resumes_user_id_created_at_idx
    on public.resumes (user_id, created_at desc);

create index resumes_user_id_parse_status_idx
    on public.resumes (user_id, parse_status);

create table public.outreach_items (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users (id) on delete cascade,
    linkedin_post_url text,
    linkedin_author_name text,
    linkedin_author_profile_url text,
    linkedin_post_text text,
    job_description_url text,
    job_description_text text,
    no_job_description boolean not null default false,
    recipient_to text not null,
    recipient_cc text,
    recipient_verification_status text not null default 'unverified'
        check (recipient_verification_status in ('unverified', 'verified', 'failed')),
    -- Restrict deletion of a selected resume so an outreach item never loses
    -- its resume relationship unexpectedly.
    selected_resume_id uuid references public.resumes (id) on delete restrict,
    status text not null default 'draft'
        check (
            status in (
                'draft',
                'ready',
                'generating',
                'generated',
                'approved',
                'rejected',
                'failed'
            )
        ),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint outreach_items_job_description_state_check check (
        no_job_description
        or nullif(btrim(job_description_text), '') is not null
    )
);

create index outreach_items_user_id_created_at_idx
    on public.outreach_items (user_id, created_at desc);

create index outreach_items_user_id_status_idx
    on public.outreach_items (user_id, status);

create index outreach_items_selected_resume_id_idx
    on public.outreach_items (selected_resume_id);

create table public.generated_drafts (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users (id) on delete cascade,
    -- Drafts are dependent workflow artifacts and are removed with their
    -- outreach item; AI usage records intentionally use restrict instead.
    outreach_item_id uuid not null references public.outreach_items (id)
        on delete cascade,
    subject text,
    body text,
    selected_experience_points jsonb not null default '[]'::jsonb,
    fallback_linkedin_message text,
    generation_status text not null default 'pending'
        check (generation_status in ('pending', 'generating', 'completed', 'failed')),
    approval_status text not null default 'pending'
        check (approval_status in ('pending', 'approved', 'rejected')),
    simulated_gmail_status text not null default 'not_started'
        check (simulated_gmail_status in ('not_started', 'created', 'failed')),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint generated_drafts_completed_content_check check (
        generation_status <> 'completed'
        or (
            nullif(btrim(subject), '') is not null
            and nullif(btrim(body), '') is not null
        )
    )
);

create index generated_drafts_user_id_created_at_idx
    on public.generated_drafts (user_id, created_at desc);

create index generated_drafts_outreach_item_id_idx
    on public.generated_drafts (outreach_item_id);

create table public.ai_usage (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users (id) on delete cascade,
    -- Retain AI usage as an audit record by preventing an outreach item from
    -- being deleted while usage records reference it.
    outreach_item_id uuid not null references public.outreach_items (id)
        on delete restrict,
    model text not null,
    input_tokens integer not null check (input_tokens >= 0),
    output_tokens integer not null check (output_tokens >= 0),
    estimated_cost_usd numeric(12, 6) not null default 0
        check (estimated_cost_usd >= 0),
    request_status text not null default 'pending'
        check (request_status in ('pending', 'completed', 'failed', 'blocked_budget')),
    created_at timestamptz not null default now()
);

create index ai_usage_user_id_created_at_idx
    on public.ai_usage (user_id, created_at desc);

create index ai_usage_outreach_item_id_idx
    on public.ai_usage (outreach_item_id);

create or replace function public.set_updated_at()
returns trigger
language plpgsql
set search_path = public
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

drop trigger if exists profiles_set_updated_at on public.profiles;
create trigger profiles_set_updated_at
before update on public.profiles
for each row execute function public.set_updated_at();

drop trigger if exists resumes_set_updated_at on public.resumes;
create trigger resumes_set_updated_at
before update on public.resumes
for each row execute function public.set_updated_at();

drop trigger if exists outreach_items_set_updated_at on public.outreach_items;
create trigger outreach_items_set_updated_at
before update on public.outreach_items
for each row execute function public.set_updated_at();

drop trigger if exists generated_drafts_set_updated_at on public.generated_drafts;
create trigger generated_drafts_set_updated_at
before update on public.generated_drafts
for each row execute function public.set_updated_at();
