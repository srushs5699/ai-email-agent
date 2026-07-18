begin;

create extension if not exists pgtap with schema extensions;
set local search_path = extensions, public, auth;

select plan(16);

insert into auth.users (id, email) values
    ('33333333-3333-3333-3333-333333333333', 'phase3-user-a@example.test'),
    ('44444444-4444-4444-4444-444444444444', 'phase3-user-b@example.test');

-- Storage fixtures use only bucket_id and name. They avoid setting deprecated
-- ownership columns that Storage manages internally in different versions.
insert into storage.objects (bucket_id, name) values
    (
        'resumes',
        '33333333-3333-3333-3333-333333333333/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1/user-a-resume.pdf'
    ),
    (
        'resumes',
        '33333333-3333-3333-3333-333333333333/bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbb2/delete-me.pdf'
    ),
    (
        'resumes',
        '44444444-4444-4444-4444-444444444444/cccccccc-cccc-cccc-cccc-ccccccccccc3/user-b-resume.pdf'
    );

insert into storage.buckets (id, name, public) values
    ('phase3-other-bucket', 'phase3-other-bucket', false);

select ok(
    exists (select 1 from storage.buckets where id = 'resumes'),
    'resumes bucket exists'
);
select ok(
    (select not public from storage.buckets where id = 'resumes'),
    'resumes bucket is private'
);
select ok(
    (select allowed_mime_types = array['application/pdf']::text[] from storage.buckets where id = 'resumes'),
    'resumes bucket allows only application/pdf'
);
select is(
    (select file_size_limit from storage.buckets where id = 'resumes'),
    10485760::bigint,
    'resumes bucket maximum size is 10 MB'
);
select is(
    (
        select count(*)
        from pg_policies
        where schemaname = 'storage'
          and tablename = 'objects'
          and policyname in (
              'resume_objects_select_own',
              'resume_objects_insert_own',
              'resume_objects_update_own',
              'resume_objects_delete_own'
          )
    ),
    4::bigint,
    'four resume-object ownership policies exist'
);
select ok(
    not exists (
        select 1
        from pg_policies
        where schemaname = 'storage'
          and tablename = 'objects'
          and policyname like 'resume_objects_%'
          and roles && array['anon']::name[]
    ),
    'no resume-object policy targets anon'
);

set local role authenticated;
set local "request.jwt.claim.sub" = '33333333-3333-3333-3333-333333333333';

select results_eq(
    $$select count(*) from storage.objects where bucket_id = 'resumes'$$,
    array[2::bigint],
    'User A can read only objects in User A path'
);
select lives_ok(
    $$insert into storage.objects (bucket_id, name) values (
        'resumes',
        '33333333-3333-3333-3333-333333333333/dddddddd-dddd-dddd-dddd-ddddddddddd4/new-resume.pdf'
    )$$,
    'User A can insert into User A path'
);
select results_eq(
    $$with changed as (
        update storage.objects
        set name = '33333333-3333-3333-3333-333333333333/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1/renamed-resume.pdf'
        where bucket_id = 'resumes'
          and name = '33333333-3333-3333-3333-333333333333/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1/user-a-resume.pdf'
        returning id
      ) select count(*) from changed$$,
    array[1::bigint],
    'User A can update within User A path'
);
select results_eq(
    $$with deleted as (
        delete from storage.objects
        where bucket_id = 'resumes'
          and name = '33333333-3333-3333-3333-333333333333/bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbb2/delete-me.pdf'
        returning id
      ) select count(*) from deleted$$,
    array[1::bigint],
    'User A can delete from User A path'
);
select is_empty(
    $$select 1 from storage.objects
      where bucket_id = 'resumes'
        and name = '44444444-4444-4444-4444-444444444444/cccccccc-cccc-cccc-cccc-ccccccccccc3/user-b-resume.pdf'$$,
    'User A cannot read User B object'
);
select results_eq(
    $$with changed as (
        update storage.objects
        set name = '44444444-4444-4444-4444-444444444444/cccccccc-cccc-cccc-cccc-ccccccccccc3/hacked.pdf'
        where bucket_id = 'resumes'
          and name = '44444444-4444-4444-4444-444444444444/cccccccc-cccc-cccc-cccc-ccccccccccc3/user-b-resume.pdf'
        returning id
      ) select count(*) from changed$$,
    array[0::bigint],
    'User A cannot update User B object'
);
select results_eq(
    $$with deleted as (
        delete from storage.objects
        where bucket_id = 'resumes'
          and name = '44444444-4444-4444-4444-444444444444/cccccccc-cccc-cccc-cccc-ccccccccccc3/user-b-resume.pdf'
        returning id
      ) select count(*) from deleted$$,
    array[0::bigint],
    'User A cannot delete User B object'
);
select throws_ok(
    $$insert into storage.objects (bucket_id, name) values (
        'resumes',
        '44444444-4444-4444-4444-444444444444/eeeeeeee-eeee-eeee-eeee-eeeeeeeeeee5/forbidden.pdf'
    )$$,
    '42501',
    null,
    'User A cannot insert into User B path'
);
select throws_ok(
    $$update storage.objects
      set name = '44444444-4444-4444-4444-444444444444/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1/forbidden-move.pdf'
      where bucket_id = 'resumes'
        and name = '33333333-3333-3333-3333-333333333333/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1/renamed-resume.pdf'$$,
    '42501',
    null,
    'User A cannot move an object into User B path'
);
select throws_ok(
    $$insert into storage.objects (bucket_id, name) values (
        'phase3-other-bucket',
        '33333333-3333-3333-3333-333333333333/ffffffff-ffff-ffff-ffff-fffffffffff6/not-allowed.pdf'
    )$$,
    '42501',
    null,
    'resume-object policies do not allow another bucket'
);

select * from finish();
rollback;
