import { requestProtectedApi } from './client'

export type ExtensionImportPayload = { version: 1; linkedin_post_url: string; author_name: string; author_profile_url?: string; linkedin_post_text: string; job_description_url?: string; job_description_text?: string; job_description_source: 'visible_page' | 'manual' | 'unavailable'; idempotency_key: string; captured_at: string }
export type ExtensionImportResult = { outcome: 'queued' | 'existing' | 'validation_required' | 'error'; status?: 'queued' | 'repaired' | 'duplicate' | 'failed'; queue_id?: string; queue_item_id?: string; outreach_item_id?: string; failed_task_id?: string; queue_item_count?: number; queue_capacity: 10; created_new_queue?: boolean; queue_status?: string; reason?: string; existing_record_type?: string; existing_item_path?: string }

export const importExtensionCapture = (payload: ExtensionImportPayload) => requestProtectedApi<ExtensionImportResult>('/api/v1/extension/import', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
