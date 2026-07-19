# Step 6 — Step 3 Draft Persistence Progress

## Status

Complete in code and automated verification. Manual verification remains for the
user to perform against the hosted Supabase project.

## Existing Implementation Found

The project already had `outreach_items` and `generated_drafts`, authenticated
RLS ownership policies, composite owner foreign keys, an editable outreach
review page, and provider-independent email generation returning `subject` and
`body`. It had no draft API, active draft state, autosave, or recovery.

## Persistence Architecture

`POST /api/v1/drafts` validates the authenticated user's selected resume,
creates an owned outreach item, then creates its generated draft. The backend
derives `user_id` from the verified JWT and never accepts an owner ID from the
browser. `PATCH /api/v1/drafts/{draft_id}` updates only an owned draft's subject
and body. `GET /api/v1/drafts/latest` and `GET /api/v1/drafts/{draft_id}` return
only drafts owned by the current user.

The email-generation endpoint and its `{subject, body}` contract are unchanged.
The frontend performs a separate draft-persistence request after generation.

## Database and RLS

Migration `20260718160000_add_draft_persistence.sql` is additive. It adds
optional recipient name/company columns to `outreach_items`, a `draft_status`
column to `generated_drafts` with only `draft` and `ready_for_review`, and an
owner/status/updated-time index for latest-draft retrieval.

No RLS policy was weakened or changed. Existing RLS and composite foreign keys
continue to enforce authenticated ownership of resumes, outreach items, and
generated drafts.

## Autosave and Race Protection

Edits debounce for 800 ms. A timer is cancelled on a newer edit or unmount.
Each save has a monotonically increasing version. A completion can display
`Saved` only when it is still the latest request and its content still matches
the latest local subject/body; stale completions cannot overwrite the status.
The editor remains usable while saving. A failed save leaves local text intact,
shows `Save failed`, and a later edit retries.

## Recovery and Actions

On initial page load, the latest unfinished draft is restored only when the
user has not entered data in that session. Recovery restores supported form
fields, subject, body, and an existing selected resume. A deleted/missing resume
is not selected.

Start Over cancels pending autosave, clears the active draft and recovered form
state, clears save status, and suppresses recovery for the remainder of that
page session. It does not delete the database record. Generate Again updates
the same active draft's subject/body through the normal autosave path after a
new generation; a new record is created only when no active draft exists.

## Tests and Verification

Added backend tests for owned creation, owner derivation, owned/other-user
resume behavior, blank subject/body rejection, owned update, latest retrieval,
and inaccessible draft handling. Frontend tests cover persistence after
generation, recovery, debounced final-content autosave, Start Over, and the
existing copy workflow.

Automated results:

```text
Backend pytest: 60 passed, 1 third-party TestClient deprecation warning
Backend Ruff check: passed
Backend Ruff format check: passed
Backend mypy: passed
Frontend Vitest: 4 files, 26 tests passed
Frontend TypeScript: passed
Frontend ESLint: passed
Frontend production build: passed
```

## Manual Verification

1. Log in and select a completed resume.
2. Enter outreach details and generate an email.
3. Confirm a draft record exists in Supabase with the authenticated owner.
4. Edit the subject; confirm `Saving…`, then `Saved`.
5. Edit the body and confirm autosave succeeds.
6. Make rapid edits and confirm the latest content remains after saving.
7. Refresh the page and confirm the unfinished draft restores recipient,
   company, subject, body, and the existing selected resume.
8. Click Start Over; confirm active draft state clears and the draft is not
   restored again during that page session.
9. Confirm the copy actions still work.

## Remaining Risk

The migration must be applied to the intended hosted Supabase project before
manual verification. No Gmail draft, sending, approval workflow, or Step 4 work
is included.

# AI Email Agent — Step 3 Draft Persistence and Autosave Progress

## Status

**Step 3 — Draft Persistence and Autosave: Complete**

Manual verification and automated verification have both passed.

## Repository

```text
/Users/srushtishinde/Desktop/Desktop/agent/ai-email-agent
```

## Scope Completed

Step 3 added persistent email drafts and autosave behavior without starting Gmail draft creation, sending, queues, duplicate detection, browser extension work, OCR, Apollo integration, deployment, or Step 4.

The completed workflow is now:

```text
generate email
→ persist draft in Supabase
→ review subject and body
→ edit subject and body
→ autosave changes after debounce
→ refresh page
→ restore latest unfinished draft
→ use Start Over to begin a new workflow
```

No email is sent automatically.

## Existing Implementation Preserved

The following existing functionality remains intact:

