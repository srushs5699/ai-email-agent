import { describe, expect, it } from 'vitest'
import { parseLinkedInImport } from './linkedinImport'

const payload = { version: 1, sourceUrl: 'https://www.linkedin.com/feed/update/urn:li:activity:1', authorName: 'Ada', postText: 'Hiring now', warnings: [], capturedAt: '2026-07-19T00:00:00Z' }
describe('parseLinkedInImport', () => {
  it('accepts a valid untrusted extension payload', () => expect(parseLinkedInImport(payload)?.authorName).toBe('Ada'))
  it('rejects malformed payloads', () => expect(parseLinkedInImport({ ...payload, sourceUrl: 'javascript:alert(1)' })).toBeNull())
  it('handles partial payloads', () => expect(parseLinkedInImport({ ...payload, authorName: undefined, postText: undefined })?.sourceUrl).toContain('linkedin.com'))
  it('rejects unsupported versions', () => expect(parseLinkedInImport({ ...payload, version: 2 })).toBeNull())
})
