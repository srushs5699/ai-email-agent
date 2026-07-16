# Step 4 — Implementation Roadmap

## AI Email Agent Project

**Repository:** `ai-email-agent`  
**Status before this step:** Steps 1, 2, and 3 complete  
**Purpose of this document:** Define the exact build order, implementation phases, dependencies, validation checkpoints, testing strategy, deployment sequence, and completion criteria for Version 1.

---

# 1. Step 4 Goal

Step 4 converts the approved product requirements and technical architecture into a practical implementation roadmap.

The roadmap is designed to:

- Build the application in small, testable phases
- Prove the core product workflow before adding advanced automation
- Reduce integration risk
- Avoid unnecessary early complexity
- Keep development and cloud costs low
- Preserve all approved Version 1 requirements
- Ensure that no email is sent without explicit user approval

---

# 2. Confirmed First Usable Milestone

The first usable milestone will prove one complete outreach workflow for one item.

The user must be able to:

1. Sign in with Google.
2. Upload a real PDF resume.
3. Select a saved resume.
4. Capture LinkedIn post information using a browser extension.
5. Use a manual LinkedIn-content fallback when extraction fails.
6. Paste a job description or select “No job description available.”
7. Enter recipient information manually.
8. Generate a real personalized email using the OpenAI API.
9. Review and edit:
   - To
   - CC
   - Subject
   - Email body
10. See the selected resume.
11. Approve the draft in a simulated Gmail workflow.
12. Reopen the application without losing the saved draft.
13. See clear validation, error, token-usage, and estimated-cost information.

The first milestone will not send a real email.

Real Gmail integration will be added immediately after the simulated one-item workflow is stable and tested.

---

# 3. Approved Step 4 Decisions

## 3.1 Core Milestone Decisions

| Area | Approved Decision |
|---|---|
| First milestone | Complete one-item workflow |
| Gmail | Simulated Gmail draft first |
| OpenAI | Real OpenAI API in the first milestone |
| Resume input | Upload and parse real PDF resumes |
| LinkedIn input | Build the browser extension in the first milestone |
| Job description | Paste manually in the first milestone |
| Resume storage | Supabase Storage from the beginning |
| Review screen | Build the complete editable review screen |
| Authentication | Real Google login through Supabase Auth |
| Recipient lookup | Enter recipient email addresses manually first |
| Database scope | Create only tables required for the first workflow |

## 3.2 Technical Defaults

| Area | Approved Default |
|---|---|
| PDF extraction | FastAPI backend |
| Development environment | Local until the workflow is stable |
| Testing | Add automated tests during development |
| Frontend priority | Functional screens before visual polish |
| Browser extension scope | Capture author name, post text, profile URL, and visible job link |
| Browser extension fallback | Always provide manual LinkedIn fields |
| Prompt design | One structured backend prompt |
| AI response | Structured JSON |
| AI factual validation | Validate generated claims against resume content |
| Cost tracking | Track tokens and estimated cost per request |
| Spending control | Configurable monthly application-level limit |
| Unreadable PDFs | Reject with a clear error; no OCR in first build |
| Database changes | Version-controlled SQL migrations |
| Draft persistence | Autosave draft edits |
| Simulated approval | Mark approved and simulate successful Gmail draft creation |
| Error handling | Friendly frontend errors and detailed backend logs |
| Local secrets | `.env` excluded from Git; `.env.example` committed |
| Production secrets | Google Cloud Secret Manager or secure Cloud Run configuration |
| CI | Basic GitHub Actions before first deployment |
| Real Gmail phase | Immediately after the simulated workflow passes |
| Queue phase | After real Gmail works for one item |
| Apollo phase | After queue and manual-recipient workflows are stable |
| Automatic JD reading | After browser extension, Gmail, queue, and Apollo |
| Deployment | Local → private staging → integrations → production |

---

# 4. Version 1 Delivery Strategy

Version 1 will be built in progressive phases.

Each phase must:

