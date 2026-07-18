const SELECTED_RESUME_STORAGE_KEY = 'ai-email-agent:selected-resume-id'

export function getSelectedResumeId(): string | null {
  return localStorage.getItem(SELECTED_RESUME_STORAGE_KEY)
}

export function setSelectedResumeId(resumeId: string): void {
  localStorage.setItem(SELECTED_RESUME_STORAGE_KEY, resumeId)
}

export function clearSelectedResumeId(): void {
  localStorage.removeItem(SELECTED_RESUME_STORAGE_KEY)
}
