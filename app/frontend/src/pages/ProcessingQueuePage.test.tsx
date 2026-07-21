import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ProcessingQueuePage } from './ProcessingQueuePage'

const mocks = vi.hoisted(() => ({
  create: vi.fn(), active: vi.fn(), list: vi.fn(), start: vi.fn(), pause: vi.fn(), resume: vi.fn(), remove: vi.fn(), update: vi.fn(), deleteQueue: vi.fn(),
}))

vi.mock('../api/resumes', () => ({ listResumes: vi.fn().mockResolvedValue([{ id: 'resume-1', name: 'Resume', parse_status: 'completed' }]) }))
vi.mock('../api/processingQueues', () => ({
  createProcessingQueue: mocks.create, getActiveProcessingQueue: mocks.active, listProcessingQueues: mocks.list,
  startProcessingQueue: mocks.start, pauseProcessingQueue: mocks.pause,
  resumeProcessingQueue: mocks.resume, removeProcessingQueueItem: mocks.remove,
  updateProcessingQueueItem: mocks.update, deleteProcessingQueue: mocks.deleteQueue,
}))

function fillRequired(): void {
  fireEvent.change(screen.getByLabelText('Resume *'), { target: { value: 'resume-1' } })
  fireEvent.change(screen.getByLabelText('Recipient email *'), { target: { value: 'person@example.com' } })
  fireEvent.change(screen.getByLabelText('LinkedIn Post URL / JD URL *'), { target: { value: 'https://jobs.example.com/role' } })
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.active.mockRejectedValue(new Error('none'))
  mocks.list.mockResolvedValue([])
})

