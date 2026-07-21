import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { deleteFailedTask, listFailedTasks, retryFailedTask, updateFailedTask, type FailedTask } from '../api/failedTasks'
import './FailedTasksQueuePage.css'

const labels: Record<FailedTask['status'], string> = {
  failed: 'Failed', duplicate: 'Duplicate', no_email_available: 'No email available',
}
const date = (value: string) => new Date(value).toLocaleString()
const stageLabel = (stage: string | null | undefined) => stage
  ? stage.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
  : 'Processing'

function requestErrorMessage(action: string, error: unknown): string {
  return error instanceof Error ? `${action}: ${error.message}` : `${action}: request failed.`
}

export function FailedTasksQueuePage() {
  const [tasks, setTasks] = useState<FailedTask[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState<Record<string, 'retry' | 'delete' | undefined>>({})
  const [editing, setEditing] = useState<string | null>(null)
  const [edit, setEdit] = useState<Record<string, string | boolean>>({})
  async function load(): Promise<void> {
    setLoading(true); setError('')
    try { setTasks((await listFailedTasks()).tasks) } catch { setError('Unable to load Failed Tasks. Please try again.') } finally { setLoading(false) }
  }
  useEffect(() => {
    void listFailedTasks().then(({ tasks: loaded }) => setTasks(loaded)).catch(() => setError('Unable to load Failed Tasks. Please try again.')).finally(() => setLoading(false))
  }, [])
  useEffect(() => {
    if (!tasks.some((task) => task.retrying)) return
    const timer = window.setInterval(() => { void listFailedTasks().then(({ tasks: current }) => {
      const retryFinished = tasks.some((task) => task.retrying && !current.some((next) => next.id === task.id))
      if (retryFinished) setMessage('Draft created and ready in the Review Queue. It has not been approved or sent.')
      setTasks(current)
    }).catch(() => undefined) }, 1000)
    return () => window.clearInterval(timer)
  }, [tasks])
  async function retry(task: FailedTask): Promise<void> {
    if (busy[task.id] || task.retrying) return
    setBusy((value) => ({ ...value, [task.id]: 'retry' })); setError(''); setMessage('')
    try {
      await retryFailedTask(task.id)
      setTasks((current) => current.filter((item) => item.id !== task.id))
      setEditing((current) => current === task.id ? null : current)
      setMessage('Task moved to Processing Queue.')
    }
    catch (error: unknown) { setError(requestErrorMessage('Retry failed', error)) }
    finally { setBusy((value) => ({ ...value, [task.id]: undefined })) }
  }
  async function remove(task: FailedTask): Promise<void> {
    if (!window.confirm('Permanently delete this failed task and related data? Its LinkedIn post can be imported again.')) return
    setBusy((value) => ({ ...value, [task.id]: 'delete' })); setError('')
    try { await deleteFailedTask(task.id); setTasks((value) => value.filter((item) => item.id !== task.id)); setMessage('Task permanently deleted. This LinkedIn post can be imported again.') }
    catch { setError('Unable to delete this failed task. It is still visible.') }
    finally { setBusy((value) => ({ ...value, [task.id]: undefined })) }
  }
  async function save(task: FailedTask): Promise<void> {
    setError(''); setMessage('')
    try {
      const updated = await updateFailedTask(task.id, edit)
      setTasks((current) => current.map((item) => item.id === task.id ? updated : item))
      setEditing(null)
      setEdit({})
      setMessage('Changes saved. Edited — ready to retry.')
    }
    catch (error: unknown) { setError(requestErrorMessage('Save failed', error)) }
  }
  return <main className="failed-tasks-page"><div className="failed-tasks-container"><header><h1>Failed Tasks</h1><p>Review items that need attention, then retry them one at a time.</p><Link to="/processing-queue">Return to Processing Queue</Link></header>
    {loading && <p aria-live="polite">Loading failed tasks…</p>}{error && <p className="alert" role="alert">{error} <button onClick={() => void load()}>Try again</button></p>}{message && <p role="status" aria-live="polite" className="failed-tasks-message">{message}</p>}
    {!loading && !tasks.length && <section className="empty-state failed-tasks-empty"><h2>No failed tasks</h2><p>Items that cannot be processed will appear here for individual review and retry.</p></section>}
    <div className="failed-tasks-list">{tasks.map((task) => { const action = busy[task.id]; const disabled = Boolean(action) || task.retrying; return <article className="failed-task-card" key={task.id}><header><div><h2>Queue item {task.processing_queue_item_id.slice(0, 8)}</h2><span className={`failed-status failed-status--${task.status}`}>{labels[task.status]}</span></div><p>Updated {date(task.updated_at)} · Retry {task.retry_count}</p></header>
      <dl><div><dt>Source URL</dt><dd>{task.linkedin_post_url ? <a href={task.linkedin_post_url} target="_blank" rel="noreferrer" aria-label={`Open source for queue item ${task.processing_queue_item_id}`}>{task.linkedin_post_url}</a> : 'No source URL was provided.'}</dd></div><div><dt>Failure stage</dt><dd>{stageLabel(task.failure_stage)}</dd></div><div><dt>Reason</dt><dd>{task.failure_reason || 'This task could not be completed.'}</dd></div><div><dt>Failed</dt><dd>{task.failed_at ? date(task.failed_at) : 'Not available'}</dd></div><div><dt>Queue</dt><dd>{task.queue_id}</dd></div></dl>
      {editing === task.id && <form className="failed-task-editor" onSubmit={(event) => { event.preventDefault(); void save(task) }}><h3>Edit failed task</h3><p className="failed-task-editor__failure"><strong>Latest failure:</strong> {task.failure_reason}</p><label>Recipient email<input aria-label="Recipient email" type="email" value={String(edit.recipient_to ?? '')} onChange={(event) => setEdit((value) => ({ ...value, recipient_to: event.target.value }))} /></label><label>LinkedIn Post URL / JD URL<input aria-label="LinkedIn Post URL / JD URL" placeholder="Paste a LinkedIn post URL, job URL, or JD URL" type="url" value={String(edit.linkedin_post_url ?? '')} onChange={(event) => setEdit((value) => ({ ...value, linkedin_post_url: event.target.value }))} /></label><label>LinkedIn Post Text (Optional)<textarea aria-label="LinkedIn Post Text (Optional)" value={String(edit.linkedin_post_text ?? '')} onChange={(event) => setEdit((value) => ({ ...value, linkedin_post_text: event.target.value }))} /></label><label>Job description (Optional)<textarea aria-label="Job description text" disabled={edit.no_job_description === true} value={String(edit.job_description_text ?? '')} onChange={(event) => setEdit((value) => ({ ...value, job_description_text: event.target.value, no_job_description: false, job_description_source: event.target.value.trim() ? 'manual' : 'unavailable' }))} /></label><label><input aria-label="No job description available" type="checkbox" checked={edit.no_job_description === true} onChange={(event) => setEdit((value) => ({ ...value, no_job_description: event.target.checked, job_description_source: event.target.checked ? 'unavailable' : 'manual', job_description_text: event.target.checked ? '' : value.job_description_text }))} /> No job description available</label><div className="failed-task-editor__actions"><button type="submit">Save Changes</button><button type="button" onClick={() => { setEditing(null); setEdit({}) }}>Cancel</button></div></form>}{task.retrying && <p role="status" aria-live="polite">Retrying this task…</p>}<div className="failed-task-actions"><button type="button" disabled={disabled} onClick={() => { setError(''); setMessage(''); setEditing(task.id); setEdit({ recipient_to: task.recipient_to ?? '', linkedin_post_url: task.linkedin_post_url ?? '', linkedin_post_text: task.linkedin_post_text ?? '', job_description_text: task.job_description_text ?? '', no_job_description: task.no_job_description ?? task.job_description_source === 'unavailable', job_description_source: task.job_description_source ?? (task.job_description_text ? 'manual' : 'unavailable') }) }}>Edit</button><button type="button" disabled={disabled || editing === task.id} onClick={() => void retry(task)}>{action === 'retry' || task.retrying ? 'Retrying…' : 'Retry Processing'}</button><button type="button" disabled={disabled} onClick={() => void remove(task)}>{action === 'delete' ? 'Deleting…' : 'Delete'}</button></div></article> })}</div>
  </div></main>
}
