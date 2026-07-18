# AI Email Agent — Step 5, Phase 2 Progress Update

## Current Phase

**Step 5 — Phase 2: Supabase Foundation and Google Authentication**

**Status:** Complete — implementation, automated checks, browser/API acceptance,
and hosted Supabase schema/RLS verification are confirmed.

---

## Completed So Far

### Supabase Project

- Created the Supabase project.
- Confirmed the project is healthy.
- Collected the Supabase project URL and publishable key.
- Added the Supabase URL and publishable key to:

```text
app/frontend/.env.local
```

- Confirmed `.env.local` is ignored by Git.

### Google Authentication Configuration

- Created the Google OAuth consent configuration.
- Selected the external audience.
- Created a Google OAuth Web Application client.
- Added the local frontend origin:

```text
http://localhost:5173
```

- Added the Supabase OAuth callback URL to Google Cloud.
- Connected the Google OAuth client ID and client secret to Supabase.
- Enabled Google as an authentication provider in Supabase.
- Configured the Supabase Site URL:

```text
http://localhost:5173
```

- Added the allowed local redirect URL:

```text
http://localhost:5173/auth/callback
```

### Frontend Supabase Setup

- Installed:

```text
@supabase/supabase-js@2.110.7
```

- Installed the required runtime dependency:

```text
tslib@2.8.1
```

- Created the Supabase client file:

```text
app/frontend/src/lib/supabase.ts
```

- Added environment-variable validation for:

```text
VITE_SUPABASE_URL
VITE_SUPABASE_PUBLISHABLE_KEY
```

### Frontend Authentication Component

- Created:

```text
app/frontend/src/components/AuthStatus.tsx
```

- Added:
  - Supabase session restoration
  - Authentication-state listener
  - Google sign-in action
  - Local sign-out action
  - Loading state
  - Authentication error display
  - Signed-in user email display

- Updated:

```text
app/frontend/src/App.tsx
```

- Preserved the existing backend health-status component.

### Dependency Issue Resolved

The frontend tests initially failed with:

```text
Cannot find module 'tslib'
```

Although npm listed `tslib`, the physical package directory was missing.

The issue was resolved by:

1. Removing the generated `node_modules` directory.
2. Reinstalling dependencies from `package-lock.json` using `npm ci`.
3. Confirming Node could resolve `tslib`.
4. Rerunning the frontend tests.

---

## Confirmed Passing Checks

The following frontend checks are currently passing:

```text
npm run typecheck
npm run lint
npm run test
```

---

## Current Implementation State

Google OAuth is configured in both Google Cloud and Supabase. Frontend login,
redirect handling, session persistence across refreshes and tabs, sign-out, and
protected routes are complete and verified.

The backend JWT verifier and protected test endpoint are complete. The initial
schema and dedicated RLS migrations are version controlled, applied manually to
the hosted Supabase project through the SQL Editor, and verified there. Local
same-user and cross-user ownership testing is confirmed complete.

---

## Immediate Next Step

The next phase is **Phase 3 — Resume Library and PDF Processing**. Phase 3 is
not implemented as part of this Phase 2 completion update.

---

## Important Security Notes

- Do not commit `.env.local`.
- Do not commit the downloaded Google OAuth JSON file.
- Do not expose the Google client secret in frontend code.
- Do not expose a Supabase secret or service-role key in the frontend.
- Continue using only the Supabase publishable key in the React application.

---

## Backend JWT Verification Update

### Verification Approach

- The configured Supabase project was checked through its public JWKS endpoint.
- It currently publishes an **ES256** signing key, so the backend uses JWKS-based
  verification through PyJWT's `PyJWKClient`.
- The JWKS client caches the key set for five minutes and caches resolved keys;
  keys are not fetched for every protected request.
- The verifier checks the signature, expiration, issuer
  (`<SUPABASE_URL>/auth/v1`), configured audience, and a non-empty `sub` claim.
