-- Phase 3 private resume storage foundation. The byte limit is intentionally
-- defined once here so the bucket configuration is consistent on reruns.
with resume_bucket_config as (
    select
        'resumes'::text as bucket_id,
        10485760::bigint as max_upload_bytes
)
insert into storage.buckets (
    id,
    name,
    public,
    file_size_limit,
    allowed_mime_types
)
select
    bucket_id,
    bucket_id,
    false,
    max_upload_bytes,
    array['application/pdf']::text[]
from resume_bucket_config
on conflict (id) do update set
    public = excluded.public,
    file_size_limit = excluded.file_size_limit,
    allowed_mime_types = excluded.allowed_mime_types;

-- These policies intentionally scope every object to:
-- <authenticated-user-id>/<resume-id>/<sanitized-filename>.pdf
drop policy if exists resume_objects_select_own on storage.objects;
drop policy if exists resume_objects_insert_own on storage.objects;
drop policy if exists resume_objects_update_own on storage.objects;
drop policy if exists resume_objects_delete_own on storage.objects;

create policy resume_objects_select_own
on storage.objects
for select
to authenticated
using (
    bucket_id = 'resumes'
    and array_length(storage.foldername(name), 1) = 2
    and (storage.foldername(name))[1] = (select auth.uid())::text
    and (storage.foldername(name))[2] ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
    and lower(storage.extension(name)) = 'pdf'
);

create policy resume_objects_insert_own
on storage.objects
for insert
to authenticated
with check (
    bucket_id = 'resumes'
    and array_length(storage.foldername(name), 1) = 2
    and (storage.foldername(name))[1] = (select auth.uid())::text
    and (storage.foldername(name))[2] ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
    and lower(storage.extension(name)) = 'pdf'
);

create policy resume_objects_update_own
on storage.objects
for update
to authenticated
using (
    bucket_id = 'resumes'
    and array_length(storage.foldername(name), 1) = 2
    and (storage.foldername(name))[1] = (select auth.uid())::text
    and (storage.foldername(name))[2] ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
    and lower(storage.extension(name)) = 'pdf'
)
with check (
    bucket_id = 'resumes'
    and array_length(storage.foldername(name), 1) = 2
    and (storage.foldername(name))[1] = (select auth.uid())::text
    and (storage.foldername(name))[2] ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
    and lower(storage.extension(name)) = 'pdf'
);

create policy resume_objects_delete_own
on storage.objects
for delete
to authenticated
using (
    bucket_id = 'resumes'
    and array_length(storage.foldername(name), 1) = 2
    and (storage.foldername(name))[1] = (select auth.uid())::text
    and (storage.foldername(name))[2] ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
    and lower(storage.extension(name)) = 'pdf'
);

-- Supabase Storage grants authenticated access at the table level. These RLS
-- policies restrict it to the resumes bucket and caller-owned object paths.
grant select, insert, update, delete on storage.objects to authenticated;
