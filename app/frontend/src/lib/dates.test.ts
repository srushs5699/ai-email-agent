import { describe, expect, it } from 'vitest'

import { formatPacificDateTime } from './dates'

describe('formatPacificDateTime', () => {
  it('formats summer UTC timestamps in Pacific daylight time', () => {
    expect(formatPacificDateTime('2026-07-19T20:15:00Z')).toBe('Jul 19, 2026 at 1:15 PM PDT')
  })

  it('formats winter UTC timestamps in Pacific standard time', () => {
    expect(formatPacificDateTime('2026-01-15T18:30:00Z')).toBe('Jan 15, 2026 at 10:30 AM PST')
  })

  it('returns a safe fallback for missing or invalid timestamps', () => {
    expect(formatPacificDateTime()).toBe('Not available')
    expect(formatPacificDateTime('not-a-date')).toBe('Not available')
  })
})
