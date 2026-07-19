import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { OutreachPage } from './OutreachPage'

const apiMocks = vi.hoisted(() => ({
  createDraft: vi.fn(),
  generateEmail: vi.fn(),
  getLatestDraft: vi.fn(),
  getGmailStatus: vi.fn(),
  authorizeGmail: vi.fn(),
  createGmailDraft: vi.fn(),
  syncGmailDraft: vi.fn(),
  listResumes: vi.fn(),
  updateDraft: vi.fn(),
  approveDraft: vi.fn(),
  sendDraft: vi.fn(),
}))

vi.mock('../api/resumes', () => ({ listResumes: apiMocks.listResumes }))
vi.mock('../api/emailGeneration', () => ({ generateEmail: apiMocks.generateEmail }))
vi.mock('../api/drafts', () => ({
  createDraft: apiMocks.createDraft,
  getLatestDraft: apiMocks.getLatestDraft,
  updateDraft: apiMocks.updateDraft,
  approveDraft: apiMocks.approveDraft,
  sendDraft: apiMocks.sendDraft,
}))
vi.mock('../api/gmail', () => ({
  getGmailStatus: apiMocks.getGmailStatus,
  authorizeGmail: apiMocks.authorizeGmail,
  createGmailDraft: apiMocks.createGmailDraft,
  syncGmailDraft: apiMocks.syncGmailDraft,
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
  apiMocks.getGmailStatus.mockResolvedValue({ configured: true, connected: false, authorization_required: false, google_email: null, granted_scopes: [] })
  apiMocks.authorizeGmail.mockResolvedValue({ authorization_url: 'https://accounts.google.com/test' })
  apiMocks.createGmailDraft.mockResolvedValue({ gmail_draft_id: 'gmail-1', gmail_message_id: null, sync_status: 'synced', created: true })
  apiMocks.syncGmailDraft.mockResolvedValue({ gmail_draft_id: 'gmail-1', gmail_message_id: null, sync_status: 'synced', created: false })
  apiMocks.approveDraft.mockResolvedValue({ approval_status: 'approved', approved_at: '2026-07-18T00:00:00Z' })
  apiMocks.sendDraft.mockResolvedValue({ send_status: 'sent', sent_at: '2026-07-18T00:01:00Z', gmail_sent_message_id: 'sent-1' })
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
      recipient_to: 'recipient@example.com',
      recipient_cc: undefined,
      resume_id: 'resume-1',
    })
    vi.useRealTimers()
  })

  it('shows Gmail connection states and creates one Gmail draft explicitly', async () => {
    apiMocks.getGmailStatus.mockResolvedValue({ configured: true, connected: true, authorization_required: false, google_email: 'person@example.com', granted_scopes: [] })
    render(<OutreachPage />)
    await screen.findByRole('option', { name: 'My Resume' })
    fillValidForm()
    fireEvent.click(screen.getByRole('button', { name: 'Generate Email' }))
    await screen.findByRole('button', { name: 'Create Gmail Draft' })
    fireEvent.click(screen.getByRole('button', { name: 'Create Gmail Draft' }))

    expect(await screen.findByText('Synced to Gmail')).toBeInTheDocument()
    expect(apiMocks.createGmailDraft).toHaveBeenCalledTimes(1)
    expect(screen.getByText('Gmail connected: person@example.com')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Send Email' })).toBeDisabled()
  })

  it('requires explicit approval before a separate send click', async () => {
    apiMocks.getGmailStatus.mockResolvedValue({ configured: true, connected: true, authorization_required: false, google_email: null, granted_scopes: [] })
    render(<OutreachPage />)
    await screen.findByRole('option', { name: 'My Resume' })
    fillValidForm()
    fireEvent.click(screen.getByRole('button', { name: 'Generate Email' }))
    await screen.findByRole('button', { name: 'Create Gmail Draft' })
    fireEvent.click(screen.getByRole('button', { name: 'Create Gmail Draft' }))
    const send = await screen.findByRole('button', { name: 'Send Email' })
    expect(send).toBeDisabled()
    fireEvent.click(screen.getByRole('button', { name: 'Approve Email' }))
    await screen.findByText('Approved — ready to send')
    expect(apiMocks.sendDraft).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: 'Send Email' }))
    expect(await screen.findByText(/Sent at/)).toBeInTheDocument()
    expect(apiMocks.sendDraft).toHaveBeenCalledTimes(1)
  })

  it('shows unavailable Gmail safely and preserves editable recipients', async () => {
    apiMocks.getGmailStatus.mockResolvedValue({ configured: false, connected: false, authorization_required: false, google_email: null, granted_scopes: [] })
    render(<OutreachPage />)
    await screen.findByRole('option', { name: 'My Resume' })
    fillValidForm()
    fireEvent.click(screen.getByRole('button', { name: 'Generate Email' }))
    await screen.findByText('Gmail integration is unavailable.')
    fireEvent.change(screen.getByLabelText('CC'), { target: { value: 'newcc@example.com' } })
    expect(screen.getAllByDisplayValue('newcc@example.com')).toHaveLength(2)
  })

  it('offers Connect Gmail while disconnected', async () => {
    render(<OutreachPage />)
    await screen.findByRole('option', { name: 'My Resume' })
    fillValidForm()
    fireEvent.click(screen.getByRole('button', { name: 'Generate Email' }))
    expect(await screen.findByRole('button', { name: 'Connect Gmail' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Connect Gmail' }))
    expect(apiMocks.authorizeGmail).toHaveBeenCalledTimes(1)
  })

  it('retries a failed Gmail sync without creating a new draft', async () => {
    apiMocks.getLatestDraft.mockResolvedValue({ id: 'draft-1', resume_id: 'resume-1', linkedin_post_text: 'A post', job_description_text: 'A role', no_job_description: false, recipient_to: 'recipient@example.com', recipient_cc: null, recipient_name: null, company_name: null, subject: 'Restored subject', body: 'Restored body', status: 'ready_for_review', gmail_draft_id: 'gmail-1', gmail_message_id: null, gmail_sync_status: 'sync_failed', gmail_sync_error_code: 'gmail_rate_limited' })
    render(<OutreachPage />)
    await screen.findByRole('button', { name: 'Retry Gmail Sync' })
    fireEvent.click(screen.getByRole('button', { name: 'Retry Gmail Sync' }))

    expect(await screen.findByText('Synced to Gmail')).toBeInTheDocument()
    expect(apiMocks.syncGmailDraft).toHaveBeenCalledWith('draft-1')
    expect(apiMocks.createGmailDraft).not.toHaveBeenCalled()
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
