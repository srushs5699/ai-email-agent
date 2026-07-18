import { supabase } from '../lib/supabase'

export class ApiConfigurationError extends Error {}

export class MissingSessionError extends Error {}

export class ApiRequestError extends Error {
  readonly status: number

  constructor(
    message: string,
    status: number,
  ) {
    super(message)
    this.status = status
  }
}

export class ApiUnauthorizedError extends ApiRequestError {
  constructor() {
    super('Your session is no longer valid. Please sign in again.', 401)
  }
}

function getApiUrl(path: string): string {
  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL

  if (!apiBaseUrl) {
    throw new ApiConfigurationError('The backend URL is not configured.')
  }

  return `${apiBaseUrl.replace(/\/$/, '')}${path}`
}

async function parseResponse<T>(response: Response): Promise<T> {
  if (response.ok) {
    if (response.status === 204) {
      return undefined as T
    }

    return response.json() as Promise<T>
  }

  if (response.status === 401) {
    throw new ApiUnauthorizedError()
  }

  throw new ApiRequestError('The backend request failed.', response.status)
}

export async function getPublicApi<T>(path: string): Promise<T> {
  const response = await fetch(getApiUrl(path))

  return parseResponse<T>(response)
}

export async function getProtectedApi<T>(path: string): Promise<T> {
  return requestProtectedApi<T>(path)
}

export async function requestProtectedApi<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const { data, error } = await supabase.auth.getSession()
  const accessToken = data.session?.access_token

  if (error || !accessToken) {
    throw new MissingSessionError('No active application session is available.')
  }

  const headers = Object.fromEntries(new Headers(options.headers).entries())
  delete headers.authorization
  headers.Authorization = `Bearer ${accessToken}`

  const response = await fetch(getApiUrl(path), {
    ...options,
    headers,
  })

  return parseResponse<T>(response)
}
