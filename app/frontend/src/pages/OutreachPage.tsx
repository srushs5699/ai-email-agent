import { useEffect, useRef, useState } from 'react'

import { approveDraft, createDraft, getLatestDraft, sendDraft, updateDraft } from '../api/drafts'
import { authorizeGmail, createGmailDraft, getGmailStatus, syncGmailDraft, type GmailStatus } from '../api/gmail'

import {
  generateEmail,
  type EmailGenerationInput,
  type GeneratedEmail,
} from '../api/emailGeneration'
import { listResumes, type ResumeMetadata } from '../api/resumes'
import { getSelectedResumeId, setSelectedResumeId } from '../lib/selectedResume'
import { parseLinkedInImport } from '../lib/linkedinImport'
import './OutreachPage.css'

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

function sourceUrlError(value: string): string | null {
  const normalized = value.trim()
  if (!normalized) return 'LinkedIn Post URL / JD URL is required.'
  try {
    const url = new URL(normalized)
    if (!['http:', 'https:'].includes(url.protocol)) return 'Only HTTP and HTTPS URLs are allowed.'
  } catch { return 'Enter a valid HTTP or HTTPS LinkedIn post, job, or JD URL.' }
  return null
}

interface OutreachForm extends Omit<EmailGenerationInput, 'linkedin_post_url'> {
  recipient_cc: string
  recipient_name: string
  company_name: string
  linkedin_source_url: string
  author_profile_url: string
}

const initialForm: OutreachForm = {
  resume_id: '',
  linkedin_post_text: '',
  job_description_text: '',
  no_job_description: false,
  recipient_to: '',
  recipient_cc: '',
  recipient_name: '',
  company_name: '',
  linkedin_source_url: '',
  author_profile_url: '',
}

function buildFullEmail(form: OutreachForm, email: GeneratedEmail): string {
  const recipients = [`To: ${form.recipient_to}`]
  if (form.recipient_cc) {
    recipients.push(`CC: ${form.recipient_cc}`)
  }
  return `${recipients.join('\n')}\nSubject: ${email.subject}\n\n${email.body}`
}

