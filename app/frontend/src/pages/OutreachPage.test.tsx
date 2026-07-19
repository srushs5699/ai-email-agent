import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { OutreachPage } from './OutreachPage'

const apiMocks = vi.hoisted(() => ({
  createDraft: vi.fn(),
  generateEmail: vi.fn(),
  getLatestDraft: vi.fn(),
  listResumes: vi.fn(),
  updateDraft: vi.fn(),
}))

vi.mock('../api/resumes', () => ({ listResumes: apiMocks.listResumes }))
vi.mock('../api/emailGeneration', () => ({ generateEmail: apiMocks.generateEmail }))
vi.mock('../api/drafts', () => ({
  createDraft: apiMocks.createDraft,
  getLatestDraft: apiMocks.getLatestDraft,
  updateDraft: apiMocks.updateDraft,
}))

beforeEach(() => {
  localStorage.clear()
  apiMocks.listResumes.mockResolvedValue([
    {
      id: 'resume-1',
      name: 'My Resume',
      mime_type: 'application/pdf',
      file_size_bytes: 1024,
      parse_status: 'completed',
      created_at: '2026-07-17T00:00:00Z',
    },
  ])
  apiMocks.generateEmail.mockResolvedValue({
    subject: 'Hello there',
    body: 'I would love to connect.',
  })
  apiMocks.createDraft.mockResolvedValue({
    id: 'draft-1',
    status: 'ready_for_review',
    created_at: '2026-07-18T00:00:00Z',
    updated_at: '2026-07-18T00:00:00Z',
  })
  apiMocks.getLatestDraft.mockRejectedValue(new Error('no draft'))
  apiMocks.updateDraft.mockResolvedValue({})
  Object.defineProperty(navigator, 'clipboard', {
    configurable: true,
    value: { writeText: vi.fn().mockResolvedValue(undefined) },
  })
})

afterEach(() => {
  vi.clearAllMocks()
})

function fillValidForm(): void {
  fireEvent.change(screen.getByLabelText('LinkedIn post text'), {
    target: { value: 'We are expanding our platform team.' },
  })
  fireEvent.change(screen.getByLabelText('Job description text'), {
    target: { value: 'Build robust backend services.' },
  })
  fireEvent.change(screen.getByLabelText('To'), {
    target: { value: 'recipient@example.com' },
  })
}

