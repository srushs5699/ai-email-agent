import { useEffect, useState } from 'react'

import {
  approveDraft, listReviewDrafts, regenerateDraft, rejectDraft,
  sendDraft, updateDraft, type Draft,
} from '../api/drafts'
import { createGmailDraft, syncGmailDraft } from '../api/gmail'
import { deleteOutreachItem } from '../api/outreachItems'
import { normalizeReviewDraft } from '../lib/reviewDraftFormatting'
import './ReviewQueuePage.css'

const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
type BusyAction = 'saving' | 'regenerating' | 'sending' | 'deleting' | null

function valid(draft: Draft): boolean {
  return Boolean(draft.subject.trim() && draft.body.trim() && emailPattern.test(draft.recipient_to.trim()) && (!draft.recipient_cc || emailPattern.test(draft.recipient_cc.trim())))
}

function formatDraftDate(value: string): string | null {
  if (!value) return null
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? null : date.toLocaleString()
}

export function ReviewQueuePage() {
  const [drafts, setDrafts] = useState<Draft[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState<Record<string, BusyAction>>({})
  const [sendErrors, setSendErrors] = useState<Record<string, string>>({})
  const [message, setMessage] = useState('')

  useEffect(() => {
    void listReviewDrafts()
      .then(({ drafts: loaded }) => setDrafts(loaded.map(normalizeReviewDraft)))
      .catch(() => setError('Unable to load the Review Queue.'))
      .finally(() => setLoading(false))
  }, [])
  function edit(id: string, key: 'recipient_to' | 'recipient_cc' | 'subject' | 'body', value: string): void {
    setDrafts((current) => current.map((draft) => draft.id === id ? { ...draft, [key]: value } : draft))
  }
  async function save(draft: Draft): Promise<void> {
    const normalized = normalizeReviewDraft(draft)
    if (!valid(normalized)) { setError('Enter valid recipients, a subject, and an email body before saving.'); return }
    setBusy((current) => ({ ...current, [draft.id]: 'saving' }))
    try { const updated = await updateDraft(draft.id, { recipient_to: normalized.recipient_to, recipient_cc: normalized.recipient_cc || undefined, subject: normalized.subject, body: normalized.body }); setDrafts((current) => current.map((item) => item.id === draft.id ? normalizeReviewDraft(updated) : item)) } catch { setError('Unable to save this draft.') } finally { setBusy((current) => ({ ...current, [draft.id]: null })) }
  }
  async function regenerate(draft: Draft): Promise<void> {
    setBusy((current) => ({ ...current, [draft.id]: 'regenerating' })); setError('')
    try { const updated = await regenerateDraft(draft.id); setDrafts((current) => current.map((item) => item.id === draft.id ? normalizeReviewDraft(updated) : item)) } catch { setError('Unable to regenerate this draft. You can try again.') } finally { setBusy((current) => ({ ...current, [draft.id]: null })) }
  }
  async function remove(draft: Draft, action: 'reject' | 'delete'): Promise<void> {
    if (!window.confirm(`Are you sure you want to ${action} this draft?`)) return
    setBusy((current) => ({ ...current, [draft.id]: action === 'delete' ? 'deleting' : 'saving' }))
    try { if (action === 'reject') await rejectDraft(draft.id); else await deleteOutreachItem(draft.outreach_item_id); setDrafts((current) => current.filter((item) => item.id !== draft.id)); if (action === 'delete') setMessage('Task permanently deleted. This LinkedIn post can be imported again.') } catch { setError(`Unable to ${action} this draft.`) } finally { setBusy((current) => ({ ...current, [draft.id]: null })) }
  }
  async function approveAndSend(draft: Draft): Promise<void> {
    const normalized = normalizeReviewDraft(draft)
    if (!valid(normalized)) { setError('Enter valid recipients, a subject, and an email body before sending.'); return }
    setBusy((current) => ({ ...current, [draft.id]: 'sending' })); setError('')
    setSendErrors((current) => ({ ...current, [draft.id]: '' }))
    try {
      const saved = await updateDraft(draft.id, { recipient_to: normalized.recipient_to, recipient_cc: normalized.recipient_cc || undefined, subject: normalized.subject, body: normalized.body })
      if (!saved.gmail_draft_id) await createGmailDraft(draft.id)
      else await syncGmailDraft(draft.id)
      await approveDraft(draft.id)
      await sendDraft(draft.id)
      setDrafts((current) => current.filter((item) => item.id !== draft.id))
    } catch { setSendErrors((current) => ({ ...current, [draft.id]: 'Email sending failed. Your draft was preserved and can be retried.' })) } finally { setBusy((current) => ({ ...current, [draft.id]: null })) }
  }
  return <main className="review-queue-page"><div className="review-queue-container"><header><h1>Review Queue</h1><p>Review, edit, or explicitly send saved outreach drafts.</p></header>{loading && <p aria-live="polite">Loading drafts…</p>}{error && <p className="alert" role="alert">{error}</p>}{message && <p role="status">{message}</p>}{!loading && !drafts.length && <section className="review-empty empty-state"><h2>No drafts waiting for review</h2><p>Generated drafts will appear here after processing.</p><a className="button button--primary" href="/outreach">Compose outreach</a></section>}<div className="review-list">{drafts.map((draft) => { const action = busy[draft.id]; const disabled = Boolean(action); const updatedAt = formatDraftDate(draft.updated_at); return <article className="review-card" key={draft.id}><header><div><h2>{draft.recipient_to || 'Draft ready for review'}</h2><span className="review-badge">{draft.status.replaceAll('_', ' ')}</span></div><p>Resume: {draft.resume_id ?? 'Unavailable'}{updatedAt ? ` · Updated ${updatedAt}` : ''}</p></header>{sendErrors[draft.id] && <p className="review-send-error" role="alert"><strong>Send failed:</strong> {sendErrors[draft.id]}</p>}<div className="review-fields"><label htmlFor={`to-${draft.id}`}>To<input id={`to-${draft.id}`} type="email" value={draft.recipient_to} disabled={disabled} onChange={(event) => edit(draft.id, 'recipient_to', event.target.value)} /></label><label htmlFor={`cc-${draft.id}`}>CC <span>Optional</span><input id={`cc-${draft.id}`} type="email" value={draft.recipient_cc ?? ''} disabled={disabled} onChange={(event) => edit(draft.id, 'recipient_cc', event.target.value)} /></label><label htmlFor={`subject-${draft.id}`}>Subject<input id={`subject-${draft.id}`} value={draft.subject} disabled={disabled} onChange={(event) => edit(draft.id, 'subject', event.target.value)} /></label><label htmlFor={`body-${draft.id}`}>Email body<textarea id={`body-${draft.id}`} value={draft.body} disabled={disabled} onChange={(event) => edit(draft.id, 'body', event.target.value)} /></label></div><div className="review-actions"><button disabled={disabled} onClick={() => void save(draft)}>{action === 'saving' ? 'Saving…' : 'Save changes'}</button><button disabled={disabled} onClick={() => void regenerate(draft)}>{action === 'regenerating' ? 'Regenerating…' : 'Regenerate'}</button><button disabled={disabled} onClick={() => void remove(draft, 'reject')}>Reject</button><button disabled={disabled} onClick={() => void remove(draft, 'delete')}>{action === 'deleting' ? 'Deleting…' : 'Delete'}</button><button className="review-send" disabled={disabled} onClick={() => void approveAndSend(draft)}>{action === 'sending' ? 'Sending…' : 'Approve and Send'}</button></div></article>})}</div></div></main>
}
