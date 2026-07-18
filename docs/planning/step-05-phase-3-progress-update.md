# AI Email Agent — Step 5, Phase 3 Progress Update

## Current Phase

**Step 5 — Phase 3: Resume Library and PDF Processing**

**Status:** In progress — the simple single-user MVP now includes private
resume upload/parsing, a Resume Library, outreach input, backend-only email
generation, and editable copy-to-Gmail review. Phase 3 is not complete.

## Simplified MVP Direction

The near-term workflow is deliberately small:

```text
Google login → upload or select a resume → paste job and LinkedIn information
→ enter recipient details → generate an outreach email → review/edit → copy for Gmail
```

All Phase 1 and Phase 2 authentication, database, RLS, and Storage work is
preserved. The current outreach form and generated result stay in frontend state
for this MVP; no additional workflow persistence schema was added.

## Storage Foundation

### Bucket

- Bucket ID: `resumes`
- Privacy: private (`public = false`); no public URLs are generated.
- MIME restriction: `application/pdf` only.
- Maximum size: `10485760` bytes (10 MB).

The bucket configuration is in:

```text
supabase/migrations/20260717003423_create_private_resume_storage.sql
```

The 10 MB value is defined once in the migration's `resume_bucket_config` CTE.
The bucket insert uses `on conflict (id) do update` so a rerun restores the
required private PDF-only configuration.

### Object Path and Ownership

All future objects must use:

```text
<authenticated-user-id>/<resume-id>/<sanitized-filename>.pdf
```

The first segment is derived from the authenticated identity, never from an
independently trusted frontend user ID. The future FastAPI upload endpoint must
derive it from the verified JWT subject.

Storage policies scope `storage.objects` to the `resumes` bucket and require:

- first path segment equals `(select auth.uid())::text`;
- exactly two folder segments (user ID and resume ID);
- UUID-shaped resume ID;
- `.pdf` object extension.

There are explicit authenticated select, insert, update, and delete policies.
The update policy checks both the current path and destination path, preventing
a user from moving an object into another user's namespace. No policy targets
`anon` and no public or signed URLs are introduced.

The migration grants the required Storage object operations to `authenticated`.
The bucket/path RLS policies limit that table-level privilege to the private
`resumes` bucket and user-owned paths; no resume-object policy or grant is added
for `anon` or `public`. No frontend service-role credential is used or added.

### Backend Configuration

Safe examples expose:

```text
RESUME_MAX_UPLOAD_BYTES=10485760
```

The bucket itself already enforces the same 10 MB limit. FastAPI now reads and
enforces this setting before parsing or uploading. The backend also requires:

```text
SUPABASE_SERVICE_ROLE_KEY=
OPENAI_API_KEY=
OPENAI_MODEL=
```

These values belong only in the backend local environment. The service-role key
is used by the trusted FastAPI process for Storage and database operations and
is never used in the frontend. `OPENAI_MODEL` has no hard-coded fallback: set a
currently supported model in a local `.env` file.

## Resume Workflow

FastAPI now provides authenticated endpoints:

- `POST /api/v1/resumes` accepts one non-empty `application/pdf` file, verifies
  the `.pdf` extension and configured size, extracts text with `pypdf`, rejects
  unreadable/encrypted/textless PDFs (no OCR), stores the original privately,
  and inserts `public.resumes` metadata with `parse_status = completed`.
- `GET /api/v1/resumes` returns only the current user's safe metadata.
- `DELETE /api/v1/resumes/{resume_id}` only removes a resume found for the
  current verified user.

Object paths are generated as
`<verified-user-id>/<resume-id>/<sanitized-filename>.pdf`. Database insertion
failure triggers best-effort Storage cleanup. Full extracted resume text is
never returned by the API.

The protected `/resumes` Resume Library provides a PDF chooser, upload state,
safe errors, list, date and size display, selection, deletion, and an empty
state. Its selected resume ID is kept in `localStorage`; it does not duplicate
or expose authentication tokens.

## Outreach and Email Generation

The protected `/outreach` page has one form for a selected resume, LinkedIn
post text, job description text or an explicit no-job-description choice,
recipient To/CC, recipient name, and company name. It validates the minimal
required inputs before calling the backend.

`POST /api/v1/email-generation`:

- requires the existing JWT dependency;
- verifies the selected resume belongs to that user and has completed parsing;
- loads only its extracted text from the database;
- calls OpenAI from FastAPI only, using `OPENAI_API_KEY` and `OPENAI_MODEL`;
- requests strict JSON with only `subject` and `body`;
- instructs the model to use only supplied resume/input facts, avoid invented
  claims or hiring assumptions, use the required Srushti Shinde signature, and
  maintain a concise friendly professional tone.

Provider/network/invalid-output errors have safe client-facing messages. The
frontend never receives an OpenAI key or raw provider response. The review area
keeps To, CC, subject, and body editable and provides Copy Subject, Copy Body,
Copy Full Email, Start Over, and Generate Again controls. It does not send
email, create Gmail drafts, or autosave.