export function OutreachPage() {
  const [resumes, setResumes] = useState<ResumeMetadata[]>([])
  const [form, setForm] = useState<OutreachForm>({
    ...initialForm,
    resume_id: getSelectedResumeId() ?? '',
  })
  const [generatedEmail, setGeneratedEmail] = useState<GeneratedEmail | null>(null)
  const [isGenerating, setIsGenerating] = useState(false)
  const [errorMessage, setErrorMessage] = useState('')
  const [activeDraftId, setActiveDraftId] = useState<string | null>(null)
  const [saveStatus, setSaveStatus] = useState<'Saving…' | 'Saved' | 'Save failed' | null>(null)
  const [gmailStatus, setGmailStatus] = useState<GmailStatus | null>(null)
  const [gmailDraftId, setGmailDraftId] = useState<string | null>(null)
  const [gmailSyncStatus, setGmailSyncStatus] = useState<string>('not_created')
  const [gmailPending, setGmailPending] = useState(false)
  const [gmailError, setGmailError] = useState('')
  const [approvalStatus, setApprovalStatus] = useState<'pending' | 'approved'>('pending')
  const [sendStatus, setSendStatus] = useState<'not_sent' | 'sending' | 'failed' | 'sent'>('not_sent')
  const [sentAt, setSentAt] = useState<string | null>(null)
  const [sendError, setSendError] = useState('')
  const [importStatus, setImportStatus] = useState('')
  const syncVersion = useRef(0)
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const saveVersion = useRef(0)
  const savedContent = useRef<string | null>(null)
  const latestContent = useRef('')
  const skipRecovery = useRef(false)
  const hasUserInput = useRef(false)

  const currentContent = generatedEmail
    ? `${form.resume_id}\u0000${form.recipient_to}\u0000${form.recipient_cc}\u0000${generatedEmail.subject}\u0000${generatedEmail.body}`
    : ''

  useEffect(() => {
    void getGmailStatus().then(setGmailStatus).catch(() => setGmailStatus(null))
    const params = new URLSearchParams(window.location.search)
    if (params.has('code') || params.has('state') || params.has('error')) {
      window.history.replaceState({}, '', window.location.pathname)
    }
  }, [])

  useEffect(() => {
    function applyImport(rawPayload: unknown): void {
      const imported = parseLinkedInImport(rawPayload)
      if (!imported) { setImportStatus('LinkedIn import could not be read safely. You can continue with manual entry.'); return }
      hasUserInput.current = true
      setForm((current) => ({
        ...current,
        linkedin_source_url: imported.sourceUrl,
        author_profile_url: imported.authorProfileUrl ?? current.author_profile_url,
        linkedin_post_text: imported.postText ?? current.linkedin_post_text,
        job_description_text: imported.jobDescriptionText ?? current.job_description_text,
        recipient_name: imported.authorName ?? current.recipient_name,
      }))
      setImportStatus('LinkedIn details were imported. Review and edit them before generating an email.')
    }
    function receive(event: MessageEvent): void {
      if (event.origin !== window.location.origin || event.source !== window || event.data?.type !== 'AI_EMAIL_AGENT_LINKEDIN_IMPORT') return
      applyImport(event.data.payload)
    }
    window.addEventListener('message', receive)
    if (new URLSearchParams(window.location.search).get('extensionImport') === '1') {
      window.postMessage({ type: 'AI_EMAIL_AGENT_REQUEST_LINKEDIN_IMPORT' }, window.location.origin)
    }
    return () => window.removeEventListener('message', receive)
  }, [])

  useEffect(() => {
    latestContent.current = currentContent
  }, [currentContent])

  useEffect(() => {
    void listResumes().then(async (loadedResumes) => {
        setResumes(loadedResumes)
        try {
          const draft = await getLatestDraft()
          if (skipRecovery.current || hasUserInput.current) return
          const hasResume = Boolean(draft.resume_id) && loadedResumes.some(
            (resume) => resume.id === draft.resume_id,
          )
          setForm({
            resume_id: hasResume && draft.resume_id ? draft.resume_id : '',
            linkedin_post_text: draft.linkedin_post_text,
            job_description_text: draft.job_description_text,
            no_job_description: draft.no_job_description,
            recipient_to: draft.recipient_to,
            recipient_cc: draft.recipient_cc ?? '',
            recipient_name: draft.recipient_name ?? '',
            company_name: draft.company_name ?? '',
            linkedin_source_url: '',
            author_profile_url: '',
          })
          if (hasResume && draft.resume_id) setSelectedResumeId(draft.resume_id)
          setGeneratedEmail({ subject: draft.subject, body: draft.body })
          setActiveDraftId(draft.id)
          setGmailDraftId(draft.gmail_draft_id)
          setGmailSyncStatus(draft.gmail_sync_status)
          setApprovalStatus(draft.approval_status === 'approved' ? 'approved' : 'pending')
          setSendStatus(draft.send_status ?? 'not_sent')
          setSentAt(draft.sent_at ?? null)
          savedContent.current = `${draft.resume_id ?? ''}\u0000${draft.recipient_to}\u0000${draft.recipient_cc ?? ''}\u0000${draft.subject}\u0000${draft.body}`
          setSaveStatus('Saved')
        } catch {
          setForm((currentForm) => {
            if (currentForm.resume_id || !loadedResumes[0]) return currentForm
            setSelectedResumeId(loadedResumes[0].id)
            return { ...currentForm, resume_id: loadedResumes[0].id }
          })
        }
      })
      .catch(() => {
        setErrorMessage('Unable to load resumes. Return to the Resume Library and try again.')
      })
  }, [])

  function updateForm<Key extends keyof OutreachForm>(
    key: Key,
    value: OutreachForm[Key],
  ): void {
    hasUserInput.current = true
    if (['resume_id', 'recipient_to', 'recipient_cc'].includes(key)) setApprovalStatus('pending')
    setForm((currentForm) => ({ ...currentForm, [key]: value }))
  }

  function validateForm(): string | null {
    if (!form.resume_id) {
      return 'Select a resume before generating an email.'
    }
    if (!form.recipient_to.trim()) return 'Recipient email is required.'
    if (!EMAIL_PATTERN.test(form.recipient_to.trim())) {
      return 'Enter a valid recipient email address.'
    }
    const urlError = sourceUrlError(form.linkedin_source_url)
    if (urlError) return urlError
    if (form.recipient_cc && !EMAIL_PATTERN.test(form.recipient_cc.trim())) {
      return 'Enter a valid CC email address.'
    }
    return null
  }

  async function handleGenerate(): Promise<void> {
    const validationError = validateForm()
    if (validationError) {
      setErrorMessage(validationError)
      return
    }

    setErrorMessage('')
    setIsGenerating(true)
    try {
      const email = await generateEmail({
        ...form,
        linkedin_post_url: form.linkedin_source_url.trim(),
        linkedin_post_text: form.linkedin_post_text.trim(),
        job_description_text: form.job_description_text.trim(),
        recipient_to: form.recipient_to.trim(),
        recipient_cc: form.recipient_cc.trim() || undefined,
        recipient_name: form.recipient_name.trim() || undefined,
        company_name: form.company_name.trim() || undefined,
      })
      setGeneratedEmail(email)
      if (activeDraftId) {
        await updateDraft(activeDraftId, {
          subject: email.subject,
          body: email.body,
          recipient_to: form.recipient_to.trim(),
          recipient_cc: form.recipient_cc.trim() || undefined,
        })
      } else {
        const draft = await createDraft({
          ...form,
          recipient_to: form.recipient_to.trim(),
          recipient_cc: form.recipient_cc.trim() || undefined,
          recipient_name: form.recipient_name.trim() || undefined,
          company_name: form.company_name.trim() || undefined,
          subject: email.subject,
          body: email.body,
        })
        setActiveDraftId(draft.id)
        setGmailDraftId(draft.gmail_draft_id)
        setGmailSyncStatus(draft.gmail_sync_status)
      }
      savedContent.current = `${form.recipient_to}\u0000${form.recipient_cc}\u0000${email.subject}\u0000${email.body}`
      setSaveStatus('Saved')
    } catch {
      setErrorMessage('Unable to generate an email right now. Please try again.')
    } finally {
      setIsGenerating(false)
    }
  }

  function updateGeneratedEmail(key: keyof GeneratedEmail, value: string): void {
    hasUserInput.current = true
    setApprovalStatus('pending')
    setGeneratedEmail((currentEmail) =>
      currentEmail ? { ...currentEmail, [key]: value } : null,
    )
  }

  useEffect(() => {
    if (!activeDraftId || !generatedEmail || currentContent === savedContent.current) return
    if (saveTimer.current) clearTimeout(saveTimer.current)
    const requestVersion = ++saveVersion.current
    setSaveStatus('Saving…')
    saveTimer.current = setTimeout(() => {
      void updateDraft(activeDraftId, {
        subject: generatedEmail.subject,
        body: generatedEmail.body,
          recipient_to: form.recipient_to.trim(),
          recipient_cc: form.recipient_cc.trim() || undefined,
          resume_id: form.resume_id,
      })
        .then((draft) => {
          if (requestVersion === saveVersion.current && currentContent === latestContent.current) {
            savedContent.current = currentContent
            setSaveStatus('Saved')
            setGmailDraftId(draft.gmail_draft_id)
            setGmailSyncStatus(draft.gmail_sync_status)
            setApprovalStatus(draft.approval_status === 'approved' ? 'approved' : 'pending')
            if (draft.gmail_draft_id) void syncExistingDraft(activeDraftId)
          }
        })
        .catch(() => {
          if (requestVersion === saveVersion.current) setSaveStatus('Save failed')
        })
    }, 800)
    return () => {
      if (saveTimer.current) clearTimeout(saveTimer.current)
    }
  }, [activeDraftId, currentContent, form.recipient_cc, form.recipient_to, generatedEmail])

  async function syncExistingDraft(draftId: string): Promise<void> {
    const version = ++syncVersion.current
    setGmailPending(true)
    setGmailSyncStatus('syncing')
    setGmailError('')
    try {
      const result = await syncGmailDraft(draftId)
      if (version === syncVersion.current) {
        setGmailDraftId(result.gmail_draft_id)
        setGmailSyncStatus(result.sync_status)
      }
    } catch {
      if (version === syncVersion.current) {
        setGmailSyncStatus('sync_failed')
        setGmailError('Gmail sync failed. Your website draft is still saved.')
      }
    } finally {
      if (version === syncVersion.current) setGmailPending(false)
    }
  }

  async function connectGmail(): Promise<void> {
    try {
      const result = await authorizeGmail()
      window.location.assign(result.authorization_url)
    } catch {
      setGmailError('Unable to start Gmail connection.')
    }
  }

  async function createDraftInGmail(): Promise<void> {
    if (!activeDraftId || gmailPending) return
    setGmailPending(true)
    setGmailSyncStatus('creating')
    setGmailError('')
    try {
      const result = await createGmailDraft(activeDraftId)
      setGmailDraftId(result.gmail_draft_id)
      setGmailSyncStatus(result.sync_status)
    } catch {
      setGmailSyncStatus('sync_failed')
      setGmailError('Unable to create a Gmail draft. Your website draft is still saved.')
    } finally {
      setGmailPending(false)
    }
  }

  async function copyText(text: string): Promise<void> {
    try {
      await navigator.clipboard.writeText(text)
    } catch {
      setErrorMessage('Copy failed. Select the text and copy it manually.')
    }
  }

  function validateRecipients(): string | null {
    const validate = (value: string, required: boolean): boolean => {
      if (!value.trim()) return !required
      const values = value.split(/[,;\n]/)
      return values.every((part) => Boolean(part.trim()) && EMAIL_PATTERN.test(part.trim()))
    }
    if (!validate(form.recipient_to, true)) return 'Enter valid To recipient email addresses.'
    if (!validate(form.recipient_cc, false)) return 'Enter valid CC recipient email addresses.'
    return null
  }

  async function handleApprove(): Promise<void> {
    if (!activeDraftId) return
    const validation = validateRecipients()
    if (validation) { setSendError(validation); return }
    setSendError('')
    try {
      await approveDraft(activeDraftId)
      setApprovalStatus('approved')
    } catch {
      setSendError('Approval requires a saved, synchronized Gmail draft with valid recipients.')
    }
  }

  async function handleSend(): Promise<void> {
    if (!activeDraftId || approvalStatus !== 'approved' || sendStatus === 'sending') return
    const validation = validateRecipients()
    if (validation) { setSendError(validation); return }
    setSendStatus('sending'); setSendError('')
    try {
      const result = await sendDraft(activeDraftId)
      setSendStatus('sent'); setSentAt(result.sent_at)
    } catch {
      setSendStatus('failed'); setSendError('Email was not sent. You can safely retry after resolving any Gmail issue.')
    }
  }

  function startOver(): void {
    skipRecovery.current = true
    if (saveTimer.current) clearTimeout(saveTimer.current)
    saveVersion.current += 1
    savedContent.current = null
    setActiveDraftId(null)
    setGeneratedEmail(null)
    setForm(initialForm)
    setSelectedResumeId('')
    setSaveStatus(null)
    setGmailDraftId(null)
    setGmailSyncStatus('not_created')
    setGmailError('')
    setApprovalStatus('pending')
    setSendStatus('not_sent')
    setSentAt(null)
    setSendError('')
    setErrorMessage('')
  }

  return (
    <main className="outreach-page">
      <div className="outreach-container">
        <header className="outreach-page__header">
          <h1>Compose outreach</h1>
          <p>Create a concise email, then copy it into Gmail.</p>
        </header>

        <section aria-labelledby="outreach-details-heading" className="outreach-panel">
          <h2 id="outreach-details-heading">Outreach details</h2>
          <div className="outreach-fields">
            <div className="outreach-field">
              <label htmlFor="resume">Resume</label>
              <select
                id="resume"
                onChange={(event) => {
                  setSelectedResumeId(event.target.value)
                  updateForm('resume_id', event.target.value)
                }}
                value={form.resume_id}
              >
                <option value="">Select a resume</option>
                {resumes.map((resume) => (
                  <option key={resume.id} value={resume.id}>
                    {resume.name}
                  </option>
                ))}
              </select>
            </div>

            <div className="outreach-field">
              <label htmlFor="linkedin-source-url">LinkedIn Post URL / JD URL <span aria-hidden="true">*</span></label>
              <input aria-describedby="linkedin-source-url-help" id="linkedin-source-url" onChange={(event) => updateForm('linkedin_source_url', event.target.value)} placeholder="Paste a LinkedIn post URL, job URL, or JD URL" type="url" value={form.linkedin_source_url} />
              <small id="linkedin-source-url-help">Required. This may be a LinkedIn post, LinkedIn job, ATS job, or external job-description URL.</small>
            </div>
            <div className="outreach-field">
              <label htmlFor="linkedin-post">LinkedIn Post Text (Optional)</label>
              <textarea
                aria-describedby="linkedin-post-help"
                id="linkedin-post"
                onChange={(event) => updateForm('linkedin_post_text', event.target.value)}
                value={form.linkedin_post_text}
              />
              <small id="linkedin-post-help">Paste the visible post text when available. The task can still be created without it.</small>
            </div>

            <div className="outreach-field">
              <div className="outreach-field__label-row">
                <label htmlFor="job-description">Job description text</label>
                <label className="outreach-checkbox">
                  <input
                    checked={form.no_job_description}
                    onChange={(event) =>
                      updateForm('no_job_description', event.target.checked)
                    }
                    type="checkbox"
                  />
                  No job description available
                </label>
              </div>
              <textarea
                disabled={form.no_job_description}
                id="job-description"
                onChange={(event) =>
                  updateForm('job_description_text', event.target.value)
                }
                value={form.job_description_text}
              />
            </div>

            <div className="outreach-contact-grid">
              <div className="outreach-field">
                <label htmlFor="recipient-to">To</label>
                <input
                  id="recipient-to"
                  onChange={(event) => updateForm('recipient_to', event.target.value)}
                  type="email"
                  value={form.recipient_to}
                />
              </div>
              <div className="outreach-field">
                <label htmlFor="recipient-cc">CC (optional)</label>
                <input
                  id="recipient-cc"
                  onChange={(event) => updateForm('recipient_cc', event.target.value)}
                  type="email"
                  value={form.recipient_cc}
                />
              </div>
              <div className="outreach-field">
                <label htmlFor="recipient-name">Recipient name (optional)</label>
                <input
                  id="recipient-name"
                  onChange={(event) => updateForm('recipient_name', event.target.value)}
                  value={form.recipient_name}
                />
              </div>
              <div className="outreach-field">
                <label htmlFor="author-profile-url">Author profile URL (optional)</label>
                <input id="author-profile-url" onChange={(event) => updateForm('author_profile_url', event.target.value)} type="url" value={form.author_profile_url} />
              </div>
              <div className="outreach-field">
                <label htmlFor="company-name">Company name (optional)</label>
                <input
                  id="company-name"
                  onChange={(event) => updateForm('company_name', event.target.value)}
                  value={form.company_name}
                />
              </div>
            </div>
          </div>

          <div className="outreach-primary-action">
            <button
              disabled={isGenerating}
              onClick={() => void handleGenerate()}
              type="button"
            >
              {isGenerating ? 'Generating…' : 'Generate Email'}
            </button>
          </div>
          {importStatus && <p aria-live="polite">{importStatus}</p>}
          {errorMessage && <p role="alert">{errorMessage}</p>}
        </section>

        {generatedEmail && (
          <section aria-label="Generated email" className="outreach-panel outreach-review">
          <h2>Review email</h2>
            <div className="outreach-review__recipient-grid">
              <div className="outreach-field">
                <label htmlFor="review-to">To</label>
                <input
                  id="review-to"
                  onChange={(event) => updateForm('recipient_to', event.target.value)}
                  value={form.recipient_to}
                />
              </div>
              <div className="outreach-field">
                <label htmlFor="review-cc">CC</label>
                <input
                  id="review-cc"
                  onChange={(event) => updateForm('recipient_cc', event.target.value)}
                  value={form.recipient_cc}
                />
              </div>
            </div>
            <div className="outreach-field">
              <label htmlFor="email-subject">Subject</label>
              <input
                id="email-subject"
                onChange={(event) =>
                  updateGeneratedEmail('subject', event.target.value)
                }
                value={generatedEmail.subject}
              />
            </div>
            <div className="outreach-field">
              <label htmlFor="email-body">Email body</label>
              <textarea
                id="email-body"
                onChange={(event) =>
                  updateGeneratedEmail('body', event.target.value)
                }
                value={generatedEmail.body}
              />
            </div>
            <div aria-label="Copy email actions" className="outreach-action-row">
              <button onClick={() => void copyText(generatedEmail.subject)} type="button">
                Copy Subject
              </button>
              <button onClick={() => void copyText(generatedEmail.body)} type="button">
                Copy Body
              </button>
              <button
                onClick={() => void copyText(buildFullEmail(form, generatedEmail))}
                type="button"
              >
                Copy Full Email
              </button>
            </div>
            {saveStatus && <p aria-live="polite">{saveStatus}</p>}
            <section aria-label="Gmail draft status" className="outreach-gmail-status">
              {!gmailStatus?.configured && <p>Gmail integration is unavailable.</p>}
              {gmailStatus?.configured && !gmailStatus.connected && (
                <><p>Gmail is not connected.</p><button onClick={() => void connectGmail()} type="button">Connect Gmail</button></>
              )}
              {gmailStatus?.connected && <p>Gmail connected{gmailStatus.google_email ? `: ${gmailStatus.google_email}` : ''}</p>}
              {gmailStatus?.connected && !gmailDraftId && (
                <button disabled={gmailPending} onClick={() => void createDraftInGmail()} type="button">{gmailPending ? 'Creating Gmail draft…' : 'Create Gmail Draft'}</button>
              )}
              {gmailDraftId && <p>{gmailSyncStatus === 'syncing' ? 'Syncing to Gmail…' : gmailSyncStatus === 'synced' ? 'Synced to Gmail' : gmailSyncStatus === 'authorization_required' ? 'Gmail authorization required' : gmailSyncStatus === 'sync_failed' ? 'Gmail sync failed' : 'Gmail draft created'}</p>}
              {gmailDraftId && gmailSyncStatus === 'sync_failed' && <button disabled={gmailPending} onClick={() => void syncExistingDraft(activeDraftId!)} type="button">Retry Gmail Sync</button>}
              {gmailError && <p role="alert">{gmailError}</p>}
            </section>
            <section aria-label="Email approval and sending" className="outreach-gmail-status">
              <p>Approval applies only to the current To, CC, subject, body, and selected resume.</p>
              {sendStatus === 'sent' ? (
                <p aria-live="polite">Sent{sentAt ? ` at ${new Date(sentAt).toLocaleString()}` : ''}.</p>
              ) : (
                <>
                  <p aria-live="polite">{sendStatus === 'sending' ? 'Sending' : approvalStatus === 'approved' ? 'Approved — ready to send' : sendStatus === 'failed' ? 'Failed — ready to retry' : 'Ready to approve'}</p>
                  <button disabled={!activeDraftId || gmailPending || gmailSyncStatus !== 'synced' || approvalStatus === 'approved' || sendStatus === 'sending'} onClick={() => void handleApprove()} type="button">Approve Email</button>
                  <button disabled={!activeDraftId || gmailPending || gmailSyncStatus !== 'synced' || approvalStatus !== 'approved' || sendStatus === 'sending'} onClick={() => void handleSend()} type="button">{sendStatus === 'sending' ? 'Sending…' : 'Send Email'}</button>
                </>
              )}
              {sendError && <p role="alert">{sendError}</p>}
            </section>
            <div aria-label="Review email actions" className="outreach-secondary-actions">
              <button onClick={startOver} type="button">
                Start Over
              </button>
              <button onClick={() => void handleGenerate()} type="button">
                Generate Again
              </button>
            </div>
          </section>
        )}
      </div>
    </main>
  )
}
