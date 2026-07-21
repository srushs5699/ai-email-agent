export type JobLinkKind = 'linkedin_job' | 'external_job' | 'missing' | 'unsafe'
export type ApplyKind = 'easy_apply' | 'external_apply' | 'none'

export function classifyJobLink(value?: string): JobLinkKind {
  if (!value) return 'missing'
  try {
    const url = new URL(value)
    if (!['http:', 'https:'].includes(url.protocol)) return 'unsafe'
    return /(^|\.)linkedin\.com$/i.test(url.hostname) && /\/jobs\//.test(url.pathname) ? 'linkedin_job' : 'external_job'
  } catch { return 'unsafe' }
}

export function detectApplyKind(document: Document): ApplyKind {
  const labels = [...document.querySelectorAll<HTMLElement>('a,button,[role="button"]')]
    .filter((node) => node.getAttribute('aria-hidden') !== 'true' && !node.hasAttribute('hidden'))
    .map((node) => `${node.getAttribute('aria-label') ?? ''} ${node.textContent ?? ''}`.replace(/\s+/g, ' ').trim().toLowerCase())
  if (labels.some((label) => /easy apply/.test(label))) return 'easy_apply'
  return labels.some((label) => /apply on company website|external application|continue to application|apply now|\bapply\b/.test(label)) ? 'external_apply' : 'none'
}

export function isSpecificJobPosting(document: Document, text: string): boolean {
  const title = document.querySelector('h1')?.textContent?.trim() ?? ''
  const blocked = /captcha|verify you are human|access denied|sign in|log in|search jobs|careers home/i
  return title.length > 2 && text.length >= 80 && !blocked.test(`${title} ${text.slice(0, 500)}`)
}
