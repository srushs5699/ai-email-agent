import { requestProtectedApi } from './client'

export function deleteOutreachItem(outreachItemId: string): Promise<{ deleted: true; outreach_item_id: string }> {
  return requestProtectedApi(`/api/v1/outreach-items/${outreachItemId}`, { method: 'DELETE' })
}
