import { useEffect, useState } from 'react'

import type { EmailGenerationInput } from '../api/emailGeneration'
import {
  createProcessingQueue,
  getActiveProcessingQueue,
  pauseProcessingQueue,
  resumeProcessingQueue,
  startProcessingQueue,
  type ProcessingQueue,
} from '../api/processingQueues'
import { listResumes, type ResumeMetadata } from '../api/resumes'
import './ProcessingQueuePage.css'

const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
const blank = (): EmailGenerationInput => ({
  resume_id: '', linkedin_post_text: '', job_description_text: '',
  no_job_description: false, recipient_to: '', recipient_cc: '',
  recipient_name: '', company_name: '',
})

function fieldError(item: EmailGenerationInput, field: keyof EmailGenerationInput): string | null {
  if (field === 'resume_id' && !item.resume_id) return 'Select a resume.'
  if (field === 'linkedin_post_text' && !item.linkedin_post_text.trim()) return 'LinkedIn post text is required.'
  if (field === 'recipient_to') {
    if (!item.recipient_to.trim()) return 'Recipient email is required.'
    if (!emailPattern.test(item.recipient_to.trim())) return 'Enter a valid email address.'
  }
  return null
}

function isValid(item: EmailGenerationInput): boolean {
  return !fieldError(item, 'resume_id') && !fieldError(item, 'linkedin_post_text') && !fieldError(item, 'recipient_to')
}

function titleCase(value: string): string {
  return value.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
}

export function ProcessingQueuePage() {
  const [resumes, setResumes] = useState<ResumeMetadata[]>([])
  const [items, setItems] = useState<EmailGenerationInput[]>([blank()])
  const [queue, setQueue] = useState<ProcessingQueue | null>(null)
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [submitted, setSubmitted] = useState(false)

  useEffect(() => {
    void listResumes().then(setResumes)
    void getActiveProcessingQueue().then(setQueue).catch(() => undefined)
  }, [])

  useEffect(() => {
    if (queue?.status !== 'running') return
    const timer = window.setInterval(() => {
      void getActiveProcessingQueue().then(setQueue).catch(() => undefined)
    }, 1000)
    return () => window.clearInterval(timer)
  }, [queue?.status])

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
        no_job_description: !item.job_description_text.trim(),
      }))
      setQueue(await createProcessingQueue(payload))
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
      setQueue(await fn(queue.id))
    } finally {
      setBusy(false)
    }
  }

  if (queue) {
    return <main className="processing-queue-page">
      <div className="processing-queue-container">
        <header className="processing-queue-header"><h1>Processing Queue</h1><p>Add up to 10 outreach items. Nothing will process until you create the queue and click Start Queue.</p></header>
        <section className="queue-status-panel" aria-live="polite">
          <p>Queue status: <strong>{titleCase(queue.status)}</strong></p>
          <p>{queue.total_items} {queue.total_items === 1 ? 'item' : 'items'}</p>
          <ol className="queue-status-list">
            {queue.items.map((item) => <li key={item.id}><span>Item {item.position + 1}</span><span className={`queue-badge queue-badge--${item.status}`}>{titleCase(item.status)}</span>{item.error_code && <small>{item.error_code}</small>}</li>)}
          </ol>
          {message && <p className="queue-message" role="status">{message}</p>}
          <div className="queue-actions">
            {queue.status === 'draft' && <button className="queue-button queue-button--primary" disabled={busy || queue.total_items === 0} onClick={() => void action(startProcessingQueue)}>Start Queue</button>}
            {queue.status === 'running' && <button className="queue-button queue-button--secondary" disabled={busy} onClick={() => void action(pauseProcessingQueue)}>Pause Queue</button>}
            {queue.status === 'paused' && <button className="queue-button queue-button--primary" disabled={busy} onClick={() => void action(resumeProcessingQueue)}>Resume Queue</button>}
          </div>
        </section>
      </div>
    </main>
  }

  const reachedMaximum = items.length === 10
  const canCreate = items.every(isValid) && !busy
  return <main className="processing-queue-page">
    <div className="processing-queue-container">
      <header className="processing-queue-header"><h1>Processing Queue</h1><p>Add up to 10 outreach items. Nothing will process until you create the queue and click Start Queue.</p></header>
      <div className="queue-builder">
        {items.map((item, index) => {
          const errors = {
            resume: submitted ? fieldError(item, 'resume_id') : null,
            linkedin: submitted ? fieldError(item, 'linkedin_post_text') : null,
            recipient: submitted ? fieldError(item, 'recipient_to') : null,
          }
          return <section className="queue-item-card" key={index} aria-labelledby={`queue-item-${index}`}>
            <header className="queue-item-card__header"><h2 id={`queue-item-${index}`}>Item {index + 1}</h2>{items.length > 1 && <button className="queue-remove" type="button" aria-label={`Remove item ${index + 1}`} onClick={() => setItems((current) => current.filter((_, itemIndex) => itemIndex !== index))}>Remove</button>}</header>
            <div className="queue-item-card__grid">
              <div className="queue-field"><label htmlFor={`resume-${index}`}>Resume <span aria-hidden="true">*</span></label><select id={`resume-${index}`} value={item.resume_id} aria-invalid={Boolean(errors.resume)} aria-describedby={errors.resume ? `resume-error-${index}` : undefined} onBlur={() => setSubmitted(true)} onChange={(event) => update(index, 'resume_id', event.target.value)}><option value="">Select resume</option>{resumes.map((resume) => <option key={resume.id} value={resume.id}>{resume.name}</option>)}</select>{errors.resume && <p id={`resume-error-${index}`} className="queue-field-error">{errors.resume}</p>}</div>
              <div className="queue-field"><label htmlFor={`recipient-${index}`}>Recipient email <span aria-hidden="true">*</span></label><input id={`recipient-${index}`} type="email" value={item.recipient_to} aria-invalid={Boolean(errors.recipient)} aria-describedby={errors.recipient ? `recipient-error-${index}` : undefined} onBlur={() => setSubmitted(true)} onChange={(event) => update(index, 'recipient_to', event.target.value)} />{errors.recipient && <p id={`recipient-error-${index}`} className="queue-field-error">{errors.recipient}</p>}</div>
              <div className="queue-field queue-field--full"><label htmlFor={`linkedin-${index}`}>LinkedIn post text <span aria-hidden="true">*</span></label><textarea id={`linkedin-${index}`} value={item.linkedin_post_text} aria-invalid={Boolean(errors.linkedin)} aria-describedby={errors.linkedin ? `linkedin-error-${index}` : undefined} onBlur={() => setSubmitted(true)} onChange={(event) => update(index, 'linkedin_post_text', event.target.value)} />{errors.linkedin && <p id={`linkedin-error-${index}`} className="queue-field-error">{errors.linkedin}</p>}</div>
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
