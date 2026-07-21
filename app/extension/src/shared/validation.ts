import type { LinkedInCapturePayload } from './types'

const MAX_TEXT = 12000
const MAX_URL = 2048
const text = (value: unknown, max: number) => typeof value === 'string' && value.trim().length <= max ? value.trim() : undefined
const linkedInUrl = (value: unknown) => {
  const candidate = text(value, MAX_URL)
  if (!candidate) return undefined
  try { const parsed = new URL(candidate); return ['http:', 'https:'].includes(parsed.protocol) ? parsed.toString() : undefined } catch { return undefined }
}

export function validatePayload(value: unknown): LinkedInCapturePayload | null {
  if (!value || typeof value !== 'object') return null
  const item = value as Record<string, unknown>
  const sourceUrl = linkedInUrl(item.sourceUrl)
  if (item.version !== 1 || !sourceUrl) return null
  const warnings = Array.isArray(item.warnings) ? item.warnings.filter((warning): warning is string => typeof warning === 'string').slice(0, 20) : []
  const jobDescriptionText = text(item.jobDescriptionText, 50000)
  const jobDescriptionSource = item.jobDescriptionSource === 'visible_page' || item.jobDescriptionSource === 'manual' || item.jobDescriptionSource === 'unavailable'
    ? item.jobDescriptionSource : (jobDescriptionText ? 'manual' : 'unavailable')
  return { version: 1, sourceUrl, authorName: text(item.authorName, 300), authorProfileUrl: linkedInUrl(item.authorProfileUrl), postText: text(item.postText, MAX_TEXT), jobDescriptionUrl: linkedInUrl(item.jobDescriptionUrl), linkedinJobUrl: linkedInUrl(item.linkedinJobUrl), officialJobUrl: linkedInUrl(item.officialJobUrl), jobDescriptionText, jobDescriptionSource, jobDescriptionCaptureStatus: item.jobDescriptionCaptureStatus === 'captured' || item.jobDescriptionCaptureStatus === 'partial' || item.jobDescriptionCaptureStatus === 'unavailable' ? item.jobDescriptionCaptureStatus : undefined, jobDescriptionCaptureWarning: text(item.jobDescriptionCaptureWarning, 500), importId: text(item.importId, 100), warnings, capturedAt: text(item.capturedAt, 100) ?? new Date().toISOString() }
}
