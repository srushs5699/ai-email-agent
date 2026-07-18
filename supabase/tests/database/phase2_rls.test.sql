begin;

create extension if not exists pgtap with schema extensions;
set local search_path = extensions, public, auth;

select plan(42);

-- Local-only fixture users and rows. The enclosing transaction is rolled back
-- by pgTAP, so no test user or application data persists.
insert into auth.users (id, email) values
    ('11111111-1111-1111-1111-111111111111', 'phase2-user-a@example.test'),
    ('22222222-2222-2222-2222-222222222222', 'phase2-user-b@example.test');

insert into public.profiles (id, email, display_name) values
    ('11111111-1111-1111-1111-111111111111', 'phase2-user-a@example.test', 'User A'),
    ('22222222-2222-2222-2222-222222222222', 'phase2-user-b@example.test', 'User B');

insert into public.resumes (
    id, user_id, name, storage_path, mime_type, file_size_bytes, parse_status
) values
    (
        'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1',
        '11111111-1111-1111-1111-111111111111',
        'User A resume',
        'test/user-a.pdf',
        'application/pdf',
        1,
        'completed'
    ),
    (
        'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbb2',
        '22222222-2222-2222-2222-222222222222',
        'User B resume',
        'test/user-b.pdf',
        'application/pdf',
        1,
        'completed'
    );

insert into public.outreach_items (
    id,
    user_id,
    job_description_text,
    recipient_to,
    selected_resume_id
) values
    (
        'cccccccc-cccc-cccc-cccc-ccccccccccc1',
        '11111111-1111-1111-1111-111111111111',
        'User A job description',
        'recipient-a@example.test',
        'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1'
    ),
    (
        'dddddddd-dddd-dddd-dddd-ddddddddddd2',
        '22222222-2222-2222-2222-222222222222',
        'User B job description',
        'recipient-b@example.test',
        'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbb2'
    );

insert into public.generated_drafts (
    id, user_id, outreach_item_id, subject, body, generation_status
) values
    (
        'eeeeeeee-eeee-eeee-eeee-eeeeeeeeeee1',
        '11111111-1111-1111-1111-111111111111',
        'cccccccc-cccc-cccc-cccc-ccccccccccc1',
        'User A subject',
        'User A body',
        'completed'
    ),
    (
        'ffffffff-ffff-ffff-ffff-fffffffffff2',
        '22222222-2222-2222-2222-222222222222',
        'dddddddd-dddd-dddd-dddd-ddddddddddd2',
        'User B subject',
        'User B body',
        'completed'
    );

insert into public.ai_usage (
    id, user_id, outreach_item_id, model, input_tokens, output_tokens
) values
    (
        '99999999-9999-9999-9999-999999999991',
        '11111111-1111-1111-1111-111111111111',
        'cccccccc-cccc-cccc-cccc-ccccccccccc1',
        'test-model',
        1,
        1
    ),
    (
        '88888888-8888-8888-8888-888888888882',
        '22222222-2222-2222-2222-222222222222',
        'dddddddd-dddd-dddd-dddd-ddddddddddd2',
        'test-model',
        1,
        1
    );

select ok((select relrowsecurity from pg_class where oid = 'public.profiles'::regclass), 'profiles has RLS enabled');
select ok((select relrowsecurity from pg_class where oid = 'public.resumes'::regclass), 'resumes has RLS enabled');
select ok((select relrowsecurity from pg_class where oid = 'public.outreach_items'::regclass), 'outreach_items has RLS enabled');
select ok((select relrowsecurity from pg_class where oid = 'public.generated_drafts'::regclass), 'generated_drafts has RLS enabled');
select ok((select relrowsecurity from pg_class where oid = 'public.ai_usage'::regclass), 'ai_usage has RLS enabled');

