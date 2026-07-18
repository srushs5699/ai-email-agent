import { useEffect, useState } from 'react'

import {
  generateEmail,
  type EmailGenerationInput,
  type GeneratedEmail,
} from '../api/emailGeneration'
import { listResumes, type ResumeMetadata } from '../api/resumes'
import { getSelectedResumeId, setSelectedResumeId } from '../lib/selectedResume'
import './OutreachPage.css'

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

interface OutreachForm extends EmailGenerationInput {
  recipient_cc: string
  recipient_name: string
  company_name: string
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

  useEffect(() => {
    void listResumes()
      .then((loadedResumes) => {
        setResumes(loadedResumes)
        setForm((currentForm) => {
          if (currentForm.resume_id || !loadedResumes[0]) {
            return currentForm
          }
          setSelectedResumeId(loadedResumes[0].id)
          return { ...currentForm, resume_id: loadedResumes[0].id }
        })
      })
      .catch(() => {
        setErrorMessage('Unable to load resumes. Return to the Resume Library and try again.')
      })
  }, [])

  function updateForm<Key extends keyof OutreachForm>(
    key: Key,
    value: OutreachForm[Key],
  ): void {
    setForm((currentForm) => ({ ...currentForm, [key]: value }))
  }

  function validateForm(): string | null {
    if (!form.resume_id) {
      return 'Select a resume before generating an email.'
    }
    if (!form.linkedin_post_text.trim() && !form.job_description_text.trim()) {
      return 'Add LinkedIn post text or a job description.'
    }
    if (!form.job_description_text.trim() && !form.no_job_description) {
      return 'Select “No job description available” when no job description is provided.'
    }
    if (!EMAIL_PATTERN.test(form.recipient_to.trim())) {
      return 'Enter a valid recipient email address.'
    }
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
        recipient_to: form.recipient_to.trim(),
        recipient_cc: form.recipient_cc.trim() || undefined,
        recipient_name: form.recipient_name.trim() || undefined,
        company_name: form.company_name.trim() || undefined,
      })
      setGeneratedEmail(email)
    } catch {
      setErrorMessage('Unable to generate an email right now. Please try again.')
    } finally {
      setIsGenerating(false)
    }
  }

  async function copyText(text: string): Promise<void> {
    try {
      await navigator.clipboard.writeText(text)
    } catch {
      setErrorMessage('Copy failed. Select the text and copy it manually.')
    }
  }

  function startOver(): void {
    setGeneratedEmail(null)
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
              <label htmlFor="linkedin-post">LinkedIn post text</label>
              <textarea
                id="linkedin-post"
                onChange={(event) => updateForm('linkedin_post_text', event.target.value)}
                value={form.linkedin_post_text}
              />
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
                  setGeneratedEmail((currentEmail) =>
                    currentEmail ? { ...currentEmail, subject: event.target.value } : null,
                  )
                }
                value={generatedEmail.subject}
              />
            </div>
            <div className="outreach-field">
              <label htmlFor="email-body">Email body</label>
              <textarea
                id="email-body"
                onChange={(event) =>
                  setGeneratedEmail((currentEmail) =>
                    currentEmail ? { ...currentEmail, body: event.target.value } : null,
                  )
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
