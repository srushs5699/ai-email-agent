# AI Email Agent — Step 8 Failed Tasks Queue Progress

## Scope

- Added an active, user-owned Failed Tasks Queue backed by existing processing queue items.

## Existing components reused

- Processing Queue's persistent item rows, atomic queue-item claims, item-level failure isolation, generation prompt, resume lookup, and draft persistence.
- Generated drafts continue to use `ready_for_review`, so the existing Review Queue receives successful retries without a second review workflow.

## Files changed

- Backend: `failed_tasks.py`, `processing_queues.py`, `supabase_admin.py`, router registration, and targeted tests.
- Frontend: failed-task API client, page, responsive card styles, navigation, route, and tests.
- Database: `20260723120000_add_failed_processing_tasks.sql`.

## Schema decision and migration

- No new failed-task table. Additive metadata on `processing_queue_items`: `failure_status`, `failure_reason`, `retry_count`, `retry_started_at`, and `hidden_at`.
- Backfills old failed rows; adds an active-failed index and a service-role atomic retry-claim RPC.
- Existing `user_id` ownership and processing queue-item RLS policy remain unchanged; no policy is weakened.

## API

- `GET /api/v1/failed-tasks`: active owned failed/retrying tasks, newest first.
- `POST /api/v1/failed-tasks/{id}/retry`: atomically claims only one active failed item and runs the existing item processor in the background.
- `DELETE /api/v1/failed-tasks/{id}`: soft-hides only that active failed item.

## Processing, statuses, retry, and delete

- Isolated failures preserve a safe reason and classify general errors as `Failed`, invalid recipient input as `No email available`, and exact recipient-plus-LinkedIn-source active-draft matches as `Duplicate`.
- Retry retains the saved queue payload, LinkedIn URL, and resume ID, creates the normal pending-review draft on success, and never approves or sends it.
- Delete is a soft hide (`hidden_at`), preserving queue, outreach, draft, resume, and audit relationships.

## Automated verification

- `cd app/frontend && npm run lint`: passed with one pre-existing `OutreachPage.tsx` hook-dependency warning.
- `cd app/frontend && npx tsc -b`: passed.
- `cd app/frontend && npm test -- --run`: passed, 9 files / 49 tests.
- `cd app/frontend && npm run build`: passed.
- `cd app/backend && pytest -q tests/test_processing_queue_finalization.py`: passed, 2 tests.
- Existing Processing Queue and Failed Tasks test modules still cannot collect in this environment because `google.genai` is unavailable to the configured interpreter; this is the same dependency limitation recorded above.
- `cd app/backend && .venv/bin/ruff check .`: passed.
- `cd app/backend && .venv/bin/mypy .`: passed (29 source files).
- `cd app/backend && pytest -q`: blocked during collection by the local environment: `google.genai` and `pypdf` are not installed in the configured interpreter.

## Manual Verification Status

Manual verification was intentionally skipped at the user's request.

The Failed Tasks Queue implementation was accepted based on the recorded implementation and automated verification results, including:

- Backend automated checks and the focused Processing Queue finalization test.
- Frontend automated tests.
- Processing Queue and Review Queue regression coverage included in the frontend suite.
- Lint checks, type checking, and the frontend production build.
- Existing Step 8 implementation results and documented environment limitations.

Manual verification items remain skipped or not performed; they were not marked as verified. In particular, a real failed-task retry through to the Review Queue was not manually performed.

## Processing Queue terminal-state correction

### Root cause

- The worker normally called finalization after each item, but restart reconciliation deliberately skipped `running` queues. A persisted running queue whose items were already terminal therefore remained active. Separately, frontend polling ignored an active-queue not-found response, retaining stale local `running` state.

### Fix

- Added one idempotent `finalize_processing_queue_if_done` implementation. It treats only `pending` and `processing` as processable, conditionally transitions draft/running/paused queues with all terminal items to `completed` or `completed_with_failures`, and updates final counters/timestamp.
- The worker invokes it on recovery, after each item, and after its loop; the active-queue lookup reconciles legacy terminal-running batches before returning an active record.
- The frontend clears stale active state when polling finds no active queue and exposes a completed-state `Create New Queue` action rather than Pause.

### Tests and verification

- Added backend finalization coverage for completed/failed terminal items and pending/processing preservation.
- Added frontend control coverage for running, paused, and completed batches.
- `cd app/backend && .venv/bin/ruff check .`: passed.
- `cd app/backend && .venv/bin/mypy .`: passed (30 source files).
- `cd app/frontend && npm test -- --run`: passed, 9 files / 52 tests.
- `cd app/frontend && npm run build`: passed.

## Completion status

Completed — implementation and automated verification complete; manual review skipped by user