1. Have a clear output.
2. Include automated and manual tests.
3. Pass its validation checkpoint.
4. Avoid introducing unrelated features.
5. Preserve all earlier working behavior.
6. Be committed to Git before the next phase begins.

---

# 5. Implementation Phases

## Phase 0 — Repository and Planning Baseline

### Goal

Prepare the repository so implementation can begin safely and consistently.

### Tasks

- Confirm the repository structure.
- Add this roadmap to:

```text
docs/planning/step-04-implementation-roadmap.md
```

- Confirm or create:

```text
app/frontend/
app/backend/
browser-extension/
tests/
scripts/
docs/architecture/
docs/testing/
docs/decisions/
```

- Add a root `README.md`.
- Add a root `.gitignore`.
- Add `.env.example` files for the backend and frontend.
- Add contribution and local setup instructions.
- Define development naming conventions.
- Define branch and commit conventions.
- Record architecture decisions in `docs/decisions/`.

### Validation checkpoint

- Repository structure exists.
- No secret keys are committed.
- The project can be cloned and understood from the README.
- Step 1 through Step 4 documents are stored in the repository.

---

## Phase 1 — Project Foundation

### Goal

Create working frontend and backend applications with automated quality checks.

### Frontend tasks

- Create a React and TypeScript application.
- Add routing.
- Add API-client structure.
- Add shared type definitions.
- Add form validation.
- Add basic layout and navigation.
- Create placeholder pages:
  - Login
  - Dashboard
  - Resume Library
  - New Outreach
  - Draft Review
  - Settings
- Add frontend environment configuration.
- Add frontend unit-test setup.
- Add formatting and linting.

### Backend tasks

- Create the FastAPI application.
- Add structured settings management.
- Add health-check endpoint.
- Add API versioning.
- Add request and response models.
- Add centralized error handling.
- Add structured logging.
- Add CORS configuration.
- Add backend test setup.
- Add formatting, linting, and type checking.

### CI tasks

Create GitHub Actions workflows that run:

- Frontend linting
- Frontend type checking
- Frontend tests
- Backend linting
- Backend type checking
- Backend tests

### Validation checkpoint

- Frontend runs locally.
- Backend runs locally.
- Frontend can call the backend health endpoint.
- CI passes.
- No business feature is implemented yet.

---

## Phase 2 — Supabase Foundation and Google Authentication

### Goal

Connect the application to Supabase and support secure Google login.

### Supabase tasks

- Create the Supabase project.
- Configure local and production environment values.
- Enable Google as an authentication provider.
- Configure redirect URLs.
- Configure allowed application origins.
- Create the first version-controlled migration.
- Enable Row Level Security for user-owned data.

### Initial database tables

Create only the tables needed for the first workflow:

#### `profiles`

Purpose:

- Store application-level user information.
- Associate Supabase authentication users with app records.

Suggested fields:

- `id`
- `email`
- `display_name`
- `created_at`
- `updated_at`

#### `resumes`

Purpose:

- Store PDF resume metadata and extracted text.

Suggested fields:

- `id`
- `user_id`
- `name`
- `storage_path`
- `mime_type`
- `file_size_bytes`
- `extracted_text`
- `parse_status`
- `parse_error`
- `created_at`
- `updated_at`

#### `outreach_items`

Purpose:

- Store the one-item outreach input and processing state.

Suggested fields:

- `id`
- `user_id`
- `linkedin_post_url`
- `linkedin_author_name`
- `linkedin_author_profile_url`
- `linkedin_post_text`
- `job_description_url`
- `job_description_text`
- `no_job_description`
- `recipient_to`
- `recipient_cc`
- `recipient_verification_status`
- `selected_resume_id`
- `status`
- `created_at`
- `updated_at`

#### `generated_drafts`

Purpose:

- Store generated and user-edited email drafts.

Suggested fields:

- `id`
- `user_id`
- `outreach_item_id`
- `subject`
- `body`
- `selected_experience_points`
- `fallback_linkedin_message`
- `generation_status`
- `approval_status`
- `simulated_gmail_status`
- `created_at`
- `updated_at`

