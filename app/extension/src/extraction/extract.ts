import { AUTHOR_SELECTORS, POST_SELECTORS, TEXT_SELECTORS } from './selectors'
import type { ExtractedField, ExtractionResult } from '../shared/types'
import { classifyJobLink } from './job-link'

const tracking = ['trk', 'trackingId', 'utm_source', 'utm_medium', 'utm_campaign']
const clean = (text: string | null | undefined) => text?.replace(/\s*\n\s*/g, '\n').replace(/[ \t]+/g, ' ').trim() ?? ''

export function normalizeUrl(raw: string, base: string): string | undefined {
  try { const url = new URL(raw, base); tracking.forEach((key) => url.searchParams.delete(key)); return url.toString() } catch { return undefined }
}
export function isSupportedPostUrl(url: string): boolean {
  try { const parsed = new URL(url); return /(^|\.)linkedin\.com$/.test(parsed.hostname) && (/\/feed\/update\/urn:li:activity:/.test(parsed.pathname) || /\/posts\//.test(parsed.pathname) || /\/activity-\d+/.test(parsed.pathname)) } catch { return false }
}
function visible(element: Element): boolean { const style = getComputedStyle(element); return style.display !== 'none' && style.visibility !== 'hidden' }
function firstVisible(root: ParentNode, selectors: string[]): Element | undefined { for (const selector of selectors) { const match = [...root.querySelectorAll(selector)].find(visible); if (match) return match } return undefined }
export function findPostContainer(document: Document): Element | undefined {
  const candidates = POST_SELECTORS.flatMap((selector) => [...document.querySelectorAll(selector)]).filter(visible)
  const permalink = candidates.find((candidate) => [...candidate.querySelectorAll('a[href]')].some((link) => link.getAttribute('href')?.includes('activity')))
  return permalink ?? candidates.find((candidate) => /(?:update|post|hiring)/i.test(candidate.getAttribute('aria-label') ?? '')) ?? candidates[0]
}
function author(container: Element, base: string): { name: ExtractedField<string>; profile: ExtractedField<string> } {
  const node = firstVisible(container, AUTHOR_SELECTORS)
  const name = clean(node?.textContent)
  const link = (node?.closest('a[href]') ?? firstVisible(container, ['a[href*="/in/"]', 'a[href*="/company/"]'])) as HTMLAnchorElement | undefined
  const profile = link?.getAttribute('href') ? normalizeUrl(link.getAttribute('href')!, base) : undefined
  return { name: name ? { value: name, source: 'post author header', confidence: 'high' } : { warning: 'Author name was not found in the post header.' }, profile: profile ? { value: profile, source: 'post author link', confidence: 'high' } : { warning: name ? 'A visible author name had no reliable profile link.' : undefined } }
}
export function extractPostText(container: Element): ExtractedField<string> {
  const node = firstVisible(container, TEXT_SELECTORS)
  const value = clean(node?.textContent)
  if (!value) return { warning: 'Visible post text was not found.' }
  if (/home|messaging|notifications/i.test(value) && value.length > 2000) return { warning: 'Post text looked contaminated by page navigation.' }
  return { value, source: 'visible post commentary', confidence: 'high' }
}
export function extractJobLink(container: Element, base: string): ExtractedField<string> {
  const ranked = [...container.querySelectorAll('a[href]')].filter(visible).map((link, index) => {
    const href = normalizeUrl(link.getAttribute('href') ?? '', base); const label = clean(link.textContent).toLowerCase()
    if (!href || /\/in\/|\/company\//.test(new URL(href).pathname)) return null
    let score = 0
    if (/linkedin\.com\/jobs\//.test(href)) score += 8
    if (/(apply|job|role|position|opening|career|hiring|description)/.test(label)) score += 5
    if (/(greenhouse|lever\.co|workday|myworkdayjobs|careers)/.test(href)) score += 3
    return { href, score, index }
  }).filter((entry): entry is { href: string; score: number; index: number } => Boolean(entry)).filter((entry) => entry.score > 0).sort((a, b) => b.score - a.score || a.index - b.index)
  if (!ranked.length) return { warning: 'No visible job-description link was found.' }
  return { value: ranked[0].href, source: 'ranked visible post link', confidence: ranked[0].score >= 8 ? 'high' : 'medium', warning: ranked.length > 1 && ranked[0].score === ranked[1].score ? 'Several likely job links were visible; the first strongest link was selected.' : undefined }
}
export function extractLinkedInPost(document: Document, sourceUrl = document.location.href): ExtractionResult {
  const normalizedSource = normalizeUrl(sourceUrl, sourceUrl) ?? sourceUrl
  const supported = isSupportedPostUrl(sourceUrl)
  const warnings: string[] = supported ? [] : ['This page does not appear to be a supported LinkedIn post page.']
  const container = findPostContainer(document)
  if (!container) warnings.push('No active post container was found; you can still import the source URL and enter details manually.')
  const authorFields = container ? author(container, sourceUrl) : { name: { warning: 'No post container.' }, profile: { warning: 'No post container.' } }
  const postText = container ? extractPostText(container) : { warning: 'No post container.' }
  const jobDescriptionUrl = container ? extractJobLink(container, sourceUrl) : { warning: 'No post container.' }
  ;[authorFields.name, authorFields.profile, postText, jobDescriptionUrl].forEach((field) => { if (field.warning) warnings.push(field.warning) })
  const kind = classifyJobLink(jobDescriptionUrl.value)
  if (kind === 'unsafe') warnings.push('The selected job link is unsafe and was not opened.')
  return { supported, fields: { authorName: authorFields.name, authorProfileUrl: authorFields.profile, postText, jobDescriptionUrl }, payload: { version: 1, sourceUrl: normalizedSource, authorName: authorFields.name.value, authorProfileUrl: authorFields.profile.value, postText: postText.value, jobDescriptionUrl: jobDescriptionUrl.value, linkedinJobUrl: kind === 'linkedin_job' ? jobDescriptionUrl.value : undefined, officialJobUrl: kind === 'external_job' ? jobDescriptionUrl.value : undefined, jobDescriptionCaptureStatus: jobDescriptionUrl.value ? 'partial' : 'unavailable', jobDescriptionCaptureWarning: jobDescriptionUrl.value ? 'Open the job page normally to capture visible job-description text.' : 'Job description could not be extracted', warnings, capturedAt: new Date().toISOString() } }
}
