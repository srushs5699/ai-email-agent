import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { describe, expect, it, vi } from 'vitest'

import { ExtensionImportPage } from './ExtensionImportPage'
import { ApiRequestError } from '../api/client'

const mocks = vi.hoisted(() => ({ importExtensionCapture: vi.fn() }))
vi.mock('../api/extensionImport', () => ({ importExtensionCapture: mocks.importExtensionCapture }))

const payload = { version: 1, sourceUrl: 'https://www.linkedin.com/feed/update/urn:li:activity:123', authorName: 'Ada', authorProfileUrl: 'https://www.linkedin.com/in/ada', postText: 'Hiring platform engineers', jobDescriptionUrl: 'https://jobs.example.com/blocked', jobDescriptionSource: 'unavailable', importId: 'capture-12345678', warnings: [], capturedAt: '2026-07-19T00:00:00Z' }

describe('ExtensionImportPage', () => {
  it('queues the exact blocked-JD capture rather than showing Failed Tasks', async () => {
    mocks.importExtensionCapture.mockResolvedValue({ outcome: 'queued', status: 'queued', queue_id: 'queue-1', outreach_item_id: 'outreach-1', queue_capacity: 10 })
    render(<MemoryRouter><ExtensionImportPage /></MemoryRouter>)
    window.dispatchEvent(new MessageEvent('message', { origin: window.location.origin, source: window, data: { type: 'AI_EMAIL_AGENT_LINKEDIN_IMPORT', payload } }))
    expect(await screen.findByText('Added to Processing Queue.')).toBeInTheDocument()
    expect(screen.queryByText('Failed Tasks')).not.toBeInTheDocument()
    expect(mocks.importExtensionCapture).toHaveBeenCalledWith(expect.objectContaining({ linkedin_post_url: payload.sourceUrl, job_description_url: payload.jobDescriptionUrl, job_description_text: undefined, job_description_source: 'unavailable', idempotency_key: payload.importId }))
  })
  it('requires manual entry only for missing required capture fields', async () => {
    render(<MemoryRouter><ExtensionImportPage /></MemoryRouter>)
    window.dispatchEvent(new MessageEvent('message', { origin: window.location.origin, source: window, data: { type: 'AI_EMAIL_AGENT_LINKEDIN_IMPORT', payload: { ...payload, postText: undefined } } }))
    expect(await screen.findByText(/Manual information is required/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Open Manual Entry' })).toHaveAttribute('href', '/outreach?extensionImport=1')
  })
  it('shows a safe backend error detail instead of the generic fallback', async () => {
    mocks.importExtensionCapture.mockRejectedValue(new ApiRequestError('Unable to repair the existing extension capture.', 502))
    render(<MemoryRouter><ExtensionImportPage /></MemoryRouter>)
    window.dispatchEvent(new MessageEvent('message', { origin: window.location.origin, source: window, data: { type: 'AI_EMAIL_AGENT_LINKEDIN_IMPORT', payload } }))
    expect(await screen.findByText('Unable to repair the existing extension capture.')).toBeInTheDocument()
  })
})
