import { requestProtectedApi } from './client'

export interface ResumeMetadata {
  id: string
  name: string
  mime_type: string
  file_size_bytes: number
  parse_status: string
  created_at: string
}

export function listResumes(): Promise<ResumeMetadata[]> {
  return requestProtectedApi<ResumeMetadata[]>('/api/v1/resumes')
}

export function uploadResume(file: File): Promise<ResumeMetadata> {
  const formData = new FormData()
  formData.append('file', file)

  return requestProtectedApi<ResumeMetadata>('/api/v1/resumes', {
    method: 'POST',
    body: formData,
  })
}

export function deleteResume(resumeId: string): Promise<void> {
  return requestProtectedApi<void>(`/api/v1/resumes/${resumeId}`, {
    method: 'DELETE',
  })
}
