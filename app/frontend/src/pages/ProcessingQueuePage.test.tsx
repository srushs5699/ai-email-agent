import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ProcessingQueuePage } from './ProcessingQueuePage'

const mocks = vi.hoisted(() => ({
  create: vi.fn(), active: vi.fn(), start: vi.fn(), pause: vi.fn(), resume: vi.fn(), remove: vi.fn(),
}))

vi.mock('../api/resumes', () => ({ listResumes: vi.fn().mockResolvedValue([{ id: 'resume-1', name: 'Resume', parse_status: 'completed' }]) }))
vi.mock('../api/processingQueues', () => ({
  createProcessingQueue: mocks.create, getActiveProcessingQueue: mocks.active,
  startProcessingQueue: mocks.start, pauseProcessingQueue: mocks.pause,
  resumeProcessingQueue: mocks.resume, removeProcessingQueueItem: mocks.remove,
}))

function fillRequired(): void {
  fireEvent.change(screen.getByLabelText('Resume *'), { target: { value: 'resume-1' } })
  fireEvent.change(screen.getByLabelText('LinkedIn post text *'), { target: { value: 'A LinkedIn post' } })
  fireEvent.change(screen.getByLabelText('Recipient email *'), { target: { value: 'person@example.com' } })
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.active.mockRejectedValue(new Error('none'))
})

describe('ProcessingQueuePage', () => {
  it('renders clearly labelled vertical item cards and separate controls', async () => {
    render(<ProcessingQueuePage />)
    expect(await screen.findByText(/Nothing will process until/)).toBeInTheDocument()
    expect(screen.getByLabelText('Resume *')).toBeInTheDocument()
    expect(screen.getByLabelText('LinkedIn post text *')).toBeInTheDocument()
    expect(screen.getByLabelText('Recipient email *')).toBeInTheDocument()
    expect(screen.getByText('Optional')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '+ Add another item' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Create Queue' })).toBeDisabled()
    expect(screen.getByText('1 of 10 items')).toBeInTheDocument()
    expect(screen.queryByText(/Review Queue/i)).not.toBeInTheDocument()
  })

  it('shows inline validation and renumbers cards after removal', async () => {
    render(<ProcessingQueuePage />)
    await screen.findByText('1 of 10 items')
    fireEvent.blur(screen.getByLabelText('LinkedIn post text *'))
    expect(screen.getByText('LinkedIn post text is required.')).toBeInTheDocument()
    expect(screen.getByText('Recipient email is required.')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '+ Add another item' }))
    expect(screen.getByRole('heading', { name: 'Item 2' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Remove item 1' }))
    expect(screen.getByRole('heading', { name: 'Item 1' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Item 2' })).not.toBeInTheDocument()
  })

  it('shows the maximum message at ten items', async () => {
    render(<ProcessingQueuePage />)
    await screen.findByText('1 of 10 items')
    const add = screen.getByRole('button', { name: '+ Add another item' })
    for (let count = 1; count < 10; count += 1) fireEvent.click(add)
    expect(screen.getByText('Maximum of 10 items reached')).toBeInTheDocument()
    expect(add).toBeDisabled()
  })

  it('displays a draft queue and does not start it automatically', async () => {
    mocks.create.mockResolvedValue({ id: 'queue-1', status: 'draft', total_items: 1, completed_items: 0, failed_items: 0, created_at: '', updated_at: '', items: [{ id: 'item-1', position: 0, status: 'pending', generated_draft_id: null, error_code: null, created_at: '', updated_at: '' }] })
    render(<ProcessingQueuePage />)
    await screen.findByText('1 of 10 items')
    fillRequired()
    fireEvent.click(screen.getByRole('button', { name: 'Create Queue' }))
    expect(await screen.findByText('Queue status:')).toBeInTheDocument()
    expect(screen.getByText('Draft')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Start Queue' })).toBeInTheDocument()
    expect(mocks.start).not.toHaveBeenCalled()
  })

  it('shows pause only for a running active queue', async () => {
    mocks.active.mockResolvedValue({ id: 'queue-1', status: 'running', total_items: 1, completed_items: 0, failed_items: 0, created_at: '', updated_at: '', items: [] })
    render(<ProcessingQueuePage />)
    expect(await screen.findByRole('button', { name: 'Pause Queue' })).toBeInTheDocument()
  })

  it('shows resume only for a paused active queue', async () => {
    mocks.active.mockResolvedValue({ id: 'queue-1', status: 'paused', total_items: 1, completed_items: 0, failed_items: 0, created_at: '', updated_at: '', items: [] })
    render(<ProcessingQueuePage />)
    expect(await screen.findByRole('button', { name: 'Resume Queue' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Pause Queue' })).not.toBeInTheDocument()
  })

  it('offers a new queue after a completed batch', async () => {
    mocks.active.mockResolvedValue({ id: 'queue-1', status: 'completed', total_items: 1, completed_items: 1, failed_items: 0, created_at: '', updated_at: '', items: [{ id: 'item-1', position: 0, status: 'completed' }] })
    render(<ProcessingQueuePage />)
    expect(await screen.findByText('Completed')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Pause Queue' })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Create New Queue' }))
    expect(await screen.findByRole('button', { name: 'Create Queue' })).toBeInTheDocument()
  })
})
