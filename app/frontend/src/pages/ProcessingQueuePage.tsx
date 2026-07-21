import { useEffect, useState, type ReactNode } from 'react'

import type { EmailGenerationInput } from '../api/emailGeneration'
import {
  createProcessingQueue,
  deleteProcessingQueue,
  getActiveProcessingQueue,
  getProcessingQueue,
  listProcessingQueues,
  pauseProcessingQueue,
  resumeProcessingQueue,
  removeProcessingQueueItem,
  startProcessingQueue,
  updateProcessingQueueItem,
  type ProcessingQueue,
} from '../api/processingQueues'
import { listResumes, type ResumeMetadata } from '../api/resumes'
import { formatPacificDateTime } from '../lib/dates'
import './ProcessingQueuePage.css'

const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
const blank = (): EmailGenerationInput => ({
  resume_id: '', linkedin_post_url: '', linkedin_post_text: '', job_description_text: '',
  no_job_description: false, recipient_to: '', recipient_cc: '',
  recipient_name: '', company_name: '',
})

function fieldError(item: EmailGenerationInput, field: keyof EmailGenerationInput): string | null {
  if (field === 'resume_id' && !item.resume_id) return 'Select a resume.'
  if (field === 'linkedin_post_url') {
    const value = item.linkedin_post_url.trim()
    if (!value) return 'LinkedIn Post URL / JD URL is required.'
    try {
      const url = new URL(value)
      if (!['http:', 'https:'].includes(url.protocol)) return 'Only HTTP and HTTPS URLs are allowed.'
    } catch { return 'Enter a valid HTTP or HTTPS LinkedIn post, job, or JD URL.' }
  }
  if (field === 'recipient_to') {
    if (!item.recipient_to.trim()) return 'Recipient email is required.'
    if (!emailPattern.test(item.recipient_to.trim())) return 'Enter a valid recipient email address.'
  }
  return null
}

function isValid(item: EmailGenerationInput): boolean {
  return !fieldError(item, 'resume_id') && !fieldError(item, 'linkedin_post_url') && !fieldError(item, 'recipient_to')
}

function titleCase(value: string): string {
  return value.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
}

function taskLabel(status: string, errorCode: string | null): string {
  if (status === 'completed') return 'Ready for Review'
  if (errorCode === 'duplicate') return 'Duplicate'
  if (errorCode === 'no_email_available') return 'No Email Available'
  return titleCase(status)
}

function taskMessage(status: string, errorCode: string | null, reason?: string | null): string {
  if (status === 'completed') return 'Moved to Review Queue'
  if (reason) return reason
  if (errorCode === 'duplicate') return 'A draft already exists for this recipient and LinkedIn source.'
  return status === 'processing' ? 'Generating outreach draft' : 'Waiting to be processed'
}

