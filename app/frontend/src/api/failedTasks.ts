import { requestProtectedApi } from './client'

export type FailedTaskStatus = 'failed' | 'duplicate' | 'no_email_available'
export interface FailedTask {
  id: string; processing_queue_item_id: string; queue_id: string; outreach_item_id: string | null
  generated_draft_id: string | null; resume_id: string | null; linkedin_post_url: string | null
  status: FailedTaskStatus; failure_reason: string; retry_count: number; retrying: boolean
  created_at: string; updated_at: string
}
export const listFailedTasks = () => requestProtectedApi<{ tasks: FailedTask[] }>('/api/v1/failed-tasks')
export const retryFailedTask = (id: string) => requestProtectedApi<FailedTask>(`/api/v1/failed-tasks/${id}/retry`, { method: 'POST' })
export const deleteFailedTask = (id: string) => requestProtectedApi<void>(`/api/v1/failed-tasks/${id}`, { method: 'DELETE' })