## Automated Validation

Local focused tests mock both Supabase and OpenAI boundaries. They cover
successful PDF upload, corrupt/textless/non-PDF rejection, unauthenticated
upload, resume ownership, owned/cross-user generation, invalid input, mocked
generation success, invalid provider output, frontend resume upload/selection,
outreach validation, result rendering, safe errors, and copying.

Latest local results:

- backend: `25 passed` (`pytest -v`), Ruff check/format, and mypy passed;
- frontend: typecheck, lint, build, and Vitest passed (`23 passed`).

## Manual Configuration and Acceptance Still Required

1. Apply the already-created Storage migration manually to the intended hosted
   Supabase development project if it has not yet been applied, then verify the
   private bucket and policies described below.
2. Set `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`,
   `RESUME_MAX_UPLOAD_BYTES=10485760`, `OPENAI_API_KEY`, and `OPENAI_MODEL` in
   `app/backend/.env` (never commit it). Keep only the publishable Supabase key
   in frontend configuration.
3. Start backend and frontend, sign in through Google, upload a small
   text-based PDF, select it, complete the outreach form, generate an email,
   edit the result, and copy it into Gmail manually.
4. Confirm the uploaded object remains private and no token, secret, resume
   text, or public URL appears in browser UI or logs.

Live OpenAI generation has not been tested here because no real credentials
were used. Hosted Storage behavior likewise requires the user's manual
verification; no hosted migration was applied by this task.

## Automated Storage Policy Tests

Added:

```text
supabase/tests/database/phase3_resume_storage.test.sql
```

The transaction-rolled-back pgTAP suite has 16 assertions for bucket settings,
policy presence and role scope, same-user read/insert/update/delete, cross-user
read/update/delete denial, cross-user insert/move denial, and other-bucket
denial. Fixtures use only `storage.objects.bucket_id` and `name`, avoiding
deprecated Storage ownership columns that may vary by Storage schema version.

## Hosted Supabase Manual Verification Required

Apply the migration manually through the hosted Supabase SQL Editor, then
confirm the bucket is private, `application/pdf` is its only allowed MIME type,
and its size limit is `10485760`. Confirm all four `resume_objects_*_own`
policies target `authenticated`, no `anon` policy exists, and no public resume
URL is enabled. Verify user-scoped upload/read/update/delete behavior with two
development accounts.

The project currently has no local Supabase database command available for this
task, so this pgTAP file has not been run here. No hosted migration was applied
automatically.

## Not Implemented Yet

- Browser extension
- Apollo
- Queue, workers, Redis, or Celery
- Gmail API, Gmail OAuth scopes, or Gmail drafts
- OCR
- Automatic job-description extraction
- Advanced cost tracking
- Production deployment hardening
- Supabase Storage signed/public URLs
- Any Phase 4 or later work

## Hosted Storage Verification Completed

The Phase 3 Storage migration was manually applied through the hosted Supabase
SQL Editor and verified successfully.

Confirmed in the hosted project:

* The `resumes` bucket exists.
* The bucket is private.
* Public access is disabled.
* The only allowed MIME type is `application/pdf`.
* The maximum object size is `10485760` bytes.
* The following four policies target `authenticated`:

```text
resume_objects_select_own
resume_objects_insert_own
resume_objects_update_own
resume_objects_delete_own
```

* No anonymous policy grants access to resume objects.
* Resume objects use user-scoped paths.
* No public resume URL was introduced.

The earlier statement that hosted migration application and Storage verification
were pending is no longer current.

## Final MVP Verification Fixes

A verification pass identified and corrected the following issues:

* Whitespace-only `recipient_to` values are now rejected.
* Resume changes made on the outreach page now update the selected resume stored
  in `localStorage`.
* The frontend environment example now contains the required Supabase URL and
  publishable-key placeholders.
* FastAPI now loads the ignored local file at `app/backend/.env`.
* Newly introduced usage of the deprecated HTTP 422 status constant was
  replaced.

Files involved in the verification pass included:

```text
.env.example
app/backend/.env.example
app/backend/main.py
app/backend/email_generation.py
app/backend/resumes.py
app/backend/tests/test_resume_workflow.py
app/frontend/.env.example
app/frontend/src/pages/OutreachPage.tsx
app/frontend/src/pages/OutreachPage.test.tsx
docs/planning/step-05-phase-3-progress-update.md
```

Final automated verification:

```text
Backend pytest:              25 passed
Backend Ruff check:          passed
Backend Ruff format check:   passed
Backend mypy:                passed
Frontend typecheck:          passed
Frontend lint:               passed
Frontend Vitest:             4 files, 23 tests passed
Frontend production build:   passed
git diff --check:             passed
```