#### `ai_usage`

Purpose:

- Track AI calls, token estimates, and application-level cost.

Suggested fields:

- `id`
- `user_id`
- `outreach_item_id`
- `model`
- `input_tokens`
- `output_tokens`
- `estimated_cost_usd`
- `request_status`
- `created_at`

### Authentication tasks

- Add Google Sign-In to the frontend.
- Exchange and verify the Supabase session.
- Protect authenticated frontend routes.
- Add backend authentication middleware or dependencies.
- Ensure users can access only their own records.
- Add sign-out.
- Add expired-session handling.

### Validation checkpoint

- The user can sign in with Google.
- Unauthenticated users cannot access application pages.
- Authenticated API requests succeed.
- Data ownership policies prevent cross-user access.
- CI still passes.

---

## Phase 3 — Resume Library and PDF Processing

### Goal

Support real PDF resume uploads, storage, parsing, selection, rename, and deletion.

### Storage tasks

- Create a private Supabase Storage bucket for resumes.
- Restrict files to authenticated users.
- Restrict file type to PDF.
- Add a configurable maximum file size.
- Use user-scoped storage paths.

### Backend tasks

- Add PDF upload endpoint.
- Validate MIME type and file extension.
- Upload the original PDF to Supabase Storage.
- Extract text in the FastAPI backend.
- Store extracted text in PostgreSQL.
- Reject unreadable or image-only PDFs with a clear error.
- Do not add OCR in the first build.
- Add list, rename, read metadata, and delete endpoints.
- Ensure database and storage deletion remain consistent.
- Add cleanup logic when an upload partially fails.

### Frontend tasks

- Build the Resume Library page.
- Add PDF upload.
- Show upload and parsing progress.
- Show clear parsing errors.
- List saved resumes.
- Rename a resume.
- Delete a resume.
- Select a resume for an outreach item.
- Show the selected resume in the workflow.

### Automated tests

- Valid PDF upload.
- Invalid file type.
- Oversized file.
- Empty PDF.
- Image-only PDF.
- Storage upload failure.
- Database failure after storage upload.
- Rename.
- Delete.
- User ownership.

### Validation checkpoint

- A real PDF can be uploaded and parsed.
- Extracted text is stored.
- Only PDFs are accepted.
- Unreadable PDFs fail safely.
- Resumes can be renamed and deleted.
- The selected resume persists.

---

## Phase 4 — LinkedIn Browser Extension and Manual Fallback

### Goal

Capture the minimum LinkedIn information required for email generation without storing LinkedIn credentials.

### Browser extension scope

The first extension should capture:

- LinkedIn post URL
- Post author name
- Author profile URL
- Visible post text
- Visible job-description link, when present

### Extension tasks

- Create the browser-extension project.
- Add a manifest.
- Add a content script.
- Add a popup or action interface.
- Extract only visible page content.
- Do not request or store LinkedIn credentials.
- Allow the user to review extracted data before sending it to the app.
- Send captured data to the web application.
- Handle missing fields.
- Handle LinkedIn layout changes gracefully.
- Display a clear extraction failure message.

### Manual fallback

The web application must always allow manual entry of:

- LinkedIn post URL
- Author name
- Author profile URL
- LinkedIn post content
- Job-description URL

### Automated and manual tests

- Post with visible author and text.
- Post with a job link.
- Post without a job link.
- Missing author profile.
- Extraction failure.
- Manual fallback.
- Duplicate content submitted accidentally.
- Authentication between extension and app.

### Validation checkpoint

- The extension can capture the required visible information.
- The user can inspect the captured data.
- Manual fallback works without the extension.
- No LinkedIn password is requested or stored.

---

## Phase 5 — One-Item Outreach Input Workflow

### Goal

Create and persist all non-AI input needed for one outreach item.

### Frontend tasks

Build the New Outreach workflow with:

