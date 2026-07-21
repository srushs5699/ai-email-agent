export type LinkedInImportPayload = {
  version: 1
  sourceUrl: string
  authorName?: string
  authorProfileUrl?: string
  postText?: string
  jobDescriptionUrl?: string
  jobDescriptionText?: string
  jobDescriptionSource?: 'visible_page' | 'manual' | 'unavailable'
  importId?: string
  warnings: string[]
  capturedAt: string
}

const MAX_TEXT = 12000
function safeUrl(value: unknown): string | undefined {
  if (typeof value !== 'string' || value.length > 2048) return undefined
  try { const url = new URL(value); return ['http:', 'https:'].includes(url.protocol) ? url.toString() : undefined } catch { return undefined }
}

export function parseLinkedInImport(value: unknown): LinkedInImportPayload | null {
  if (!value || typeof value !== 'object') return null
  const raw = value as Record<string, unknown>
  const sourceUrl = safeUrl(raw.sourceUrl)
  if (raw.version !== 1 || !sourceUrl) return null
  const string = (field: unknown, max: number) => typeof field === 'string' && field.trim().length <= max ? field.trim() : undefined
  const jobDescriptionText = string(raw.jobDescriptionText, 50000)
  const jobDescriptionSource = raw.jobDescriptionSource === 'visible_page' || raw.jobDescriptionSource === 'manual' || raw.jobDescriptionSource === 'unavailable' ? raw.jobDescriptionSource : (jobDescriptionText ? 'manual' : 'unavailable')
  return { version: 1, sourceUrl, authorName: string(raw.authorName, 300), authorProfileUrl: safeUrl(raw.authorProfileUrl), postText: string(raw.postText, MAX_TEXT), jobDescriptionUrl: safeUrl(raw.jobDescriptionUrl), jobDescriptionText, jobDescriptionSource, importId: string(raw.importId, 100), warnings: Array.isArray(raw.warnings) ? raw.warnings.filter((warning): warning is string => typeof warning === 'string').slice(0, 20) : [], capturedAt: string(raw.capturedAt, 100) ?? new Date().toISOString() }
}
