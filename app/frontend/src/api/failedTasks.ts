import { requestProtectedApi } from './client'

export type FailedTaskStatus = 'failed' | 'duplicate' | 'no_email_available'
export interface FailedTask {
  id: string; processing_queue_item_id: string; queue_id: string; outreach_item_id: string | null
  generated_draft_id: string | null; resume_id: string | null; linkedin_post_url: string | null
  job_description_url?: string | null; author_name?: string | null; author_profile_url?: string | null; linkedin_post_text?: string | null
  job_description_text?: string | null; recipient_to?: string | null; recipient_cc?: string | null
  no_job_description?: boolean | null; job_description_source?: 'visible_page' | 'manual' | 'unavailable' | null
  status: FailedTaskStatus; failure_reason: string; retry_count: number; retrying: boolean
  failure_stage?: string | null; failed_at?: string | null
  created_at: string; updated_at: string
}
export const listFailedTasks = () => requestProtectedApi<{ tasks: FailedTask[] }>('/api/v1/failed-tasks')
export const retryFailedTask = (id: string) => requestProtectedApi<FailedTask>(`/api/v1/failed-tasks/${id}/retry`, { method: 'POST' })
export const updateFailedTask = (id: string, update: Record<string, string | boolean>) => requestProtectedApi<FailedTask>(`/api/v1/failed-tasks/${id}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(update) })
export const deleteFailedTask = (id: string) => requestProtectedApi<void>(`/api/v1/failed-tasks/${id}`, { method: 'DELETE' })
