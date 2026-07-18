import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ResumeLibraryPage } from './ResumeLibraryPage'

const resumeApiMocks = vi.hoisted(() => ({
  deleteResume: vi.fn(),
  listResumes: vi.fn(),
  uploadResume: vi.fn(),
}))

vi.mock('../api/resumes', () => resumeApiMocks)

const existingResume = {
  id: 'resume-1',
  name: 'My Resume',
  mime_type: 'application/pdf',
  file_size_bytes: 1024,
  parse_status: 'completed',
  created_at: '2026-07-17T00:00:00Z',
}

beforeEach(() => {
  localStorage.clear()
  resumeApiMocks.listResumes.mockResolvedValue([existingResume])
  resumeApiMocks.uploadResume.mockResolvedValue({
    ...existingResume,
    id: 'resume-2',
    name: 'New Resume',
  })
  resumeApiMocks.deleteResume.mockResolvedValue(undefined)
})

afterEach(() => {
  vi.clearAllMocks()
})

describe('ResumeLibraryPage', () => {
  it('uploads and selects a PDF resume', async () => {
    render(<ResumeLibraryPage />)
    await screen.findByText('My Resume')

    const file = new File(['pdf data'], 'new resume.pdf', {
      type: 'application/pdf',
    })
    fireEvent.change(screen.getByLabelText('Resume PDF'), {
      target: { files: [file] },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Upload resume' }))

    expect(await screen.findByText('New Resume')).toBeInTheDocument()
    expect(resumeApiMocks.uploadResume).toHaveBeenCalledWith(file)
    expect(localStorage.getItem('ai-email-agent:selected-resume-id')).toBe('resume-2')
  })

  it('shows a safe upload error', async () => {
    resumeApiMocks.uploadResume.mockRejectedValue(new Error('backend detail'))
    render(<ResumeLibraryPage />)
    await screen.findByText('My Resume')

    const file = new File(['pdf data'], 'resume.pdf', { type: 'application/pdf' })
    fireEvent.change(screen.getByLabelText('Resume PDF'), {
      target: { files: [file] },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Upload resume' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Unable to upload this resume',
    )
    expect(screen.queryByText('backend detail')).not.toBeInTheDocument()
  })

  it('deletes a selected resume and clears the selection', async () => {
    localStorage.setItem('ai-email-agent:selected-resume-id', 'resume-1')
    render(<ResumeLibraryPage />)
    await screen.findByText('(selected)')

    fireEvent.click(screen.getByRole('button', { name: 'Delete' }))

    expect(await screen.findByText('No resumes yet. Upload a PDF to get started.')).toBeInTheDocument()
    expect(resumeApiMocks.deleteResume).toHaveBeenCalledWith('resume-1')
    expect(localStorage.getItem('ai-email-agent:selected-resume-id')).toBeNull()
  })
})