- The legacy HS256 secret is supported only for older Supabase projects when
  `SUPABASE_JWT_SECRET` is explicitly configured. The current project does not
  use this path.
- Authentication failures return the same safe `401` response and no tokens or
  cryptographic/provider details are logged or returned.

### Environment Variables

- `SUPABASE_URL` — required public project URL used to derive the issuer and
  JWKS URL.
- `SUPABASE_JWT_AUDIENCE` — expected audience; defaults to `authenticated`.
- `SUPABASE_JWT_SECRET` — legacy HS256-only fallback; do not set for the current
  ES256/JWKS project and never expose it to the frontend.

Safe placeholders are present in `.env.example` and `app/backend/.env.example`.

### Files Created or Modified

- Created `app/backend/auth.py` with the reusable `get_current_user` dependency
  and typed `AuthenticatedUser` identity object.
- Updated `app/backend/main.py` with protected
  `GET /api/v1/auth/me`; it returns only `user_id` and optional `email`.
- Created `app/backend/tests/test_auth.py`.
- Updated `.env.example` and created `app/backend/.env.example`.
- Added `PyJWT` and its cryptography support to `app/backend/requirements.txt`.

### Automated Validation

From `app/backend` with `.venv/bin/python`:

```text
python -m pytest -v                 13 passed
python -m ruff check .              passed
python -m ruff format --check .     passed
python -m mypy .                    passed
```

The authentication tests are network-independent: they mock the JWKS retrieval
boundary and cover public health access, missing/malformed authorization,
invalid/invalid-signature/expired tokens, issuer and audience mismatches,
missing subject, valid identity output, and token non-disclosure.

### Initial Schema Migration

Created:

```text
supabase/migrations/20260716212924_create_initial_phase2_tables.sql
```

The migration creates `profiles`, `resumes`, `outreach_items`,
`generated_drafts`, and `ai_usage` with UUID keys, `timestamptz` timestamps,
foreign keys to `auth.users`, constrained workflow/status values, and relevant
data checks. It also adds:

- non-negative checks for resume file size, AI token counts, and estimated cost;
- the required job-description state check for outreach items;
- required generated subject/body when generation is `completed`;
- nine user/workflow lookup indexes;
- reusable `public.set_updated_at()` plus four update triggers for tables with
  `updated_at`;
- `pgcrypto` (safely with `if not exists`) for `gen_random_uuid()`.

Foreign-key deletion behavior is deliberate: deleting an Auth user cascades its
owned application data, generated drafts cascade with their outreach item,
while selected resumes and AI usage records use `restrict` so an existing
workflow cannot silently lose its resume relationship or AI audit record.

No profile-creation trigger, storage bucket, RLS enablement, or RLS policy is
included. This keeps the schema migration focused and avoids deploying enabled
RLS with no intended access policy.

### Migration Validation and Limitation

Static review confirmed five table declarations, nine indexes, four update
triggers, the expected foreign keys and constraints, and no executable RLS or
policy statements. `git diff --check` passes.

The migrations were applied manually through the hosted Supabase SQL Editor.
The five tables, constraints, indexes, triggers, RLS configuration, grants, and
policies were verified in the hosted project. The hosted migration-history query
against `supabase_migrations.schema_migrations` failed because that table does
not exist in this project, so SQL Editor application is documented as the source
of hosted migration evidence.

### Exact Next Task

Begin **Phase 3 — Resume Library and PDF Processing** in a separate task.

### Row Level Security and Ownership Migration

Created:

```text
supabase/migrations/20260716213437_add_phase2_rls_policies.sql
```

The migration enables RLS for `profiles`, `resumes`, `outreach_items`,
`generated_drafts`, and `ai_usage`. Each browser-accessible table has separate,
explicit `authenticated` policies for select, insert, update, and delete using
`(select auth.uid())`; update policies apply both `using` and `with check` so a
user cannot reassign the ownership column.

