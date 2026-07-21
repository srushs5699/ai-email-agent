import { describe, expect, it } from 'vitest'
import { classifyJobLink, detectApplyKind, isSpecificJobPosting } from '../src/extraction/job-link'

describe('safe job-link classification', () => {
  it('classifies LinkedIn, external, missing, and unsafe links', () => {
    expect(classifyJobLink('https://www.linkedin.com/jobs/view/1')).toBe('linkedin_job')
    expect(classifyJobLink('https://jobs.example.com/roles/1')).toBe('external_job')
    expect(classifyJobLink()).toBe('missing')
    expect(classifyJobLink('javascript:alert(1)')).toBe('unsafe')
  })
  it('detects Easy Apply without clicking it', () => {
    document.body.innerHTML = '<button aria-label="Easy Apply">Easy Apply</button>'
    expect(detectApplyKind(document)).toBe('easy_apply')
  })
  it('rejects generic and blocked pages as job postings', () => {
    document.body.innerHTML = '<h1>Careers home</h1>'
    expect(isSpecificJobPosting(document, 'x'.repeat(100))).toBe(false)
  })
})
