import { requestProtectedApi } from './client'

export interface EmailGenerationInput {
  resume_id: string
  linkedin_post_url?: string
  linkedin_post_text: string
  job_description_text: string
  no_job_description: boolean
  recipient_to: string
  recipient_cc?: string
  recipient_name?: string
  company_name?: string
}

export interface GeneratedEmail {
  subject: string
  body: string
}

export function generateEmail(
  input: EmailGenerationInput,
): Promise<GeneratedEmail> {
  return requestProtectedApi<GeneratedEmail>('/api/v1/email-generation', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
}