describe('OutreachPage', () => {
  it('validates required outreach inputs', async () => {
    render(<OutreachPage />)
    await screen.findByRole('option', { name: 'My Resume' })

    fireEvent.click(screen.getByRole('button', { name: 'Generate Email' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Add LinkedIn post text or a job description.',
    )
    expect(apiMocks.generateEmail).not.toHaveBeenCalled()
  })

  it('generates and displays editable email content', async () => {
    render(<OutreachPage />)
    await screen.findByRole('option', { name: 'My Resume' })
    fillValidForm()

    fireEvent.click(screen.getByRole('button', { name: 'Generate Email' }))

    expect(await screen.findByDisplayValue('Hello there')).toBeInTheDocument()
    expect(screen.getByDisplayValue('I would love to connect.')).toBeInTheDocument()
    expect(apiMocks.generateEmail).toHaveBeenCalledWith(
      expect.objectContaining({
        recipient_to: 'recipient@example.com',
        resume_id: 'resume-1',
      }),
    )
    expect(apiMocks.createDraft).toHaveBeenCalledWith(
      expect.objectContaining({ subject: 'Hello there', body: 'I would love to connect.' }),
    )
  })

  it('persists an outreach-page resume selection', async () => {
    apiMocks.listResumes.mockResolvedValue([
      {
        id: 'resume-1',
        name: 'My Resume',
        mime_type: 'application/pdf',
        file_size_bytes: 1024,
        parse_status: 'completed',
        created_at: '2026-07-17T00:00:00Z',
      },
      {
        id: 'resume-2',
        name: 'Second Resume',
        mime_type: 'application/pdf',
        file_size_bytes: 2048,
        parse_status: 'completed',
        created_at: '2026-07-18T00:00:00Z',
      },
    ])
    render(<OutreachPage />)
    await screen.findByRole('option', { name: 'Second Resume' })

    fireEvent.change(screen.getByLabelText('Resume'), {
      target: { value: 'resume-2' },
    })

    expect(localStorage.getItem('ai-email-agent:selected-resume-id')).toBe(
      'resume-2',
    )
  })

  it('shows a safe generation error', async () => {
    apiMocks.generateEmail.mockRejectedValue(new Error('provider detail'))
    render(<OutreachPage />)
    await screen.findByRole('option', { name: 'My Resume' })
    fillValidForm()

    fireEvent.click(screen.getByRole('button', { name: 'Generate Email' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Unable to generate an email right now.',
    )
    expect(screen.queryByText('provider detail')).not.toBeInTheDocument()
  })

  it('copies the generated subject', async () => {
    render(<OutreachPage />)
    await screen.findByRole('option', { name: 'My Resume' })
    fillValidForm()
    fireEvent.click(screen.getByRole('button', { name: 'Generate Email' }))
    await screen.findByDisplayValue('Hello there')

    fireEvent.click(screen.getByRole('button', { name: 'Copy Subject' }))

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith('Hello there')
  })

  it('restores the latest draft when the page opens', async () => {
    apiMocks.getLatestDraft.mockResolvedValue({
      id: 'draft-1',
      resume_id: 'resume-1',
      linkedin_post_text: 'A post',
      job_description_text: 'A role',
      no_job_description: false,
      recipient_to: 'recipient@example.com',
      recipient_cc: 'cc@example.com',
      recipient_name: 'Alex',
      company_name: 'Example',
      subject: 'Restored subject',
      body: 'Restored body',
      status: 'ready_for_review',
    })
    render(<OutreachPage />)

    expect(await screen.findByDisplayValue('Restored subject')).toBeInTheDocument()
    expect(screen.getByDisplayValue('Restored body')).toBeInTheDocument()
    expect(screen.getByDisplayValue('Example')).toBeInTheDocument()
  })

  it('autosaves only the latest edited content after the debounce', async () => {
    render(<OutreachPage />)
    await screen.findByRole('option', { name: 'My Resume' })
    fillValidForm()
    fireEvent.click(screen.getByRole('button', { name: 'Generate Email' }))
    await screen.findByDisplayValue('Hello there')

    vi.useFakeTimers()
    fireEvent.change(screen.getByLabelText('Subject'), { target: { value: 'First' } })
    fireEvent.change(screen.getByLabelText('Subject'), { target: { value: 'Final' } })
    await vi.advanceTimersByTimeAsync(800)

    expect(apiMocks.updateDraft).toHaveBeenCalledTimes(1)
    expect(apiMocks.updateDraft).toHaveBeenCalledWith('draft-1', {
      subject: 'Final',
      body: 'I would love to connect.',
    })
    vi.useRealTimers()
  })

  it('start over clears the restored draft without restoring it again', async () => {
    apiMocks.getLatestDraft.mockResolvedValue({
      id: 'draft-1', resume_id: 'resume-1', linkedin_post_text: '',
      job_description_text: 'A role', no_job_description: false,
      recipient_to: 'recipient@example.com', recipient_cc: null,
      recipient_name: null, company_name: null, subject: 'Restored subject',
      body: 'Restored body', status: 'ready_for_review',
    })
    render(<OutreachPage />)
    await screen.findByDisplayValue('Restored subject')
    fireEvent.click(screen.getByRole('button', { name: 'Start Over' }))

    expect(screen.queryByDisplayValue('Restored subject')).not.toBeInTheDocument()
    expect(screen.queryByText('Saved')).not.toBeInTheDocument()
  })
})