select ok(
    not has_table_privilege('anon', 'public.profiles', 'select')
    and not has_table_privilege('anon', 'public.resumes', 'select')
    and not has_table_privilege('anon', 'public.outreach_items', 'select')
    and not has_table_privilege('anon', 'public.generated_drafts', 'select')
    and not has_table_privilege('anon', 'public.ai_usage', 'select'),
    'anon cannot select user-owned tables'
);
select ok(
    not has_table_privilege('anon', 'public.profiles', 'insert')
    and not has_table_privilege('anon', 'public.resumes', 'insert')
    and not has_table_privilege('anon', 'public.outreach_items', 'insert')
    and not has_table_privilege('anon', 'public.generated_drafts', 'insert')
    and not has_table_privilege('anon', 'public.ai_usage', 'insert'),
    'anon cannot insert user-owned rows'
);
select ok(
    not has_table_privilege('anon', 'public.profiles', 'update')
    and not has_table_privilege('anon', 'public.resumes', 'update')
    and not has_table_privilege('anon', 'public.outreach_items', 'update')
    and not has_table_privilege('anon', 'public.generated_drafts', 'update')
    and not has_table_privilege('anon', 'public.ai_usage', 'update'),
    'anon cannot update user-owned rows'
);
select ok(
    not has_table_privilege('anon', 'public.profiles', 'delete')
    and not has_table_privilege('anon', 'public.resumes', 'delete')
    and not has_table_privilege('anon', 'public.outreach_items', 'delete')
    and not has_table_privilege('anon', 'public.generated_drafts', 'delete')
    and not has_table_privilege('anon', 'public.ai_usage', 'delete'),
    'anon cannot delete user-owned rows'
);

set local role anon;
select throws_ok(
    $$select * from public.profiles$$,
    '42501',
    null,
    'Anonymous users are denied select access'
);
select throws_ok(
    $$insert into public.profiles (id, email) values ('11111111-1111-1111-1111-111111111111', 'denied@example.test')$$,
    '42501',
    null,
    'Anonymous users are denied insert access'
);
select throws_ok(
    $$update public.profiles set display_name = 'Denied'$$,
    '42501',
    null,
    'Anonymous users are denied update access'
);
select throws_ok(
    $$delete from public.profiles$$,
    '42501',
    null,
    'Anonymous users are denied delete access'
);

set local role authenticated;
set local "request.jwt.claim.sub" = '11111111-1111-1111-1111-111111111111';