`ai_usage` has a select-only policy and only `select` is granted to
`authenticated`. Inserts, updates, and deletes are intentionally reserved for
future trusted backend code using backend-only credentials; no service-role key
is used by or exposed to the frontend.

The migration revokes all table access from `public`, `anon`, and
`authenticated` before granting the minimum `authenticated` access required.
No policies are granted to `anon`.

Same-user relationships are enforced with composite foreign keys, not merely
frontend filtering or RLS visibility:

- `outreach_items.selected_resume_id` must reference a resume with the same
  `user_id`.
- `generated_drafts.outreach_item_id` must reference an outreach item with the
  same `user_id`.
- `ai_usage.outreach_item_id` has the same backend-side ownership protection.

### Automated Ownership Tests

Created local pgTAP suite:

```text
supabase/tests/database/phase2_rls.test.sql
```

The transaction-rolled-back suite has 42 assertions covering RLS status,
anonymous grant and operation denial, User A own-row access, User B isolation,
ownership reassignment, cross-user relationship attempts, and the read-only AI
usage boundary. It uses fixture Auth users only in the local test transaction.

### RLS Validation and Limitation

Static review confirms five RLS-enablement statements, five grant revocations,
17 explicit `authenticated` policies, composite same-owner foreign keys, no
unsafe `using (true)`/`with check (true)` policies, and a pgTAP plan matching
the 42 assertions.

Local same-user and cross-user ownership testing is confirmed complete. The
Supabase CLI is available through `npx` at version `2.109.1`, but the repository
is not linked to the hosted project, so `npx supabase migration list` cannot
inspect hosted migration state. `npx supabase db lint` cannot run because no
local Supabase Postgres instance is running. No Supabase CLI command changed the
database; hosted migration application was performed manually in the SQL Editor.

### Authenticated Frontend-to-Backend Request Flow

Created a reusable frontend API client that reads the current Supabase session
only when a protected request is made. It sends the access token directly in the
`Authorization: Bearer <token>` header for `GET /api/v1/auth/me`; it does not
copy tokens into another storage location or log them. Public `GET /health`
continues to use the same API base URL without an authorization header.

The protected dashboard calls the identity endpoint once for the current
session, displays a checking/confirmed/error state, and shows only the returned
email or a safe fallback. A backend `401` sets a friendly sign-in-again message
and signs the Supabase client out locally, returning the user to `/login` without
a retry loop. Supabase remains responsible for normal session refresh.

Frontend additions:

- `app/frontend/src/api/client.ts`
- `app/frontend/src/api/auth.ts`
- `app/frontend/src/components/AuthenticatedBackendStatus.tsx`
- `app/frontend/src/api/client.test.ts`

`app/frontend/.env.example` now requires `VITE_API_BASE_URL` to be set per
environment. The real local value remains in ignored `.env.local`; frontend code
uses only the Supabase publishable key and contains no service-role reference.

Automated validation completed in this environment:

```text
Frontend: npm run typecheck                 passed
Frontend: npm run lint                      passed
Frontend: npm run test                      15 passed
Frontend: npm run build                     passed
Backend:  python -m pytest -v               13 passed
Backend:  python -m ruff check .            passed
Backend:  python -m ruff format --check .   passed
Backend:  python -m mypy .                  passed
```

The Supabase CLI limitation is documented above. Hosted verification was instead
performed manually in the Supabase dashboard and SQL Editor. No destructive CLI
database command was run.

### Active Documentation Paths

The existing planning documents remain in `docs/planning/`. They were not
renamed or deleted during Phase 2 final integration because they are historical,
already referenced by the repository, and currently contain uncommitted project
work. This file remains the active Phase 2 progress record until a deliberate,
reviewed documentation migration is performed.

## Phase 2 Completion Summary

### Completed