- LinkedIn information
- Selected resume
- Job description input
- “No job description available” option
- Recipient To field
- Recipient CC field
- Recipient verification status
- Validation messages
- Save and continue behavior

### Backend tasks

- Create outreach-item endpoint.
- Update outreach-item endpoint.
- Retrieve saved outreach item.
- Validate selected resume ownership.
- Validate recipient email formats.
- Normalize empty CC values.
- Require either:
  - Job-description text, or
  - “No job description available”
- Store manual and extension-captured input using the same schema.

### Validation checkpoint

- The user can create one complete outreach item.
- The item survives a browser refresh.
- The user can return and edit it.
- Invalid inputs are rejected clearly.
- No Apollo integration is required yet.

---

## Phase 6 — OpenAI Email Generation

### Goal

Generate a personalized, factual, structured outreach email using real application inputs.

### Model verification

Before implementation:

- Verify currently available OpenAI API models.
- Verify exact model IDs.
- Verify current pricing.
- Verify account access.
- Select one fixed model through backend configuration.
- Do not add a model selector to the UI.
- Do not rely on unverified historical model names.

### Prompt design

Use one structured backend prompt with separate sections for:

- Approved user profile information
- Resume text
- LinkedIn post
- Job description
- Recipient details
- Email-writing rules
- Prohibited inventions
- Required tone
- Required output schema

### Required output

Require structured JSON containing:

- `subject`
- `email_body`
- `selected_experience_points`
- `fallback_linkedin_message`
- `source_claims` or equivalent traceability data

### Email-writing rules

The generated email must:

- Describe the user as “Software Developer with four years of experience.”
- Use only approved and supplied facts.
- Be friendly, informal, playful, professional, personalized, and easy to read.
- Vary playful analogies.
- Avoid repeating the exact same analogy every time.
- Include the fixed signature exactly:

```text
Best regards,
Srushti Shinde
Phone: (608) 217-2116
LinkedIn: https://www.linkedin.com/in/srushtisanjayshinde/
```

The generated email must never invent:

- Experience
- Technologies
- Projects
- Dates
- Metrics
- Education
- Achievements
- Recipient information
- Company information
- Job requirements
- Email addresses

### Factual validation

Before saving the draft:

- Validate selected claims against extracted resume text.
- Validate recipient facts against user-provided input.
- Validate company and job references against the LinkedIn post or job description.
- Reject or regenerate output containing unsupported claims.
- Record validation errors.

### Cost controls

For each request:

- Record model ID.
- Record input tokens.
- Record output tokens.
- Estimate request cost.
- Add the cost to the monthly total.
- Check the application-level monthly budget before sending a request.
- Stop new AI generation when the configured limit is reached.
- Display a clear budget-limit message.

### Backend tasks

- Add generation endpoint.
- Add prompt builder.
- Add output-schema validation.
- Add factual-validation service.
- Add retry handling for transient provider errors.
- Prevent duplicate generation requests.
- Save generation results.
- Save usage information.
- Never expose the OpenAI API key to the frontend.

### Frontend tasks

- Add Generate Email action.
- Show loading state.
- Prevent repeated clicks.
- Show validation failures.
- Show token and estimated-cost information.
- Display the generated draft.

### Automated tests

- Successful generation.
- Missing resume content.
- Missing LinkedIn content.
- No job description selected.
- Invalid JSON response.
- Unsupported claim detected.
- Provider timeout.
- Rate limit.
- Budget exceeded.
- Duplicate generation request.
- Fixed signature validation.

### Validation checkpoint

- A real email is generated using real inputs.
- Output is structured.
- Unsupported claims are blocked.
- Token and cost data are stored.
- Budget enforcement works.
- The draft persists.

---

## Phase 7 — Complete Draft Review Screen

### Goal

Allow the user to review and edit every important draft field before approval.

### Review screen requirements

The screen must allow editing:

- To
- CC
- Subject
- Email body

The screen must also show:

