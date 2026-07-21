import type { Confidence } from '../shared/types'

export type JobDescriptionCaptureResult = { text: string | null; url: string | null; source: 'visible_page' | 'unavailable'; warning: string | null; confidence?: Confidence; warnings: string[] }
export const MAX_JOB_DESCRIPTION_LENGTH = 50000
export const normalizeJobDescription = (value: string) => value.replace(/\s+/g, ' ').trim().slice(0, MAX_JOB_DESCRIPTION_LENGTH)
const visible = (node: Element) => { const style = getComputedStyle(node); return style.display !== 'none' && style.visibility !== 'hidden' && node.getAttribute('aria-hidden') !== 'true' }
const reject = /captcha|verify you are human|access denied|sign in|log in|cookie|privacy|recommended jobs|apply now/i
const selectors = ['[data-testid*="job-description"]', '[id*="job-description"]', '[id*="jobDescription"]', '[class*="job-description"]', '[class*="jobDescription"]', 'article', 'main']
const unavailable = (url: string | null): JobDescriptionCaptureResult => ({ text: null, url, source: 'unavailable', warning: 'The job description could not be extracted automatically.', warnings: ['The job description could not be extracted automatically.'] })

export function extractJobDescription(document: Document): JobDescriptionCaptureResult {
  for (const selector of selectors) {
    const node = [...document.querySelectorAll(selector)].find(visible)
    const text = normalizeJobDescription(node?.textContent ?? '')
    if (text.length >= 80 && !reject.test(text.slice(0, 500))) return { text, url: document.location.href, source: 'visible_page', warning: null, confidence: selector === 'main' ? 'medium' : 'high', warnings: [] }
  }
  const bodyText = normalizeJobDescription(document.body?.innerText ?? '')
  if (bodyText.length >= 80 && !reject.test(bodyText.slice(0, 500))) return { text: bodyText, url: document.location.href, source: 'visible_page', warning: null, confidence: 'low', warnings: [] }
  return unavailable(document.location.href)
}