describe('ProcessingQueuePage', () => {
  it('renders clearly labelled vertical item cards and separate controls', async () => {
    render(<ProcessingQueuePage />)
    expect(await screen.findByText(/Nothing will process until/)).toBeInTheDocument()
    expect(screen.getByLabelText('Resume *')).toBeInTheDocument()
    expect(screen.getByLabelText('LinkedIn Post URL / JD URL *')).toBeInTheDocument()
    expect(screen.getByLabelText('LinkedIn Post Text (Optional)')).toBeInTheDocument()
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
    fireEvent.blur(screen.getByLabelText('LinkedIn Post URL / JD URL *'))
    expect(screen.getByText('LinkedIn Post URL / JD URL is required.')).toBeInTheDocument()
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
    expect(await screen.findByText('Queue status')).toBeInTheDocument()
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

  it('keeps another queue visible while the selected queue is running', async () => {
    const first = { id: 'queue-1', queue_number: 1, status: 'running', total_items: 2, completed_items: 1, failed_items: 0, created_at: '', updated_at: '', items: [] }
    const second = { id: 'queue-2', queue_number: 2, status: 'running', total_items: 3, completed_items: 0, failed_items: 0, created_at: '', updated_at: '', items: [] }
    mocks.active.mockResolvedValue(first)
    mocks.list.mockResolvedValue([first, second])
    render(<ProcessingQueuePage />)
    expect(await screen.findByText('Other Queues')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Queue 2/i })).toBeInTheDocument()
  })

  it('reloads and renders persisted extension capture details from the queue API', async () => {
    mocks.active.mockResolvedValue({ id: 'queue-1', status: 'draft', total_items: 1, completed_items: 0, failed_items: 0, created_at: '', updated_at: '', items: [{ id: 'item-1', position: 0, status: 'pending', generated_draft_id: null, error_code: null, created_at: '', updated_at: '', source_author_name: 'Ada', source_linkedin_post_url: 'https://linkedin.example/post', source_author_profile_url: 'https://linkedin.example/ada', source_linkedin_post_text: 'We are hiring.', source_job_description_url: 'https://jobs.example/1', source_job_description_text: 'Build reliable systems.' }] })
    render(<ProcessingQueuePage />)
    expect(await screen.findByRole('heading', { name: 'Ada' })).toBeInTheDocument()
    expect(screen.getByText('Captured details')).toBeInTheDocument()
    expect(screen.getByText('LinkedIn Post Text (Optional)')).toBeInTheDocument()
    expect(screen.getByText('Job Description')).toBeInTheDocument()
    expect(screen.getByText('We are hiring.')).toBeInTheDocument()
    expect(screen.getByText('Build reliable systems.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Author Profile' })).toHaveAttribute('href', 'https://linkedin.example/ada')
  })

  it('offers a new queue after a completed batch', async () => {
    mocks.active.mockResolvedValue({ id: 'queue-1', status: 'completed', total_items: 1, completed_items: 1, failed_items: 0, created_at: '', updated_at: '', items: [{ id: 'item-1', position: 0, status: 'completed' }] })
    render(<ProcessingQueuePage />)
    expect(await screen.findByText('Completed')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Pause Queue' })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Create New Queue' }))
    expect(await screen.findByRole('button', { name: 'Create Queue' })).toBeInTheDocument()
  })

  it('edits a missing JD and removes only the selected pending item', async () => {
    mocks.active.mockResolvedValue({ id: 'queue-1', status: 'draft', total_items: 1, completed_items: 0, failed_items: 0, created_at: '', updated_at: '', items: [{ id: 'item-1', position: 0, status: 'pending', generated_draft_id: null, error_code: null, created_at: '', updated_at: '', source_author_name: 'Ada', source_job_description_text: null }] })
    mocks.update.mockResolvedValue({ source_job_description_text: 'Manual JD' })
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    render(<ProcessingQueuePage />)
    fireEvent.click(await screen.findByRole('button', { name: 'Add Job Description' }))
    fireEvent.change(screen.getByLabelText('Job description text'), { target: { value: 'Manual JD' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save job description' }))
    expect(mocks.update).toHaveBeenCalledWith('queue-1', 'item-1', { job_description_text: 'Manual JD' })
    fireEvent.click(screen.getByRole('button', { name: 'Delete task' }))
    expect(mocks.remove).toHaveBeenCalledWith('queue-1', 'item-1')
  })

  it('derives completed and failed summary badges from current item states', async () => {
    mocks.list.mockResolvedValue([{ id: 'queue-1', status: 'completed_with_failures', total_items: 2, completed_items: 0, failed_items: 2, created_at: '', updated_at: '', items: [{ id: 'item-1', position: 0, status: 'completed', generated_draft_id: null, error_code: null, created_at: '', updated_at: '' }, { id: 'item-2', position: 1, status: 'failed', generated_draft_id: null, error_code: null, created_at: '', updated_at: '' }] }])
    render(<ProcessingQueuePage />)

    expect(await screen.findByText('2 of 2 processed')).toBeInTheDocument()
    expect(screen.getByText('1 completed')).toBeInTheDocument()
    expect(screen.getByText('1 failed')).toBeInTheDocument()
  })

  it('expands queue tasks independently and deletes an inactive queue after confirmation', async () => {
    const first = { id: 'queue-1', status: 'completed', total_items: 1, completed_items: 1, failed_items: 0, created_at: '', updated_at: '', items: [{ id: 'item-1', position: 0, status: 'completed', generated_draft_id: null, error_code: null, created_at: '', updated_at: '', source_author_name: 'Ada' }] }
    const second = { ...first, id: 'queue-2', items: [{ ...first.items[0], id: 'item-2', source_author_name: 'Bea' }] }
    mocks.list.mockResolvedValue([first, second]); mocks.deleteQueue.mockResolvedValue(undefined)
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    render(<ProcessingQueuePage />)

    const expand = await screen.findAllByRole('button', { name: 'Expand tasks' })
    fireEvent.click(expand[0])
    expect(screen.getByText('Ada')).toBeInTheDocument()
    expect(expand[0]).toHaveAttribute('aria-expanded', 'true')
    fireEvent.click(screen.getAllByRole('button', { name: 'Delete queue' })[0])
    await waitFor(() => expect(mocks.deleteQueue).toHaveBeenCalledWith('queue-1'))
    await waitFor(() => expect(screen.queryByText('Ada')).not.toBeInTheDocument())
  })
})
