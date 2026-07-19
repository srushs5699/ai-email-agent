import type { Draft } from '../api/drafts'

/**
 * Converts only legacy JSON-escaped line separators stored as text. Actual
 * newline characters do not match these patterns, making this idempotent.
 */
export function normalizeLegacyEmailBody(body: string): string {
  return body
    .replace(/\\\\n/g, '\n')
    .replace(/\\r\\n/g, '\n')
    .replace(/\\n/g, '\n')
    .replace(/\\r/g, '\n')
}

export function normalizeReviewDraft(draft: Draft): Draft {
  const body = normalizeLegacyEmailBody(draft.body)
  return body === draft.body ? draft : { ...draft, body }
}