- Selected resume name
- Recipient verification status
- LinkedIn author
- LinkedIn post URL
- Job-description availability
- AI-selected experience points
- Estimated AI cost
- Generation and validation status

### Draft persistence

- Autosave edits.
- Use debouncing to avoid excessive requests.
- Show saving, saved, and failed-to-save states.
- Prevent accidental data loss.
- Restore the latest saved version after refresh.

### Draft actions

- Edit
- Regenerate
- Reject
- Delete
- Approve simulated Gmail draft

### Approval rule

Approval must:

- Mark the draft as approved.
- Simulate Gmail draft creation.
- Mark the simulation as successful.
- Never send a real email.
- Record the approval timestamp.

### Automated tests

- Edit each field.
- Autosave success.
- Autosave failure.
- Refresh restoration.
- Reject.
- Delete.
- Regenerate.
- Approve.
- Prevent approval with invalid recipient data.
- Prevent sending or real Gmail calls.

### Validation checkpoint

- Every draft field is editable.
- Changes persist.
- Approval simulates Gmail safely.
- No real email is sent.
- The one-item workflow is complete end to end.

---

## Phase 8 — First Milestone Hardening

### Goal

Stabilize the complete simulated one-item workflow before adding real Gmail.

### Tasks

- Run complete end-to-end tests.
- Add missing validation.
- Improve user-facing errors.
- Review backend logs.
- Add loading and empty states.
- Add retry behavior where safe.
- Review database policies.
- Review storage policies.
- Review API authorization.
- Review secrets handling.
- Review cost controls.
- Review duplicate action protection.
- Test browser refresh and session expiration.
- Test the extension and manual fallback.
- Confirm that no real email can be sent.

### First milestone completion criteria

The first milestone is complete only when the user can:

1. Sign in with Google.
2. Upload and select a real PDF resume.
3. Capture a LinkedIn post with the extension or use manual entry.
4. Paste a job description or select no job description.
5. Enter recipient information manually.
6. Generate a real email with OpenAI.
7. Review and edit all draft fields.
8. Approve the simulated Gmail draft.
9. Reopen the application without losing the draft.
10. See clear validation, error, token, and cost information.
11. Complete all automated tests.
12. Complete the manual acceptance checklist.

---

## Phase 9 — Private Staging Deployment

### Goal

Deploy the stable first milestone to a private cloud environment.

### Backend deployment

- Containerize FastAPI.
- Deploy to Google Cloud Run.
- Configure minimum instances according to budget.
- Prefer scale-to-zero behavior where appropriate.
- Configure CORS.
- Configure health checks.
- Configure secure environment values.
- Use Secret Manager or secure Cloud Run configuration.
- Configure logs.
- Add basic monitoring.

### Frontend deployment

Deploy the frontend using a low-cost cloud-hosted option compatible with the project architecture.

Requirements:

- HTTPS
- Environment configuration
- Private or restricted access where practical
- Correct redirect URLs
- Correct API base URL

### Supabase production configuration

- Add production redirect URLs.
- Review Row Level Security.
- Review storage access policies.
- Apply migrations.
- Confirm backups and recovery options available under the selected plan.

### Browser extension configuration

- Configure the staging application URL.
- Restrict allowed origins.
- Test authentication.
- Package the extension for local browser installation.

### Validation checkpoint

- The complete simulated workflow works in staging.
- Secrets are not exposed.
- Logs are available.
- Authentication works using production redirect URLs.
- Monthly cost remains within the approved direction.

---

## Phase 10 — Real Gmail Integration

### Goal

Replace the simulated Gmail step with real Gmail draft creation and approved sending.

### Gmail OAuth tasks

- Configure the Google Cloud OAuth consent screen.
- Request only required Gmail scopes.
- Connect Gmail authorization to the logged-in user.
- Store tokens securely.
- Handle token refresh.
- Handle revoked access.
- Never request or store the Gmail password.

### Gmail draft tasks

