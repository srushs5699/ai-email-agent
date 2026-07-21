import { describe, expect, it } from 'vitest'
import { validatePayload } from '../src/shared/validation'

describe('popup review payload behavior', () => {
  const base = { version: 1, sourceUrl: 'https://www.linkedin.com/feed/update/urn:li:activity:1', warnings: [], capturedAt: '2026-07-19T00:00:00Z' }
  it('allows a partial editable capture and requires an explicit valid source URL', () => { expect(validatePayload({ ...base, authorName: 'Ada' })?.authorName).toBe('Ada'); expect(validatePayload({ ...base, sourceUrl: 'javascript:x' })).toBeNull() })
  it('preserves warnings for unsupported and partial extraction states', () => expect(validatePayload({ ...base, warnings: ['Unsupported page', 'No job link'] })?.warnings).toHaveLength(2))
  it('does not model automatic transmission', () => { expect(validatePayload(base)).not.toBeNull() })
})
