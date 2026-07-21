import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router'
import { FailedTasksQueuePage } from './FailedTasksQueuePage'

const api = vi.hoisted(() => ({ list: vi.fn(), retry: vi.fn(), update: vi.fn(), remove: vi.fn() }))
vi.mock('../api/failedTasks', () => ({ listFailedTasks: api.list, retryFailedTask: api.retry, updateFailedTask: api.update, deleteFailedTask: api.remove }))
const task = { id: 'task-1', processing_queue_item_id: 'queue-item-1', queue_id: 'queue-1', outreach_item_id: null, generated_draft_id: null, resume_id: 'resume-1', linkedin_post_url: 'https://www.linkedin.com/posts/example', status: 'no_email_available' as const, failure_reason: 'No usable recipient email is available.', retry_count: 0, retrying: false, created_at: '2026-07-23T00:00:00Z', updated_at: '2026-07-23T00:00:00Z' }
beforeEach(() => { vi.clearAllMocks(); api.list.mockResolvedValue({ tasks: [] }); vi.stubGlobal('confirm', vi.fn(() => true)) })
describe('FailedTasksQueuePage', () => {
  it('shows an accessible empty state', async () => { render(<MemoryRouter><FailedTasksQueuePage /></MemoryRouter>); expect(await screen.findByText('No failed tasks')).toBeInTheDocument() })
  it('shows stage, reason, status and retries only the selected task', async () => { api.list.mockResolvedValue({ tasks: [{ ...task, failure_stage: 'ai_generation', failed_at: '2026-07-24T00:00:00Z' }] }); api.retry.mockResolvedValue({ ...task, retrying: true }); render(<MemoryRouter><FailedTasksQueuePage /></MemoryRouter>); const link = await screen.findByRole('link', { name: /open source/i }); expect(link).toHaveAttribute('href', task.linkedin_post_url); expect(screen.getByText('No email available')).toBeInTheDocument(); expect(screen.getByText(task.failure_reason)).toBeInTheDocument(); expect(screen.getByText('Ai Generation')).toBeInTheDocument(); fireEvent.click(screen.getByRole('button', { name: 'Retry Processing' })); expect(await screen.findByRole('button', { name: 'Retrying…' })).toBeDisabled(); expect(api.retry).toHaveBeenCalledWith('task-1') })
  it('requires confirmation before deleting', async () => { api.list.mockResolvedValue({ tasks: [task] }); const confirm = vi.fn(() => false); vi.stubGlobal('confirm', confirm); render(<MemoryRouter><FailedTasksQueuePage /></MemoryRouter>); fireEvent.click(await screen.findByRole('button', { name: 'Delete' })); expect(confirm).toHaveBeenCalled(); expect(api.remove).not.toHaveBeenCalled() })
  it('saves the queue-item ID and enables retry after a successful edit', async () => {
    api.list.mockResolvedValue({ tasks: [task] })
    api.update.mockResolvedValue({ ...task, recipient_to: 'corrected@example.com' })
    render(<MemoryRouter><FailedTasksQueuePage /></MemoryRouter>)

    fireEvent.click(await screen.findByRole('button', { name: 'Edit' }))
    fireEvent.change(screen.getByLabelText('Recipient email'), { target: { value: 'corrected@example.com' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save Changes' }))

    expect(await screen.findByText(/changes saved/i)).toBeInTheDocument()
    expect(api.update).toHaveBeenCalledWith('task-1', expect.objectContaining({ recipient_to: 'corrected@example.com' }))
    expect(screen.getByRole('button', { name: 'Retry Processing' })).toBeEnabled()
  })
  it('shows the API error when save or retry fails', async () => {
    api.list.mockResolvedValue({ tasks: [task] })
    api.update.mockRejectedValue(new Error('Failed task not found.'))
    render(<MemoryRouter><FailedTasksQueuePage /></MemoryRouter>)

    fireEvent.click(await screen.findByRole('button', { name: 'Edit' }))
    fireEvent.click(screen.getByRole('button', { name: 'Save Changes' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Save failed: Failed task not found.')
  })
  it('persists the canonical unavailable job-description state', async () => {
    api.list.mockResolvedValue({ tasks: [task] })
    api.update.mockResolvedValue({ ...task, no_job_description: true, job_description_source: 'unavailable' })
    render(<MemoryRouter><FailedTasksQueuePage /></MemoryRouter>)

    fireEvent.click(await screen.findByRole('button', { name: 'Edit' }))
    fireEvent.click(screen.getByLabelText('No job description available'))
    fireEvent.click(screen.getByRole('button', { name: 'Save Changes' }))

    expect(api.update).toHaveBeenCalledWith('task-1', expect.objectContaining({
      no_job_description: true,
      job_description_source: 'unavailable',
      job_description_text: '',
    }))
  })
})
