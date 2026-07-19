create schema if not exists private;

create table private.gmail_connections (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null unique references auth.users(id) on delete cascade,
    google_email text,
    encrypted_refresh_token text not null,
    access_token text,
    access_token_expires_at timestamptz,
    granted_scopes text[] not null default '{}',
    revoked_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table private.gmail_oauth_states (
    state_hash text primary key,
    user_id uuid not null references auth.users(id) on delete cascade,
    expires_at timestamptz not null,
    created_at timestamptz not null default now()
);

alter table public.generated_drafts
    add column if not exists gmail_draft_id text,
    add column if not exists gmail_message_id text,
    add column if not exists gmail_sync_status text not null default 'not_created'
        check (gmail_sync_status in ('not_created','creating','synced','syncing','sync_failed','authorization_required')),
    add column if not exists gmail_last_synced_at timestamptz,
    add column if not exists gmail_sync_error_code text;

alter table private.gmail_connections enable row level security;
alter table private.gmail_oauth_states enable row level security;
revoke all on schema private from public, anon, authenticated;
revoke all on table private.gmail_connections, private.gmail_oauth_states from public, anon, authenticated;
grant usage on schema private to service_role;
grant select, insert, update, delete on table private.gmail_connections, private.gmail_oauth_states to service_role;
create index gmail_oauth_states_expires_at_idx on private.gmail_oauth_states(expires_at);
create index generated_drafts_gmail_draft_id_idx on public.generated_drafts(gmail_draft_id) where gmail_draft_id is not null;
