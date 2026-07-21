import { requestProtectedApi } from './client'

export interface DraftInput {
  resume_id: string
  linkedin_post_text: string
  job_description_text: string
  no_job_description: boolean
  recipient_to: string
  recipient_cc?: string
  recipient_name?: string
  company_name?: string
  subject: string
  body: string
}

export interface Draft extends Omit<DraftInput, 'resume_id'> {
  id: string
  outreach_item_id: string
  resume_id: string | null
  status: 'draft' | 'ready_for_review' | 'sent' | 'rejected' | 'deleted'
  created_at: string
  updated_at: string
  gmail_draft_id: string | null
  gmail_message_id: string | null
  gmail_sync_status: 'not_created' | 'creating' | 'synced' | 'syncing' | 'sync_failed' | 'authorization_required'
  gmail_sync_error_code: string | null
  approval_status: 'pending' | 'approved' | 'rejected'
  approved_at: string | null
  send_status: 'not_sent' | 'sending' | 'failed' | 'sent'
  sent_at: string | null
  gmail_sent_message_id: string | null
  send_error_code: string | null
}

export function createDraft(input: DraftInput): Promise<Draft> {
  return requestProtectedApi<Draft>('/api/v1/drafts', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
}

export function getLatestDraft(): Promise<Draft> {
  return requestProtectedApi<Draft>('/api/v1/drafts/latest')
}

export function listReviewDrafts(): Promise<{ drafts: Draft[] }> {
  return requestProtectedApi('/api/v1/drafts')
}

export function regenerateDraft(draftId: string): Promise<Draft> {
  return requestProtectedApi(`/api/v1/drafts/${draftId}/regenerate`, { method: 'POST' })
}

export function rejectDraft(draftId: string): Promise<void> {
  return requestProtectedApi(`/api/v1/drafts/${draftId}/reject`, { method: 'POST' })
}

export function deleteDraft(draftId: string): Promise<void> {
  return requestProtectedApi(`/api/v1/drafts/${draftId}`, { method: 'DELETE' })
}

export function updateDraft(
  draftId: string,
  input: Pick<DraftInput, 'subject' | 'body'> & Partial<Pick<DraftInput, 'recipient_to' | 'recipient_cc' | 'resume_id'>>,
): Promise<Draft> {
  return requestProtectedApi<Draft>(`/api/v1/drafts/${draftId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
}

export function approveDraft(draftId: string): Promise<{ approval_status: 'approved'; approved_at: string }> {
  return requestProtectedApi(`/api/v1/drafts/${draftId}/approve`, { method: 'POST' })
}

export function sendDraft(draftId: string): Promise<{ send_status: 'sent'; sent_at: string; gmail_sent_message_id: string }> {
  return requestProtectedApi(`/api/v1/drafts/${draftId}/send`, { method: 'POST' })
}
