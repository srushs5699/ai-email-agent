import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { OutreachPage } from './OutreachPage'

const apiMocks = vi.hoisted(() => ({
  generateEmail: vi.fn(),
  listResumes: vi.fn(),
}))

vi.mock('../api/resumes', () => ({ listResumes: apiMocks.listResumes }))
vi.mock('../api/emailGeneration', () => ({ generateEmail: apiMocks.generateEmail }))

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
})