- Supabase project configuration
- Google OAuth configuration
- Google login and sign-out
- Session restoration and cross-tab persistence
- Protected frontend routes
- Backend Supabase JWT verification
- Protected FastAPI authentication endpoint
- Initial database migration
- Five approved database tables:
  - `profiles`
  - `resumes`
  - `outreach_items`
  - `generated_drafts`
  - `ai_usage`
- Row Level Security
- User-ownership policies
- Same-user and cross-user database tests
- Authenticated frontend-to-backend API request flow
- Frontend automated checks
- Backend automated checks
- Phase 2 documentation updates

### Final Browser and API Verification

Confirmed manually:

- `GET /health` returns `200`.
- An unauthenticated `GET /api/v1/auth/me` returns safe `401 Unauthorized` with
  `{"detail":"Invalid or expired access token"}`.
- Google login reaches the protected dashboard.
- The authenticated frontend request to `GET /api/v1/auth/me` succeeds and its
  returned email matches the signed-in Google account.
- Refresh and cross-tab session persistence work.
- Local sign-out blocks protected routes and is reflected in other tabs.
- No authentication retry loop or exposed access token was observed in the UI,
  response body, or logs.

### Final Hosted Supabase Verification

The version-controlled migrations were applied manually through the hosted
Supabase SQL Editor. The hosted project contains all five approved tables, RLS
is enabled on each table, and exactly 17 policies target `authenticated`:

- `profiles`, `resumes`, `outreach_items`, and `generated_drafts` each have
  select, insert, update, and delete ownership policies.
- `ai_usage` grants authenticated users select-only access.
- Update policies include both `using` and `with check`.
- No unrestricted `true` policies exist and `anon` has no table grants.
- Authenticated grants match the approved browser-access boundary.
- The three same-user composite foreign-key protections exist for
  outreach-item/resume, generated-draft/outreach-item, and
  AI-usage/outreach-item relationships.

### Security Advisor

Security Advisor results: **0 errors** and **1 warning**. The warning is
**Leaked Password Protection Disabled**. It is accepted as non-blocking for
Phase 2 because Version 1 uses Google OAuth only. It should be reconsidered if
password-based authentication is introduced later.

### Supabase CLI and Migration-History Limitation

- `npx supabase` is available at version `2.109.1`.
- `npx supabase migration list` cannot inspect hosted migrations because the
  repository is not linked to the hosted project.
- `npx supabase db lint` cannot run because no local Supabase Postgres instance
  is running.
- The hosted `supabase_migrations.schema_migrations` query failed because that
  table does not exist in this project.
- Manual SQL Editor application and the hosted schema/policy inspection are the
  recorded migration-verification evidence.

### Exact Next Phase

**Phase 3 — Resume Library and PDF Processing**

Start with the private resume-storage bucket, then implement PDF-only upload,
backend extraction, and the Resume Library workflow according to the approved
Step 4 roadmap. No Phase 3 code was started during this update.

### Final Supabase CLI Verification

The earlier Supabase CLI limitations were subsequently resolved.

Confirmed:

* The Supabase CLI was available through `npx`.
* The repository/project migration status was inspected successfully.
* Database lint completed successfully.
* The migration-history setup was corrected, including the required
  `supabase_migrations.schema_migrations` state.
* Version-controlled Phase 2 migrations remained aligned with the hosted
  database.
* No destructive database reset or unintended schema operation was performed.

The earlier notes stating that migration status and database lint could not be
verified are retained only as historical troubleshooting context and no longer
represent the final Phase 2 state.

### Final Phase 2 Status

Phase 2 is formally complete and verified through:

* Automated frontend and backend checks
* Manual Google authentication acceptance
* Authenticated frontend-to-backend API verification
* Hosted table, constraint, RLS, grant, and policy inspection
* Same-user and cross-user ownership validation
* Security Advisor review
* Supabase CLI migration and database-lint verification

The next active implementation work is Phase 3.
