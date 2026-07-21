export type Confidence = 'high' | 'medium' | 'low'

export type ExtractedField<T> = { value?: T; source?: string; confidence?: Confidence; warning?: string }

export type LinkedInCapturePayload = {
  version: 1
  sourceUrl: string
  authorName?: string
  authorProfileUrl?: string
  postText?: string
  jobDescriptionUrl?: string
  jobDescriptionText?: string
  jobDescriptionSource?: 'visible_page' | 'manual' | 'unavailable'
  linkedinJobUrl?: string
  officialJobUrl?: string
  jobDescriptionCaptureStatus?: 'captured' | 'partial' | 'unavailable'
  jobDescriptionCaptureWarning?: string
  importId?: string
  warnings: string[]
  capturedAt: string
}

export type ExtractionResult = {
  payload: LinkedInCapturePayload
  supported: boolean
  fields: { authorName: ExtractedField<string>; authorProfileUrl: ExtractedField<string>; postText: ExtractedField<string>; jobDescriptionUrl: ExtractedField<string> }
}

export type ExtensionMessage =
  | { type: 'EXTRACT_ACTIVE_POST' }
  | { type: 'OPEN_IMPORT'; payload: LinkedInCapturePayload }
  | { type: 'OPEN_MANUAL'; payload: LinkedInCapturePayload }
  | { type: 'GET_PENDING_IMPORT' }
  | { type: 'CLEAR_PENDING_IMPORT' }
  | { type: 'OPEN_JOB_CAPTURE'; payload: LinkedInCapturePayload }
  | { type: 'CAPTURE_JOB_WORKFLOW'; payload: LinkedInCapturePayload; originalTabId?: number }
  | { type: 'ATTACH_JOB_DESCRIPTION'; text?: string; source?: 'visible_page' | 'manual' | 'unavailable' }
  | { type: 'EXTRACT_JOB_DESCRIPTION' }