select results_eq(
    'select id from public.profiles',
    array['11111111-1111-1111-1111-111111111111'::uuid],
    'User A can select only their profile'
);
select results_eq(
    $$with changed as (
        update public.profiles set display_name = 'Updated User A'
        where id = '11111111-1111-1111-1111-111111111111'::uuid returning id
      ) select count(*) from changed$$,
    array[1::bigint],
    'User A can update their profile without changing its owner ID'
);
select lives_ok(
    $$insert into public.resumes (user_id, name, storage_path, mime_type, file_size_bytes)
      values ('11111111-1111-1111-1111-111111111111', 'New resume', 'test/new.pdf', 'application/pdf', 1)$$,
    'User A can insert a resume they own'
);
select results_eq(
    $$select count(*) from public.resumes where user_id = '11111111-1111-1111-1111-111111111111'::uuid$$,
    array[2::bigint],
    'User A can select their resumes'
);
select results_eq(
    $$with changed as (
        update public.resumes set name = 'Updated resume'
        where id = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1'::uuid returning id
      ) select count(*) from changed$$,
    array[1::bigint],
    'User A can update their resume'
);
select lives_ok(
    $$delete from public.resumes where name = 'New resume'$$,
    'User A can delete their unreferenced resume'
);
select lives_ok(
    $$insert into public.outreach_items (user_id, job_description_text, recipient_to, selected_resume_id)
      values ('11111111-1111-1111-1111-111111111111', 'Another job description', 'new-recipient@example.test', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1')$$,
    'User A can insert an outreach item with their resume'
);
select results_eq(
    $$select count(*) from public.outreach_items where user_id = '11111111-1111-1111-1111-111111111111'::uuid$$,
    array[2::bigint],
    'User A can select their outreach items'
);
select lives_ok(
    $$insert into public.generated_drafts (user_id, outreach_item_id, subject, body, generation_status)
      values ('11111111-1111-1111-1111-111111111111', 'cccccccc-cccc-cccc-cccc-ccccccccccc1', 'New subject', 'New body', 'completed')$$,
    'User A can insert a draft for their outreach item'
);
select results_eq(
    $$select count(*) from public.generated_drafts where user_id = '11111111-1111-1111-1111-111111111111'::uuid$$,
    array[2::bigint],
    'User A can select their drafts'
);
select results_eq(
    $$select count(*) from public.ai_usage$$,
    array[1::bigint],
    'User A can read only their AI usage'
);

select is_empty(
    $$select 1 from public.profiles where id = '22222222-2222-2222-2222-222222222222'::uuid$$,
    'User A cannot select User B profile'
);
select is_empty(
    $$select 1 from public.resumes where id = 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbb2'::uuid$$,
    'User A cannot select User B resume'
);
select results_eq(
    $$with changed as (
        update public.resumes set name = 'Hacked' where id = 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbb2'::uuid returning id
      ) select count(*) from changed$$,
    array[0::bigint],
    'User A cannot update User B resume'
);
select results_eq(
    $$with deleted as (
        delete from public.resumes where id = 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbb2'::uuid returning id
      ) select count(*) from deleted$$,
    array[0::bigint],
    'User A cannot delete User B resume'
);
select is_empty(
    $$select 1 from public.outreach_items where id = 'dddddddd-dddd-dddd-dddd-ddddddddddd2'::uuid$$,
    'User A cannot select User B outreach item'
);
select results_eq(
    $$with changed as (
        update public.outreach_items set recipient_to = 'hacked@example.test'
        where id = 'dddddddd-dddd-dddd-dddd-ddddddddddd2'::uuid returning id
      ) select count(*) from changed$$,
    array[0::bigint],
    'User A cannot update User B outreach item'
);
select results_eq(
    $$with deleted as (
        delete from public.outreach_items where id = 'dddddddd-dddd-dddd-dddd-ddddddddddd2'::uuid returning id
      ) select count(*) from deleted$$,
    array[0::bigint],
    'User A cannot delete User B outreach item'
);
select is_empty(
    $$select 1 from public.generated_drafts where id = 'ffffffff-ffff-ffff-ffff-fffffffffff2'::uuid$$,
    'User A cannot select User B draft'
);
select results_eq(
    $$with changed as (
        update public.generated_drafts set subject = 'Hacked'
        where id = 'ffffffff-ffff-ffff-ffff-fffffffffff2'::uuid returning id
      ) select count(*) from changed$$,
    array[0::bigint],
    'User A cannot update User B draft'
);
select results_eq(
    $$with deleted as (
        delete from public.generated_drafts where id = 'ffffffff-ffff-ffff-ffff-fffffffffff2'::uuid returning id
      ) select count(*) from deleted$$,
    array[0::bigint],
    'User A cannot delete User B draft'
);
select is_empty(
    $$select 1 from public.ai_usage where id = '88888888-8888-8888-8888-888888888882'::uuid$$,
    'User A cannot read User B AI usage'
);

select throws_ok(
    $$update public.resumes set user_id = '22222222-2222-2222-2222-222222222222'::uuid
      where id = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1'::uuid$$,
    '42501',
    null,
    'User A cannot transfer resume ownership to User B'
);
select throws_ok(
    $$insert into public.outreach_items (user_id, job_description_text, recipient_to, selected_resume_id)
      values ('11111111-1111-1111-1111-111111111111', 'Invalid relationship', 'recipient@example.test', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbb2')$$,
    '23503',
    null,
    'User A cannot create outreach item with User B resume'
);
select throws_ok(
    $$insert into public.generated_drafts (user_id, outreach_item_id, subject, body, generation_status)
      values ('11111111-1111-1111-1111-111111111111', 'dddddddd-dddd-dddd-dddd-ddddddddddd2', 'Invalid', 'Invalid', 'completed')$$,
    '23503',
    null,
    'User A cannot create draft linked to User B outreach item'
);
select throws_ok(
    $$update public.outreach_items set selected_resume_id = 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbb2'::uuid
      where id = 'cccccccc-cccc-cccc-cccc-ccccccccccc1'::uuid$$,
    '23503',
    null,
    'User A cannot point their outreach item at User B resume'
);
select throws_ok(
    $$update public.generated_drafts set outreach_item_id = 'dddddddd-dddd-dddd-dddd-ddddddddddd2'::uuid
      where id = 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeeee1'::uuid$$,
    '23503',
    null,
    'User A cannot point their draft at User B outreach item'
);
select ok(
    not has_table_privilege('authenticated', 'public.ai_usage', 'insert')
    and not has_table_privilege('authenticated', 'public.ai_usage', 'update')
    and not has_table_privilege('authenticated', 'public.ai_usage', 'delete'),
    'Authenticated users cannot forge, alter, or delete AI usage records'
);
select lives_ok(
    $$delete from public.profiles where id = '11111111-1111-1111-1111-111111111111'::uuid$$,
    'User A can delete their own profile'
);

select * from finish();
rollback;
