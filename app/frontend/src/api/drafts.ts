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
  resume_id: string | null
  status: 'draft' | 'ready_for_review'
  created_at: string
  updated_at: string
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

export function updateDraft(
  draftId: string,
  input: Pick<DraftInput, 'subject' | 'body'>,
): Promise<Draft> {
  return requestProtectedApi<Draft>(`/api/v1/drafts/${draftId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
}