- Create a Gmail draft after AI generation or after explicit draft action, according to the finalized workflow.
- Attach the selected resume.
- Store the Gmail draft identifier securely.
- Synchronize website edits with the Gmail draft.
- Preserve To, CC, subject, body, and attachment.
- Send the existing Gmail draft only after approval.
- Do not add another confirmation screen after the green approval action.
- Remove successfully sent items from active application queues.
- Rely on Gmail Sent for sent-email history.

### Safety controls

- Disable Gmail sending outside the approved action.
- Prevent duplicate sends.
- Record send status.
- Handle expired or revoked tokens.
- Handle Gmail API errors.
- Verify attachment integrity.
- Verify recipients before sending.

### Validation checkpoint

- A real Gmail draft is created.
- Website edits synchronize correctly.
- The selected resume is attached.
- No email sends before approval.
- Approval sends exactly once.
- The sent email appears in Gmail Sent.

---

## Phase 11 — Full Queue Workflow

### Goal

Expand the proven one-item workflow into the approved three-queue system.

### Required queues

#### Processing Queue

- Maximum 10 LinkedIn URLs
- Manual start
- First-in processing order
- Process one item at a time
- Pause
- Resume
- Resume current unfinished item
- Do not rerun completed items
- Continue after failures

#### Review Queue

- Generated drafts waiting for review
- Edit
- Reject
- Delete
- Send
- Show resume
- Show email verification status

#### Failed Tasks

- Failed
- Duplicate
- No email available
- Original LinkedIn URL visible
- Retry
- Delete

### Queue database expansion

Add queue-specific tables or extend existing tables through migrations.

Potential additions:

- `processing_batches`
- `queue_items`
- `queue_events`
- `failed_task_details`

Do not add Redis or Celery unless PostgreSQL-backed processing proves insufficient.

### Queue processing rules

- Maximum queue size of 10.
- Prevent duplicate workers from processing the same task.
- Use database locking or atomic status transitions.
- Preserve state across backend restarts.
- Resume the current unfinished item.
- Never restart completed items.
- One failed item must not stop the queue.
- Draft approval remains mandatory.
- Batch completion requires:
  - Processing Queue = 0
  - Review Queue = 0
  - Failed Tasks = 0

### Validation checkpoint

- Ten items can be queued.
- Processing is sequential.
- Pause and resume work.
- Restart recovery works.
- Failures do not stop later items.
- Duplicate processing is prevented.
- Batch completion is calculated correctly.

---

## Phase 12 — Apollo Integration

### Goal

Replace manual recipient entry with Apollo contact discovery while preserving manual fallback.

### Tasks

- Verify Apollo’s current API availability, limits, and pricing.
- Use API or an approved integration.
- Never request or store Apollo password.
- Track remaining credits where possible.
- Stop new lookups when credits are exhausted.
- Show:

```text
Apollo credits are exhausted.
```

- Never guess email addresses.

### Email selection rules

When a company-domain email exists:

- Put one domain email in To.
- Put remaining emails in CC.

When no domain email exists:

- Put one personal email in To.
- Put remaining personal emails in CC.

Unverified emails:

- May be used.
- Must be clearly labeled as unverified.
- Must remain subject to user review.

No email available:

- Move the item to Failed Tasks.
- Mark it `No email available`.
- Generate a short LinkedIn message for manual use.

### Validation checkpoint

- Apollo lookup works.
- Credits are tracked or errors are handled.
- Exhausted credits stop future lookups.
- Email-selection rules are correct.
- Unverified emails are labeled.
- No-email results enter Failed Tasks.
- No guessed email is ever produced.

---

## Phase 13 — Duplicate Detection and Failure Recovery

### Goal

Complete the approved failure-handling and duplicate rules.

### Duplicate rules

Detect duplicates by:

- Same LinkedIn URL
- Same recipient
- Existing active or completed outreach record

Duplicate behavior:

- Do not generate another email.
- Do not send another email.
- Move the item to Failed Tasks.
- Mark it `Duplicate`.

### Failure behavior