- React and TypeScript frontend
- FastAPI backend
- Supabase authentication with Google login
- Backend JWT verification
- Protected API routes
- Resume upload, parsing, listing, selection, and deletion
- Manual LinkedIn post input
- Manual job-description input
- Manual recipient input
- OpenAI and Gemini provider support
- Provider switching through `AI_PROVIDER`
- Provider-independent generation response contract
- Editable generated subject and body
- Copy-to-clipboard workflow
- Existing frontend layout
- Existing backend and frontend tests
- GitHub Actions CI

## Draft Persistence Design

The frontend continues to call the backend draft API:

```text
POST /api/v1/drafts
PATCH /api/v1/drafts/{draft_id}
GET /api/v1/drafts/latest
GET /api/v1/drafts/{draft_id}
```

The backend persists draft records in the existing Supabase table:

```text
public.generated_drafts
```

The API endpoint name and database table name are intentionally different.

Draft ownership is derived from the authenticated user. The frontend does not provide or control the owner ID.

Each new outreach workflow creates one new draft row. Editing the same active draft updates the existing row instead of creating additional rows.

## Database Migration

The existing migration was applied to the hosted Supabase database:

```text
supabase/migrations/20260718160000_add_draft_persistence.sql
```

The migration added or enabled the fields required for Step 3, including:

- `recipient_name`
- `company_name`
- `draft_status`

It also added the latest-draft lookup index.

Existing RLS policies were preserved and were not weakened.

Read-only hosted checks confirmed that the expected fields are available.

## PostgREST Relationship Fix

After applying the migration, latest-draft retrieval still failed with:

```text
HTTP 300
PostgREST code: PGRST201
Could not embed because more than one relationship was found
```

Cause:

`generated_drafts` had both its original foreign key and an ownership-enforcing composite foreign key to `outreach_items`. The unqualified relationship embed was ambiguous.

The backend query was updated to explicitly use the ownership relationship:

```text
outreach_items!generated_drafts_outreach_item_same_owner_fkey(*)
```

The corrected hosted query returned:

```text
status=200
```

## Autosave Behavior

Subject and body edits now autosave after a short debounce.

Verified behavior:

- Editing shows `Saving…`
- Successful persistence changes the status to `Saved`
- Rapid edits save the latest value
- Repeated edits update the existing draft row
- Older content does not overwrite newer content
- The UI remains editable while saving
- A failed initial persistence does not create a false saved state

## Draft Recovery

The latest unfinished draft is restored when the outreach page is refreshed.

Manual verification confirmed that refresh recovery works.

Recovered state includes the saved email content and related workflow data where available.

## Start Over Behavior

`Start Over` clears the active frontend workflow and returns the user to the LinkedIn-post input step.

Verified behavior:

- Generated subject and body are cleared from the active UI
- The app returns to the initial outreach input step
- The existing saved row remains in `generated_drafts`
- The database row is not deleted
- Generating after Start Over creates a new draft row for the new workflow

This is intentional. Start Over begins a new workflow; it is not a delete operation.

## Generate Again / New Workflow Behavior

A new email generated after Start Over creates a second draft row.

This is correct because:

- edits to the same draft update the same row
- a new workflow creates a new row
- rapid edits do not create duplicate rows

## Safe Error Diagnostics

Backend draft persistence diagnostics now safely log:

- upstream HTTP status
- PostgREST error code
- safe error message
- safe error details

The backend does not log full draft bodies, resume text, prompts, authorization headers, secrets, or tokens.

## Automated Verification

### Backend

```text
61 passed
1 third-party Starlette TestClient deprecation warning
ruff check: passed
ruff format --check: passed
mypy: passed
```

### Frontend

```text
Vitest: 4 files passed
26 tests passed
TypeScript: passed
ESLint: passed
Production build: passed
```

### Repository

```text
git diff --check: passed
```

## Manual Verification Results

The following manual checks passed:

- Email generation succeeds
- Draft persistence succeeds
- A row appears in `public.generated_drafts`
- Editing the subject shows `Saving… → Saved`
- Editing the body autosaves successfully
- Existing draft rows are updated correctly
- Rapid edits preserve the latest content
- Refresh restores the latest unfinished draft
- Start Over clears the active frontend workflow
- Start Over does not delete the saved database row
- A new workflow after Start Over creates a new draft row

## Remaining Blockers

None for Step 3.

## Step 3 Completion Criteria

- [x] Drafts are persisted in Supabase
- [x] Autosave works with debounce
- [x] Draft edits survive refresh
- [x] Ownership rules remain enforced
- [x] Existing generation workflow still works
- [x] Existing copy workflow remains preserved
- [x] Backend checks pass
- [x] Frontend checks pass
- [x] `git diff --check` passes
- [x] Documentation is updated
- [x] Manual recovery and autosave verification succeeds

## Final Result

**Step 3 is complete.**

The project is ready to move to Step 4.
