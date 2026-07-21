import { requestProtectedApi } from './client'
import type { EmailGenerationInput } from './emailGeneration'

export interface ProcessingQueueItem {
  id: string; position: number; status: 'pending' | 'processing' | 'completed' | 'failed'
  generated_draft_id: string | null; error_code: string | null; created_at: string; updated_at: string
  failure_status?: string | null; failure_reason?: string | null; started_at?: string | null; completed_at?: string | null
  outreach_item_id?: string | null; source_linkedin_post_url?: string | null; source_author_name?: string | null
  source_author_profile_url?: string | null; source_linkedin_post_text?: string | null
  source_job_description_url?: string | null; source_job_description_text?: string | null
}
export interface ProcessingQueue {
  id: string; queue_number?: number; status: 'draft' | 'running' | 'paused' | 'completed' | 'completed_with_failures'
  total_items: number; completed_items: number; failed_items: number; created_at: string; updated_at: string; started_at?: string | null; paused_at?: string | null; completed_at?: string | null; items: ProcessingQueueItem[]
}
export const createProcessingQueue = (items: EmailGenerationInput[]) => requestProtectedApi<ProcessingQueue>('/api/v1/processing-queues', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ items }) })
export const getActiveProcessingQueue = () => requestProtectedApi<ProcessingQueue>('/api/v1/processing-queues/active')
export const listProcessingQueues = () => requestProtectedApi<ProcessingQueue[]>('/api/v1/processing-queues')
export const getProcessingQueue = (id: string) => requestProtectedApi<ProcessingQueue>(`/api/v1/processing-queues/${id}`)
export const deleteProcessingQueue = (id: string) => requestProtectedApi<void>(`/api/v1/processing-queues/${id}`, { method: 'DELETE' })
export const startProcessingQueue = (id: string) => requestProtectedApi<ProcessingQueue>(`/api/v1/processing-queues/${id}/start`, { method: 'POST' })
export const pauseProcessingQueue = (id: string) => requestProtectedApi<ProcessingQueue>(`/api/v1/processing-queues/${id}/pause`, { method: 'POST' })
export const resumeProcessingQueue = (id: string) => requestProtectedApi<ProcessingQueue>(`/api/v1/processing-queues/${id}/resume`, { method: 'POST' })
export const removeProcessingQueueItem = (queueId: string, itemId: string) => requestProtectedApi<void>(`/api/v1/processing-queues/${queueId}/items/${itemId}`, { method: 'DELETE' })
export const updateProcessingQueueItem = (queueId: string, itemId: string, update: Record<string, string>) => requestProtectedApi<ProcessingQueueItem>(`/api/v1/processing-queues/${queueId}/items/${itemId}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(update) })