- Preserve original input.
- Preserve LinkedIn URL.
- Store failure reason.
- Allow retry.
- Allow delete.
- Prevent a failed item from stopping the queue.
- Avoid infinite retry loops.
- Show actionable frontend errors.

### Validation checkpoint

- Duplicate URLs are caught.
- Duplicate recipients are caught.
- Retry resumes safely.
- Delete removes only the selected failed task.
- Queue processing continues after failure.

---

## Phase 14 — Automatic Job-Description Reading

### Goal

Add automatic job-description extraction after the more important integrations are stable.

### Tasks

- Read visible job-description links from the extension.
- Attempt backend retrieval only when permitted.
- Support common public career-site patterns.
- Sanitize retrieved content.
- Detect blocked, authenticated, or inaccessible pages.
- Ask the user to paste the job description when retrieval fails.
- Allow “No job description available.”
- Continue other queue items while waiting for manual input.

### Validation checkpoint

- Accessible job descriptions are extracted.
- Blocked pages fall back cleanly.
- Missing job descriptions do not stop the queue.
- Manual paste remains available.

---

## Phase 15 — Version 1 UI Improvement and Mobile Browser Support

### Goal

Improve usability after the complete workflow is stable.

### Tasks

- Improve visual hierarchy.
- Improve queue status visibility.
- Improve responsive behavior for phone browsers.
- Preserve desktop-first behavior.
- Improve empty, loading, success, warning, and error states.
- Add keyboard accessibility.
- Improve form accessibility.
- Review contrast and focus states.
- Improve browser-extension guidance.
- Add concise onboarding.

### Validation checkpoint

- Desktop workflow is polished.
- Core pages open and remain usable in a phone browser.
- Accessibility checks pass at an acceptable level.
- No workflow behavior changes unexpectedly.

---

## Phase 16 — Final Version 1 Verification

### Goal

Confirm that every approved Version 1 requirement is complete.

### Functional verification

Verify:

- Google login
- PDF-only resume library
- Resume rename and delete
- Resume selection per queue
- LinkedIn browser extension
- Manual LinkedIn fallback
- Job-description fallback
- OpenAI generation
- Factual validation
- Cost controls
- Gmail draft creation
- Draft synchronization
- Approval-only sending
- Apollo integration
- Queue size of 10
- Pause and resume
- Failed-task retry and delete
- Duplicate detection
- No-email behavior
- Apollo-credit exhaustion behavior
- Batch completion rule

### Security verification

Verify:

- No Gmail password handling
- No LinkedIn password handling
- No Apollo password handling
- No API keys in frontend code
- No secrets committed to Git
- User-scoped database access
- User-scoped storage access
- Secure production configuration
- No unauthorized send path

### Cost verification

Verify:

- OpenAI usage recording
- Monthly estimated cost
- Application-level AI spending limit
- Automatic AI pause
- Apollo credit stop
- Cloud costs remain within the intended low-cost direction

### Final acceptance rule

Version 1 is complete only when:

- All required workflows pass.
- All critical tests pass.
- No email can send without approval.
- No unsupported factual claims are generated.
- No credentials or secrets are exposed.
- The application works from the cloud without requiring the local development machine to remain online.

---

# 6. Exact Build Order

The implementation should follow this order:

1. Store Step 4 roadmap in the repository.
2. Prepare repository structure and documentation.
3. Create React and TypeScript frontend.
4. Create FastAPI backend.
5. Add linting, type checking, testing, and CI.
6. Create Supabase project.
7. Add Google authentication.
8. Add initial migrations and Row Level Security.
9. Add private resume storage.
10. Build PDF upload and backend extraction.
11. Build Resume Library.
12. Build LinkedIn browser extension.
13. Build manual LinkedIn fallback.
14. Build one-item outreach input flow.
15. Verify current OpenAI models and pricing.
16. Add structured prompt and AI generation.
17. Add factual validation.
18. Add AI usage and spending controls.
19. Build complete editable review screen.
20. Add autosave.
21. Add simulated Gmail approval.
22. Harden and test the first milestone.
23. Deploy private staging.
24. Add real Gmail OAuth and drafts.
25. Add Gmail synchronization and approval-only sending.
26. Add the full PostgreSQL-backed queue.
27. Add pause, resume, restart recovery, retry, and delete.
28. Add Apollo integration.
29. Add duplicate detection and no-email handling.
30. Add automatic job-description reading.
31. Improve responsive UI and accessibility.
32. Run final Version 1 verification.
33. Promote the stable build to the main deployment.

