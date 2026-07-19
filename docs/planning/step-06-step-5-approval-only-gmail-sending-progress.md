# Step 7 — Step 5 Approval-Only Gmail Sending Progress

## Implemented

- Separate `Approve Email` and `Send Email` actions; approval never sends.
- Deterministic SHA-256 approval hash over normalized To, CC, subject, body, and selected resume ID.
- Server-side recipient-list validation for approval and again immediately before send.
- Approval invalidation on persisted To, CC, subject, body, or selected-resume edits.
- Approval and send routes enforce ownership, Gmail connection, existing Gmail draft, successful latest synchronization, valid recipients, and current approval.
- Gmail send uses only `POST /gmail/v1/users/me/drafts/send` with the stored Gmail draft ID; it neither creates a draft nor sends a raw MIME message.
- Atomic database claim (`not_sent`/`failed` to `sending`) prevents concurrent or repeated requests from making a second Gmail send call.
- Success persists sent audit metadata and marks the draft `sent`, excluding it from unfinished active-draft recovery. Failure preserves website content, Gmail metadata, and approval for a safe retry.

## Automatically verified

- Backend: 120 tests passed; Ruff and formatting checks passed; mypy passed for 25 source files.
- Frontend: 4 Vitest files / 31 tests passed; TypeScript, ESLint, and production build passed.
- `git diff --check` passed.

## Manually verified

- None during this implementation.

## Pending manual verification

- Real Gmail approval and send behavior, Sent-folder appearance, duplicate-send behavior, safe retry, refresh recovery, and Supabase audit records.
- Apply migration `20260720120000_add_approval_only_gmail_sending.sql` to the target Supabase environment before browser/Gmail verification.

## Blockers

- No code blocker. Hosted/local migration status was not confirmed in this workspace.

## Warnings

- Existing Starlette/httpx deprecation warning in backend tests.
- ESLint reports one existing exhaustive-deps warning in `OutreachPage.tsx`.

# AI Email Agent — Step 5 Approval-Only Gmail Sending Progress

## Status

**Step 5 is complete and manually verified.**

Repository:

```text
/Users/srushtishinde/Desktop/Desktop/agent/ai-email-agent
```

Previous progress document:

```text
docs/planning/step-06-step-4-gmail-api-integration-progress.md
```

Recommended repository filename:

```text
docs/planning/step-07-step-5-approval-only-gmail-sending-progress.md
```

---

## 1. Scope completed

Step 5 added approval-only Gmail sending to the existing single-user review workflow.

The implementation preserves all previously completed behavior:

- Resume upload, parsing, selection, listing, and deletion
- Manual outreach inputs
- OpenAI and Gemini email generation
- Provider switching through `AI_PROVIDER`
- Editable To, CC, subject, and body fields
- Copy-to-clipboard
- Draft persistence and autosave
- Refresh recovery
- Start Over
- Gmail OAuth connection
- Gmail draft creation
- Gmail synchronization
- PDF resume attachment
- Sync failure handling and retry

No automatic sending, bulk sending, scheduling, campaign automation, or multi-item queue processing was added.

---

## 2. Approval model

The application now requires two separate explicit actions:

1. `Approve Email`
2. `Send Email`

Approval does not send the email.

Sending is unavailable until the current persisted draft has been explicitly approved.

Approval applies to the current material content:

- To
- CC
- Subject
- Body
- Selected resume

Approval is invalidated when any of these values changes.

After a material edit:

- The previous approval becomes invalid
- Send becomes unavailable
- Gmail synchronization must complete again
- The user must explicitly approve the updated content again

The backend enforces approval even when the frontend is bypassed.

---

## 3. Recipient validation

Recipient validation is enforced before approval and again before sending.

Verified behavior:

- At least one valid To recipient is required
- Invalid To addresses are rejected
- Invalid CC addresses are rejected
- Empty or malformed recipient entries are rejected
- Sending cannot proceed with invalid recipients
- Backend validation does not rely only on the frontend

---

## 4. Gmail sending behavior

The application sends the existing Gmail draft using its stored Gmail draft ID.

The send operation does not create a new Gmail draft.

Sending is blocked when:

- Gmail is disconnected
- No Gmail draft exists
- Gmail synchronization is pending
- Gmail synchronization failed
- Approval is missing
- Approval is stale
- Website content changed after approval
- The draft was already sent

After Gmail confirms success, the application records the sent state, sent timestamp, and Gmail sent message ID.

---

## 5. Duplicate-send protection

Duplicate sending is prevented across:

- Repeated button clicks
- Rapid clicks
- Browser or network retries
- Repeated API calls
- Page refreshes
- Attempts to resend an already-sent draft

A successfully sent draft is not silently sent again.

The frontend disables repeated send actions while sending, and the backend independently enforces duplicate-send protection.

---

## 6. Send states and failure handling

The review interface shows the applicable lifecycle states:

- Ready to approve
- Approved
- Ready to send
- Sending
- Sent
- Failed

While sending:

- Repeated send actions are disabled
- A visible pending state is shown
- Only one send request is accepted

After success:

- A clear sent confirmation is shown
- The sent timestamp is displayed
- Further send attempts are blocked
- The persisted draft and audit metadata are retained

After failure:

- A sanitized failure state is shown
- Website draft content is preserved
- Gmail draft metadata is preserved
- The draft is not marked as sent
- Safe retry remains available
- No new Gmail draft is created

---

## 7. Active review behavior

After successful sending:

- The sent item is removed from the active review workflow
- The persisted database row is retained
- Approval and Gmail audit metadata remain available
- The sent item is not restored as an unfinished draft after refresh

This is still a single-active-item workflow.

A formal multi-item Review Queue has not yet been implemented.

---

## 8. Database changes

A new additive Step 5 migration was created and applied to the hosted Supabase project.

The migration adds the approval and send-state fields required by the implementation while preserving existing ownership and RLS protections.

Verified:

- The hosted migration was applied
- Local and remote migration history matched
- Existing generated-draft ownership protections remained intact
- Sent drafts remain stored as historical records
- Sent drafts are excluded from unfinished active-draft recovery
- OAuth tokens are not exposed through generated-draft records

### Applied migration

Record the exact migration filename here:

```text
TODO: paste the exact Step 5 migration filename
```

---

## 9. API changes

Step 5 added backend operations equivalent to:

```text
POST /api/v1/drafts/{draft_id}/approve
POST /api/v1/drafts/{draft_id}/send
```

The exact route names follow the repository's existing API conventions.

Approval enforcement includes:

- Authentication
- Ownership
- Gmail connection
- Existing Gmail draft
- Successful latest Gmail synchronization
- Valid recipients
- Current-content approval integrity

Send enforcement includes:

- Authentication
- Ownership
- Connected Gmail account
- Existing stored Gmail draft ID
- Successful latest synchronization
- Valid current approval
- Duplicate-send protection
- Existing-draft Gmail send operation
- Sent-state persistence only after Gmail success

---

## 10. Tests added

Backend test coverage includes:

- Approval success for an owned synchronized Gmail draft
- Approval rejection without Gmail draft
- Approval rejection when Gmail is disconnected
- Approval rejection when sync is pending or failed
- Recipient validation
- Material-edit approval invalidation
- Resume-change approval invalidation
- Send rejection without approval
- Send rejection with stale approval
- Send rejection without Gmail draft
- Send rejection when Gmail is disconnected
- Successful sending of the existing Gmail draft
- Sent timestamp and Gmail sent message ID persistence
- Duplicate-send prevention
- Send failure preservation and safe retry
- Cross-user access denial
- No new Gmail draft during send
- No sensitive data leakage

Frontend test coverage includes:

- Approve Email control
- Send Email control
- Send disabled before approval
- Approval does not automatically send
- Send enabled after valid approval
- Recipient validation
- Approval invalidation after edits
- Resume-change invalidation
- Sync gating
- Sending state
- Sent state
- Failed state
- Duplicate-click prevention
- Safe retry
- No automatic send
- Existing Step 3 and Step 4 behavior remains intact

---

## 11. Automated verification

All Step 5 automated checks were reported as passing.

The exact final command output was not included in this chat. Paste the final results below so the progress document remains auditable.

### Backend

```text
TODO: paste focused Step 5 pytest output
TODO: paste complete pytest output
TODO: paste Ruff check output
TODO: paste Ruff format-check output
TODO: paste mypy output
```

### Frontend

```text
TODO: paste focused approval/send test output
TODO: paste complete Vitest output
TODO: paste TypeScript output
TODO: paste ESLint output
TODO: paste production build output
```

### Repository and database

```text
TODO: paste migration-list verification
TODO: paste database lint output, if run
TODO: paste git diff --check output
TODO: paste git status --short output
```

---

## 12. Manual verification completed

The following checks were manually verified:

- Separate Approve Email and Send Email actions
- Sending blocked before explicit approval
- Approval alone does not send
- Recipient validation before approval and sending
- Approval invalidation after To changes
- Approval invalidation after CC changes
- Approval invalidation after subject changes
- Approval invalidation after body changes
- Approval invalidation after selected-resume changes
- Gmail synchronization required before approval and sending
- Successful send of the existing Gmail draft
- Correct email appears in Gmail Sent
- Correct To recipients
- Correct CC recipients
- Correct subject
- Correct body
- Correct PDF resume attachment
- Duplicate-send prevention
- Sending state
- Sent state
- Failed state
- Safe failure and retry
- Refresh before sending does not trigger automatic sending
- Sent item does not return as an unfinished draft after refresh
- Sent item is removed from the active review workflow
- Sent database row and audit state remain preserved
- Existing Step 3 persistence behavior still works
- Existing Step 4 Gmail draft and synchronization behavior still works
- Start Over still works
- Copy-to-clipboard remains available

---

## 13. Security and privacy verification

Verified safeguards:

- OAuth tokens are not exposed to the frontend
- OAuth tokens are not logged
- Recipient values are not logged
- Email bodies are not logged
- Resume contents and attachments are not logged
- Raw Gmail payloads containing private content are not logged
- Error responses are sanitized
- Cross-user draft approval and sending are denied
- Sending does not create a new Gmail draft
- Already-sent drafts are not silently resent

---

## 14. Blockers and warnings

### Blockers

None reported.

### Existing warning

The previously known Starlette/httpx deprecation warning may still be present unless separately resolved.

### Documentation follow-up

Before committing this file, replace the `TODO` entries with:

- Exact Step 5 migration filename
- Exact final automated verification output
- Final repository status output

---

## 15. Completion statement

Step 5 — Approval-Only Gmail Sending is complete and manually verified.

The application now supports the safe single-item workflow:

```text
Generate email
→ Review and edit
→ Create/synchronize Gmail draft
→ Approve current content
→ Send existing Gmail draft
→ Preserve sent audit history
→ Remove sent item from active review
```

The application does not yet support a formal multi-item Review Queue. That remains later roadmap work.