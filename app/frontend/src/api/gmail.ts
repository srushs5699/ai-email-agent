import { requestProtectedApi } from './client'

export interface GmailStatus {
  configured: boolean
  connected: boolean
  authorization_required: boolean
  google_email: string | null
  granted_scopes: string[]
}

export interface GmailAuthorization {
  authorization_url: string
}

export interface GmailDraftResult {
  gmail_draft_id: string
  gmail_message_id: string | null
  sync_status: 'synced'
  created: boolean
}

export function getGmailStatus(): Promise<GmailStatus> {
  return requestProtectedApi<GmailStatus>('/api/v1/gmail/status')
}

export function authorizeGmail(): Promise<GmailAuthorization> {
  return requestProtectedApi<GmailAuthorization>('/api/v1/gmail/authorize')
}

export function createGmailDraft(draftId: string): Promise<GmailDraftResult> {
  return requestProtectedApi<GmailDraftResult>(`/api/v1/drafts/${draftId}/gmail`, { method: 'POST' })
}

export function syncGmailDraft(draftId: string): Promise<GmailDraftResult> {
  return requestProtectedApi<GmailDraftResult>(`/api/v1/drafts/${draftId}/gmail/sync`, { method: 'POST' })
}
