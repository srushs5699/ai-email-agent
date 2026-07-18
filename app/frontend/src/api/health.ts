import { getPublicApi } from './client'

export interface HealthResponse {
  status: string
}

export async function getBackendHealth(): Promise<HealthResponse> {
  return getPublicApi<HealthResponse>('/health')
}
