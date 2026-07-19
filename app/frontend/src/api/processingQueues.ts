import { requestProtectedApi } from './client'
import type { EmailGenerationInput } from './emailGeneration'

export interface ProcessingQueueItem {
  id: string; position: number; status: 'pending' | 'processing' | 'completed' | 'failed'
  generated_draft_id: string | null; error_code: string | null; created_at: string; updated_at: string
}
export interface ProcessingQueue {
  id: string; status: 'draft' | 'running' | 'paused' | 'completed' | 'completed_with_failures'
  total_items: number; completed_items: number; failed_items: number; created_at: string; updated_at: string; items: ProcessingQueueItem[]
}
export const createProcessingQueue = (items: EmailGenerationInput[]) => requestProtectedApi<ProcessingQueue>('/api/v1/processing-queues', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ items }) })
export const getActiveProcessingQueue = () => requestProtectedApi<ProcessingQueue>('/api/v1/processing-queues/active')
export const startProcessingQueue = (id: string) => requestProtectedApi<ProcessingQueue>(`/api/v1/processing-queues/${id}/start`, { method: 'POST' })
export const pauseProcessingQueue = (id: string) => requestProtectedApi<ProcessingQueue>(`/api/v1/processing-queues/${id}/pause`, { method: 'POST' })
export const resumeProcessingQueue = (id: string) => requestProtectedApi<ProcessingQueue>(`/api/v1/processing-queues/${id}/resume`, { method: 'POST' })
export const removeProcessingQueueItem = (queueId: string, itemId: string) => requestProtectedApi<void>(`/api/v1/processing-queues/${queueId}/items/${itemId}`, { method: 'DELETE' })
