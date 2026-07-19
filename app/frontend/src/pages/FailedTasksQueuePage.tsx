import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { deleteFailedTask, listFailedTasks, retryFailedTask, type FailedTask } from '../api/failedTasks'
import './FailedTasksQueuePage.css'

const labels: Record<FailedTask['status'], string> = {
  failed: 'Failed', duplicate: 'Duplicate', no_email_available: 'No email available',
}
const date = (value: string) => new Date(value).toLocaleString()

export function FailedTasksQueuePage() {
  const [tasks, setTasks] = useState<FailedTask[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState<Record<string, 'retry' | 'delete' | undefined>>({})
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
    try { const updated = await retryFailedTask(task.id); setTasks((value) => value.map((item) => item.id === task.id ? updated : item)) }
    catch { setError('Unable to retry this failed task.') }
    finally { setBusy((value) => ({ ...value, [task.id]: undefined })) }
  }
  async function remove(task: FailedTask): Promise<void> {
    if (!window.confirm('Remove only this failed-task entry from the active Failed Tasks Queue? Related outreach, drafts, and resumes will be preserved.')) return
    setBusy((value) => ({ ...value, [task.id]: 'delete' })); setError('')
    try { await deleteFailedTask(task.id); setTasks((value) => value.filter((item) => item.id !== task.id)); setMessage('Failed-task entry removed.') }
    catch { setError('Unable to remove this failed task.') }
    finally { setBusy((value) => ({ ...value, [task.id]: undefined })) }
  }
  return <main className="failed-tasks-page"><div className="failed-tasks-container"><header><h1>Failed Tasks</h1><p>Review items that need attention, then retry them one at a time.</p><Link to="/processing-queue">Return to Processing Queue</Link></header>
    {loading && <p aria-live="polite">Loading failed tasks…</p>}{error && <p className="alert" role="alert">{error} <button onClick={() => void load()}>Try again</button></p>}{message && <p role="status" aria-live="polite" className="failed-tasks-message">{message}</p>}
    {!loading && !tasks.length && <section className="empty-state failed-tasks-empty"><h2>No failed tasks</h2><p>Items that cannot be processed will appear here for individual review and retry.</p></section>}
    <div className="failed-tasks-list">{tasks.map((task) => { const action = busy[task.id]; const disabled = Boolean(action) || task.retrying; return <article className="failed-task-card" key={task.id}><header><div><h2>Queue item {task.processing_queue_item_id.slice(0, 8)}</h2><span className={`failed-status failed-status--${task.status}`}>{labels[task.status]}</span></div><p>Updated {date(task.updated_at)} · Retry {task.retry_count}</p></header>
      <dl><div><dt>LinkedIn source</dt><dd>{task.linkedin_post_url ? <a href={task.linkedin_post_url} target="_blank" rel="noreferrer" aria-label={`Open LinkedIn source for queue item ${task.processing_queue_item_id}`}>{task.linkedin_post_url}</a> : 'No LinkedIn URL was provided.'}</dd></div><div><dt>Reason</dt><dd>{task.failure_reason}</dd></div><div><dt>Queue</dt><dd>{task.queue_id}</dd></div></dl>
      {task.retrying && <p role="status" aria-live="polite">Retrying this task…</p>}<div className="failed-task-actions"><button type="button" disabled={disabled} onClick={() => void retry(task)}>{action === 'retry' || task.retrying ? 'Retrying…' : 'Retry'}</button><button type="button" disabled={disabled} onClick={() => void remove(task)}>{action === 'delete' ? 'Removing…' : 'Delete'}</button></div></article> })}</div>
  </div></main>
}
