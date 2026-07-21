import { describe, expect, it } from 'vitest'

import { MAX_JOB_DESCRIPTION_LENGTH, extractJobDescription, normalizeJobDescription } from '../src/extraction/job-description'

function page(body: string): Document {
  document.body.innerHTML = body
  Object.defineProperty(document.body, 'innerText', { configurable: true, value: document.body.textContent ?? '' })
  return document
}

const jd = 'Senior engineer responsible for designing reliable distributed systems, collaborating with product teams, and improving the platform for customers every day.'

describe('visible job-description extraction', () => {
  it('reads a known visible job-description container', () => {
    const result = extractJobDescription(page(`<nav>ignore</nav><section class="job-description">${jd}</section>`))
    expect(result).toMatchObject({ text: jd, source: 'visible_page', warning: null })
  })
  it('falls back to main before the body', () => {
    const result = extractJobDescription(page(`<main>${jd}</main><footer>ignore</footer>`))
    expect(result.text).toBe(jd)
    expect(result.confidence).toBe('medium')
  })
  it('falls back to cleaned body text when no reliable container exists', () => {
    const result = extractJobDescription(page(`<div>${jd}</div>`))
    expect(result.text).toBe(jd)
    expect(result.confidence).toBe('low')
  })
  it('normalizes whitespace and truncates to the safe maximum', () => {
    expect(normalizeJobDescription(' one\n\t two  ')).toBe('one two')
    expect(normalizeJobDescription('x'.repeat(MAX_JOB_DESCRIPTION_LENGTH + 10))).toHaveLength(MAX_JOB_DESCRIPTION_LENGTH)
  })
  it('returns a non-fatal unavailable result for CAPTCHA-like visible pages', () => {
    const result = extractJobDescription(page(`<main>Verify you are human CAPTCHA ${'x'.repeat(100)}</main>`))
    expect(result).toMatchObject({ text: null, source: 'unavailable', warning: 'The job description could not be extracted automatically.' })
  })
})