---

# 7. Testing Strategy

## 7.1 Unit tests

Use unit tests for:

- PDF validation
- PDF text extraction helpers
- Prompt construction
- AI output parsing
- Factual claim validation
- Cost calculations
- Email-selection rules
- Queue state transitions
- Duplicate detection
- Batch completion rules

## 7.2 Integration tests

Use integration tests for:

- Supabase authentication
- Database operations
- Storage upload and deletion
- OpenAI request flow using mocks in CI
- Gmail draft and send flow
- Apollo lookup flow
- Queue locking and recovery

## 7.3 End-to-end tests

Use end-to-end tests for:

- Login
- Resume upload
- LinkedIn capture
- Manual fallback
- Job-description input
- Email generation
- Draft editing
- Approval
- Gmail sending
- Queue processing
- Failed-task recovery

## 7.4 Manual acceptance testing

Manual testing is required for:

- Google OAuth
- LinkedIn extension behavior
- Real PDF quality
- Generated-email quality
- Gmail attachment behavior
- Gmail send behavior
- Apollo credit behavior
- Mobile-browser usability
- Production redirect and cookie behavior

---

# 8. Dependency Map

| Feature | Depends On |
|---|---|
| Resume Library | Authentication, database, storage |
| LinkedIn extension | Frontend URL, authentication, input schema |
| Outreach item | Authentication, resume selection, LinkedIn data |
| AI generation | Resume parsing, outreach item, model verification |
| Review screen | Generated draft, draft persistence |
| Simulated Gmail | Review screen and approval state |
| Real Gmail | Stable review workflow and OAuth configuration |
| Queue | Proven one-item workflow |
| Apollo | Stable queue and recipient schema |
| Automatic JD reading | Browser extension and fallback workflow |
| Final deployment | Stable integrations and complete testing |

---

# 9. Development Rules

During implementation:

- Do not add unrelated features.
- Do not silently change approved architecture.
- Do not replace Supabase with Cloud SQL without approval.
- Do not add Redis or Celery unless PostgreSQL becomes insufficient.
- Do not accept non-PDF resumes.
- Do not exceed a queue size of 10.
- Do not send email without approval.
- Do not guess contact information.
- Do not expose secrets.
- Do not trust unverified model names or prices.
- Do not treat provider free tiers as permanent guarantees.
- Keep migrations version controlled.
- Keep business logic out of the frontend when it involves secrets or security.
- Preserve manual fallbacks for external-site failures.
- Complete tests and validation before moving to the next phase.

---

# 10. Documentation Deliverables

The following documents should be created or updated during implementation:

```text
docs/planning/step-04-implementation-roadmap.md
docs/architecture/system-architecture.md
docs/architecture/database-schema.md
docs/architecture/authentication-flow.md
docs/architecture/gmail-integration.md
docs/architecture/queue-design.md
docs/architecture/browser-extension.md
docs/testing/test-strategy.md
docs/testing/manual-acceptance-checklist.md
docs/decisions/
README.md
.env.example
```

---

# 11. Next Step After Step 4

After this roadmap is saved, begin:

```text
Step 5 — Build the First Usable Milestone
```

The first implementation activity is:

```text
Phase 0 — Repository and Planning Baseline
```

The first coding activity is:

```text
Phase 1 — Project Foundation
```

Do not begin Gmail, queue, Apollo, or automatic job-description extraction before the simulated one-item workflow is stable and verified.