export function ProcessingQueuePage() {
  const [resumes, setResumes] = useState<ResumeMetadata[]>([])
  const [items, setItems] = useState<EmailGenerationInput[]>([blank()])
  const [queue, setQueue] = useState<ProcessingQueue | null>(null)
  const [recentQueues, setRecentQueues] = useState<ProcessingQueue[]>([])
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [submitted, setSubmitted] = useState(false)
  const [editing, setEditing] = useState<string | null>(null)
  const [editText, setEditText] = useState('')
  const [loadError, setLoadError] = useState(false)
  const [deleting, setDeleting] = useState<string | null>(null)
  const [expandedPosts, setExpandedPosts] = useState<Set<string>>(new Set())
  const [expandedQueues, setExpandedQueues] = useState<Set<string>>(new Set())

  useEffect(() => {
    void listResumes().then(setResumes)
    const requestedQueue = new URLSearchParams(window.location.search).get('queueId')
    void listProcessingQueues().then(setRecentQueues).catch(() => setRecentQueues([]))
    void (requestedQueue ? getProcessingQueue(requestedQueue) : getActiveProcessingQueue()).then(setQueue).catch(() => { setQueue(null); setLoadError(Boolean(requestedQueue)) })
  }, [])

  useEffect(() => {
    if (queue?.status !== 'running') return
    const timer = window.setInterval(() => {
      void getProcessingQueue(queue.id).then((updated) => {
        setQueue(updated)
        setRecentQueues((current) => [updated, ...current.filter((item) => item.id !== updated.id)])
      }).catch(() => setMessage('Unable to refresh this queue.'))
    }, 1000)
    return () => window.clearInterval(timer)
  }, [queue?.id, queue?.status])

  function update(index: number, key: keyof EmailGenerationInput, value: string): void {
    setItems((current) => current.map((item, itemIndex) => (
      itemIndex === index ? { ...item, [key]: value } : item
    )))
  }

  async function save(): Promise<void> {
    setSubmitted(true)
    if (!items.every(isValid)) return
    setBusy(true)
    try {
      const payload = items.map((item) => ({
        ...item,
        linkedin_post_url: item.linkedin_post_url.trim(), linkedin_post_text: item.linkedin_post_text.trim(),
        job_description_text: item.job_description_text.trim(), no_job_description: !item.job_description_text.trim(),
      }))
      const created = await createProcessingQueue(payload)
      setQueue(created)
      setRecentQueues((current) => [created, ...current.filter((item) => item.id !== created.id)])
      setMessage('Queue saved. It will not run until you start it.')
    } catch {
      setMessage('Unable to save the queue. Check each item and try again.')
    } finally {
      setBusy(false)
    }
  }

  async function action(fn: (id: string) => Promise<ProcessingQueue>): Promise<void> {
    if (!queue || busy) return
    setBusy(true)
    try {
      const updated = await fn(queue.id)
      setQueue(updated)
      setRecentQueues((current) => [updated, ...current.filter((item) => item.id !== updated.id)])
    } finally {
      setBusy(false)
    }
  }
  async function remove(queueId: string, itemId: string): Promise<void> {
    if (deleting || !window.confirm('Permanently delete this task? Its LinkedIn post can be imported again.')) return
    setDeleting(itemId)
    try {
      await removeProcessingQueueItem(queueId, itemId)
      setQueue((current) => current ? { ...current, total_items: Math.max(0, current.total_items - 1), items: current.items.filter((item) => item.id !== itemId) } : current)
      setMessage('Task permanently deleted. This LinkedIn post can be imported again.')
    } catch { setMessage('Unable to delete this task. It is still in the queue.') } finally { setDeleting(null) }
  }
  async function removeQueue(queueId: string): Promise<void> {
    if (deleting || !window.confirm('Delete this queue and its queue-task history? Outreach items, drafts, and sent emails will be preserved.')) return
    setDeleting(queueId)
    try {
      await deleteProcessingQueue(queueId)
      setRecentQueues((current) => current.filter((item) => item.id !== queueId))
      setQueue((current) => current?.id === queueId ? null : current)
      setMessage('Queue deleted. Outreach items and drafts were preserved.')
    } catch (error: unknown) {
      setMessage(error instanceof Error ? error.message : 'Unable to delete this queue.')
    } finally { setDeleting(null) }
  }
  async function saveJd(queueId: string, itemId: string): Promise<void> {
    const saved = await updateProcessingQueueItem(queueId, itemId, { job_description_text: editText })
    setQueue((current) => current ? { ...current, items: current.items.map((item) => item.id === itemId ? { ...item, ...saved } : item) } : current)
    setEditing(null)
  }
  function toggleQueue(queueId: string): void {
    setExpandedQueues((current) => {
      const next = new Set(current)
      if (next.has(queueId)) next.delete(queueId)
      else next.add(queueId)
      return next
    })
  }
  function queueRunCard(item: ProcessingQueue): ReactNode {
    const completed = item.items.filter((task) => task.status === 'completed' || task.failure_status === 'duplicate' || task.failure_status === 'no_email_available').length
    const failed = item.items.filter((task) => task.status === 'failed' && task.failure_status !== 'duplicate' && task.failure_status !== 'no_email_available').length
    const terminal = completed + failed
    const pending = item.items.filter((task) => task.status === 'pending').length
    const processing = item.items.filter((task) => task.status === 'processing').length
    const progress = item.total_items ? Math.round((terminal / item.total_items) * 100) : 0
    const expanded = expandedQueues.has(item.id)
    return <article className="recent-queue-card" key={item.id}>
      <button type="button" onClick={() => { setQueue(item); toggleQueue(item.id) }}><span>Queue {item.queue_number ?? '—'}</span><strong>{titleCase(item.status)}</strong><small>Created {formatPacificDateTime(item.created_at)}{item.started_at ? ` · Started ${formatPacificDateTime(item.started_at)}` : ''}</small></button>
      <div className="queue-run-counts">{pending > 0 && <span>{pending} pending</span>}{processing > 0 && <span>{processing} processing</span>}<span>{terminal} of {item.total_items} processed</span>{completed > 0 && <span>{completed} completed</span>}{failed > 0 && <span>{failed} failed</span>}</div>
      <div className="queue-progress" aria-label={`${terminal} of ${item.total_items} tasks processed`}><span style={{ width: `${progress}%` }} /></div>
      <div className="queue-run-actions"><button className="queue-text-button" type="button" aria-expanded={expanded} aria-controls={`queue-tasks-${item.id}`} onClick={() => toggleQueue(item.id)}>{expanded ? 'Collapse tasks' : 'Expand tasks'}</button><button className="queue-text-button" type="button" disabled={deleting === item.id || ['draft', 'running', 'paused'].includes(item.status)} onClick={() => void removeQueue(item.id)}>{deleting === item.id ? 'Deleting…' : 'Delete queue'}</button></div>
      {expanded && <ol id={`queue-tasks-${item.id}`} className="queue-run-tasks">{item.items.map((task) => <li key={task.id}><div><strong>{task.source_author_name || 'Source capture'}</strong><span className={`queue-badge queue-badge--${task.status}`}>{taskLabel(task.status, task.error_code)}</span></div>{task.source_linkedin_post_url && <a href={task.source_linkedin_post_url} target="_blank" rel="noreferrer">Source URL ↗</a>}<p>{taskMessage(task.status, task.error_code, task.failure_reason)}</p><small>Updated {task.updated_at || 'recently'}</small>{task.status === 'completed' && <a href="/review-queue">View in Review Queue</a>}{task.status === 'failed' && <a href="/failed-tasks">View in Failed Tasks</a>}</li>)}</ol>}
    </article>
  }

  if (loadError) return <main className="processing-queue-page"><div className="processing-queue-container"><h1>Processing Queue</h1><p role="alert">The existing item could not be loaded.</p><a className="queue-button queue-button--primary" href="/processing-queue">Return to the Processing Queue</a></div></main>

  if (queue && ['draft', 'running', 'paused'].includes(queue.status)) {
    const pendingItems = queue.items.filter((item) => item.status === 'pending').length
    const processingItems = queue.items.filter((item) => item.status === 'processing').length
    const failedItems = queue.items.filter((item) => item.status === 'failed').length
    return <main className="processing-queue-page">
      <div className="processing-queue-container">
        <header className="processing-queue-header">
          <p className="queue-eyebrow">Queue workspace</p>
          <h1>Processing Queue</h1>
          <p>Review each captured outreach task before starting the queue.</p>
        </header>
        <section className="queue-overview" aria-label="Queue summary" aria-live="polite">
          <div><span className="queue-overview__label">Queue status</span><strong>{titleCase(queue.status)}</strong></div>
          <div><strong>{pendingItems}</strong><span>Pending</span></div>
          <div><strong>{processingItems}</strong><span>Processing</span></div>
          <div><strong>{failedItems}</strong><span>Failed</span></div>
        </section>
        {recentQueues.filter((item) => item.id !== queue.id).length > 0 && <section className="recent-queues" aria-label="Other queues"><h2>Other Queues</h2><div>{recentQueues.filter((item) => item.id !== queue.id).map(queueRunCard)}</div></section>}
        <section className="queue-status-panel" aria-label="Queue tasks">
          <ol className="queue-status-list">
            {queue.items.map((item) => {
              const postText = item.source_linkedin_post_text || 'No LinkedIn post text captured.'
              const isExpanded = expandedPosts.has(item.id)
              const isLongPost = postText.length > 280
              const postPreview = isExpanded || !isLongPost ? postText : `${postText.slice(0, 280).trimEnd()}…`
              const hasJobDescription = Boolean(item.source_job_description_text)
              return <li className="queue-task-card" key={item.id}>
                <header className="queue-task-card__header">
                  <div><span className="queue-task-card__number">Item {item.position + 1}</span><h2>{item.source_author_name || 'Source capture'}</h2><p>Captured from the supplied source URL</p></div>
                  <span className={`queue-badge queue-badge--${item.status}`}>{titleCase(item.status)}</span>
                </header>
                {item.error_code && <p className="queue-task-card__error">{item.error_code}</p>}
                <section className="queue-task-card__details" aria-label="Captured LinkedIn details">
                  <span>Captured details</span>
                  <div className="queue-link-list">
                    {item.source_linkedin_post_url && <a href={item.source_linkedin_post_url} target="_blank" rel="noreferrer">Source URL <span aria-hidden="true">↗</span></a>}
                    {item.source_author_profile_url && <a href={item.source_author_profile_url} target="_blank" rel="noreferrer">Author Profile <span aria-hidden="true">↗</span></a>}
                    {!item.source_linkedin_post_url && !item.source_author_profile_url && <span>No source links captured</span>}
                  </div>
                </section>
                <section className="queue-task-card__section">
                  <h3>LinkedIn Post Text (Optional)</h3><p className="queue-post-preview">{postPreview}</p>
                  {isLongPost && <button className="queue-text-button" type="button" aria-expanded={isExpanded} onClick={() => setExpandedPosts((current) => { const next = new Set(current); if (next.has(item.id)) next.delete(item.id); else next.add(item.id); return next })}>{isExpanded ? 'Show less' : 'Show full post'}</button>}
                </section>
                <section className={`queue-task-card__section queue-job-description${hasJobDescription ? '' : ' queue-job-description--missing'}`}>
                  <div className="queue-section-heading"><h3>Job Description</h3>{item.source_job_description_url && <a href={item.source_job_description_url} target="_blank" rel="noreferrer">View source <span aria-hidden="true">↗</span></a>}</div>
                  {editing === item.id ? <div className="queue-jd-editor"><textarea aria-label="Job description text" value={editText} onChange={(event) => setEditText(event.target.value)} /><div><button className="queue-button queue-button--primary" type="button" onClick={() => void saveJd(queue.id, item.id)}>Save job description</button><button className="queue-button queue-button--secondary" type="button" onClick={() => setEditing(null)}>Cancel</button></div></div> : <><p>{item.source_job_description_text || 'No job description captured'}</p>{item.status !== 'processing' && <button className="queue-button queue-button--secondary queue-jd-action" type="button" onClick={() => { setEditing(item.id); setEditText(item.source_job_description_text ?? '') }}>{hasJobDescription ? 'Edit Job Description' : 'Add Job Description'}</button>}</>}
                </section>
                {item.status !== 'processing' && <footer className="queue-task-card__actions"><button className="queue-button queue-button--danger" type="button" disabled={deleting === item.id} onClick={() => void remove(queue.id, item.id)}>{deleting === item.id ? 'Deleting…' : 'Delete task'}</button></footer>}
              </li>
            })}
          </ol>
          {message && <p className="queue-message" role="status">{message}</p>}
          <div className="queue-actions" aria-label="Queue controls">
            {queue.status === 'draft' && <button className="queue-button queue-button--primary" disabled={busy || queue.total_items === 0} onClick={() => void action(startProcessingQueue)}>Start Queue</button>}
            {queue.status === 'running' && <button className="queue-button queue-button--secondary" disabled={busy} onClick={() => void action(pauseProcessingQueue)}>Pause Queue</button>}
            {queue.status === 'paused' && <button className="queue-button queue-button--primary" disabled={busy} onClick={() => void action(resumeProcessingQueue)}>Resume Queue</button>}
            <button className="queue-button queue-button--secondary" type="button" onClick={() => setQueue(null)}>+ Start New Queue</button>
          </div>
        </section>
      </div>
    </main>
  }

  if (queue) {
    return <main className="processing-queue-page"><div className="processing-queue-container">
      <header className="processing-queue-header"><h1>Processing Queue</h1><p>The previous queue has finished.</p></header>
      <section className="queue-status-panel" aria-live="polite"><p>Queue status: <strong>{titleCase(queue.status)}</strong></p><p>{queue.completed_items} completed · {queue.failed_items} failed</p><ol className="queue-status-list">{queue.items.map((item) => <li key={item.id}><span>Item {item.position + 1} · {titleCase(item.status)}</span><button type="button" disabled={deleting === item.id} onClick={() => void remove(queue.id, item.id)}>{deleting === item.id ? 'Deleting…' : 'Delete'}</button></li>)}</ol>{message && <p className="queue-message" role="status">{message}</p>}<button className="queue-button queue-button--primary" type="button" onClick={() => { setQueue(null); setMessage('Create a new queue below.') }}>Create New Queue</button></section>
    </div></main>
  }

  const reachedMaximum = items.length === 10
  const canCreate = items.every(isValid) && !busy
  return <main className="processing-queue-page">
    <div className="processing-queue-container">
      {recentQueues.length > 0 ? <section className="recent-queues" aria-label="Recent queues"><h2>Recent Queues</h2><div>{recentQueues.map(queueRunCard)}</div></section> : <p className="queue-empty-state">No queues yet. Create a queue to begin processing outreach tasks.</p>}
      <header className="processing-queue-header"><h1>Create New Queue</h1><p>Add up to 10 outreach items. Nothing will process until you create the queue and click Start Queue.</p></header>
      <div className="queue-builder">
        {items.map((item, index) => {
          const errors = {
            resume: submitted ? fieldError(item, 'resume_id') : null,
            url: submitted ? fieldError(item, 'linkedin_post_url') : null,
            recipient: submitted ? fieldError(item, 'recipient_to') : null,
          }
          return <section className="queue-item-card" key={index} aria-labelledby={`queue-item-${index}`}>
            <header className="queue-item-card__header"><h2 id={`queue-item-${index}`}>Item {index + 1}</h2>{items.length > 1 && <button className="queue-remove" type="button" aria-label={`Remove item ${index + 1}`} onClick={() => setItems((current) => current.filter((_, itemIndex) => itemIndex !== index))}>Remove</button>}</header>
            <div className="queue-item-card__grid">
              <div className="queue-field"><label htmlFor={`resume-${index}`}>Resume <span aria-hidden="true">*</span></label><select id={`resume-${index}`} value={item.resume_id} aria-invalid={Boolean(errors.resume)} aria-describedby={errors.resume ? `resume-error-${index}` : undefined} onBlur={() => setSubmitted(true)} onChange={(event) => update(index, 'resume_id', event.target.value)}><option value="">Select resume</option>{resumes.map((resume) => <option key={resume.id} value={resume.id}>{resume.name}</option>)}</select>{errors.resume && <p id={`resume-error-${index}`} className="queue-field-error">{errors.resume}</p>}</div>
              <div className="queue-field"><label htmlFor={`recipient-${index}`}>Recipient email <span aria-hidden="true">*</span></label><input id={`recipient-${index}`} type="email" value={item.recipient_to} aria-invalid={Boolean(errors.recipient)} aria-describedby={errors.recipient ? `recipient-error-${index}` : undefined} onBlur={() => setSubmitted(true)} onChange={(event) => update(index, 'recipient_to', event.target.value)} />{errors.recipient && <p id={`recipient-error-${index}`} className="queue-field-error">{errors.recipient}</p>}</div>
              <div className="queue-field"><label htmlFor={`linkedin-url-${index}`}>LinkedIn Post URL / JD URL <span aria-hidden="true">*</span></label><input aria-describedby={errors.url ? `linkedin-url-error-${index}` : `linkedin-url-help-${index}`} id={`linkedin-url-${index}`} placeholder="Paste a LinkedIn post URL, job URL, or JD URL" type="url" value={item.linkedin_post_url ?? ''} aria-invalid={Boolean(errors.url)} onBlur={() => setSubmitted(true)} onChange={(event) => update(index, 'linkedin_post_url', event.target.value)} />{errors.url ? <p id={`linkedin-url-error-${index}`} className="queue-field-error">{errors.url}</p> : <small id={`linkedin-url-help-${index}`}>Required. This may be a LinkedIn post, LinkedIn job, ATS job, or external job-description URL.</small>}</div>
              <div className="queue-field queue-field--full"><label htmlFor={`linkedin-${index}`}>LinkedIn Post Text (Optional)</label><textarea id={`linkedin-${index}`} value={item.linkedin_post_text} onChange={(event) => update(index, 'linkedin_post_text', event.target.value)} /><small>Paste the visible post text when available. The task can still be created without it.</small></div>
              <div className="queue-field queue-field--full"><label htmlFor={`job-description-${index}`}>Job description <span className="queue-optional">Optional</span></label><textarea id={`job-description-${index}`} value={item.job_description_text} onChange={(event) => update(index, 'job_description_text', event.target.value)} /></div>
            </div>
          </section>
        })}
      </div>
      <div className="queue-builder-controls">
        <button className="queue-button queue-button--secondary" type="button" disabled={reachedMaximum} onClick={() => setItems((current) => [...current, blank()])}>+ Add another item</button>
        <p className="queue-count">{items.length} of 10 items</p>
        {reachedMaximum && <p className="queue-maximum" role="status">Maximum of 10 items reached</p>}
        {message && <p className="queue-message" role="alert">{message}</p>}
        <button className="queue-button queue-button--primary" type="button" disabled={!canCreate} onClick={() => void save()}>Create Queue</button>
      </div>
    </div>
  </main>
}