One third-party TestClient deprecation warning remains, but it does not cause a
test failure.

## Updated AI Provider Direction

The initial email-generation implementation uses OpenAI through backend-only
configuration.

For immediate testing, the user decided not to:

* Pay for OpenAI API usage yet
* Download a large local Ollama model

The intended temporary testing direction is therefore a hosted Gemini API free
tier while preserving OpenAI as a future provider option.

This is currently a project decision, not confirmed completed implementation.

Planned configuration:

```text
AI_PROVIDER=gemini
GEMINI_API_KEY=
GEMINI_MODEL=
OPENAI_API_KEY=
OPENAI_MODEL=
```

Before implementation, verify the current official Gemini Python SDK, the
current free-tier model ID, and the account's available quota.

Gemini and OpenAI credentials must remain backend-only. The React frontend must
not call either provider directly.

## Current Remaining Work

No known code blocker remains for the OpenAI-based implementation.

The remaining work before the first live use is:

1. Complete the required backend local environment values.
2. Either:

   * Configure OpenAI and perform the first live generation, or
   * Implement and configure the planned Gemini provider option.
3. Start the backend and frontend locally.
4. Complete one manual end-to-end test:

   * Google login
   * PDF resume upload
   * Resume selection
   * Outreach inputs
   * Email generation
   * Editing
   * Copying into Gmail

Phase 3 remains in progress until a live AI provider and the complete manual
workflow are verified.

## Step 1 — Gemini Provider Support

**Status:** Implemented and automatedly verified on 2026-07-17. No live Gemini
request was made because this work did not use a real API key.

Email generation now supports exactly two backend-only providers selected by
`AI_PROVIDER` (case-insensitive, with surrounding whitespace ignored):

```text
AI_PROVIDER=gemini
AI_PROVIDER=openai
```

`gemini` requires only `GEMINI_API_KEY` and `GEMINI_MODEL`; `openai` requires
only `OPENAI_API_KEY` and `OPENAI_MODEL`. Credentials for the inactive provider
are not required. Unsupported providers and incomplete active-provider
configuration return the existing safe configuration error. Neither provider is
configured in the frontend, and no provider field or migration was added to the
database.

Both providers use the same prompt construction, factuality and tone rules, and
the approved signature:

```text
Best regards,
Srushti Shinde
Phone: (608) 217-2116
LinkedIn: https://www.linkedin.com/in/srushtisanjayshinde/
```

They also use the same strict internal Pydantic validation before returning the
unchanged frontend/API contract:

```json
{"subject":"string","body":"string"}
```

Invalid JSON, non-object output, missing/null/non-string fields, blank fields,
and unexpected extra output are rejected. Provider exceptions are recorded only
as a provider name, broad category, and exception class; prompts, resume text,
raw provider responses, request bodies, authorization headers, and credentials
are not logged or exposed to clients.

### Gemini SDK Verification

Official Google documentation was consulted on **2026-07-17**:

- [Getting started](https://ai.google.dev/gemini-api/docs/get-started) specifies
  `pip install -U google-genai` and the native `from google import genai` SDK.
- [Migrating to the Interactions API](https://ai.google.dev/gemini-api/docs/migrate-to-interactions)
  documents the currently supported `generate_content` structured-output form:
  `types.GenerateContentConfig(response_mime_type="application/json",
  response_schema=...)`.
- [Gemini 2.5 Flash model page](https://ai.google.dev/gemini-api/docs/models/gemini-2.5-flash)
  identifies `gemini-2.5-flash` as **stable** and structured-output capable.
- [Gemini Developer API pricing](https://ai.google.dev/gemini-api/docs/pricing)
  lists a Free Tier for Gemini 2.5 Flash.

The backend uses the native Google Gen AI client initialized as
`genai.Client(api_key=GEMINI_API_KEY)` and requests `application/json` with the
shared Pydantic schema. The environment examples use the verified stable model:

```text
GEMINI_MODEL=gemini-2.5-flash
```

### Tests and Automated Verification

Added fully mocked provider-boundary coverage for Gemini and OpenAI selection,
active-provider configuration, successful structured output, malformed JSON,
missing/empty/null/non-string fields, and safe provider exceptions. Existing
authentication and resume-ownership tests continue to run. Tests make no
Gemini or OpenAI network calls.

Automated verification completed from the repository root on 2026-07-17:

```text
app/backend/.venv/bin/pytest                 52 passed (one TestClient deprecation warning)
app/backend/.venv/bin/ruff check .           passed
app/backend/.venv/bin/ruff format --check .  passed
app/backend/.venv/bin/mypy .                 passed
git diff --check                             reports a pre-existing trailing blank-line
                                             issue in step-05-phase-2-progress-update.md
```

No frontend files changed for this Step 1 provider work, so frontend checks
were not rerun. Live Gemini generation remains **not verified** and requires a
user-supplied local `GEMINI_API_KEY`.
