import type { LinkedInCapturePayload, ExtractionResult } from '../shared/types'
import { validatePayload } from '../shared/validation'
import { requestCapture } from '../communication/capture'

const status = document.querySelector<HTMLParagraphElement>('#status')!
const form = document.querySelector<HTMLFormElement>('#capture-form')!
const jobForm = document.querySelector<HTMLFormElement>('#job-form')!
const warnings = document.querySelector<HTMLDivElement>('#warnings')!
const field = (id: string) => document.querySelector<HTMLInputElement | HTMLTextAreaElement>(`#${id}`)!
let payload: LinkedInCapturePayload | null = null

function displayJob(result: { text: string | null; url: string | null; source: 'visible_page' | 'unavailable'; warning: string | null }) {
  form.hidden = true; jobForm.hidden = false
  field('jobDescriptionTextReview').value = result.text ?? ''
  document.querySelector<HTMLDivElement>('#job-warnings')!.textContent = result.warning ?? 'Extracted from content visible in this browser tab. Review or edit it before continuing.'
  status.textContent = result.text ? 'Review the visible job description before attaching it.' : 'The job description could not be extracted automatically. You can paste it manually or continue without it.'
}

function readForm(): LinkedInCapturePayload | null {
  if (!payload) return null
  const jobDescriptionText = field('jobDescriptionText').value.trim() || undefined
  return validatePayload({ ...payload, sourceUrl: field('sourceUrl').value, authorName: field('authorName').value || undefined, authorProfileUrl: field('authorProfileUrl').value || undefined, postText: field('postText').value || undefined, jobDescriptionUrl: field('jobDescriptionUrl').value || undefined, jobDescriptionText, jobDescriptionSource: jobDescriptionText ? 'manual' : 'unavailable' })
}
function display(result: ExtractionResult) {
  payload = { ...result.payload, importId: crypto.randomUUID() }
  ;(['sourceUrl', 'authorName', 'authorProfileUrl', 'postText', 'jobDescriptionUrl', 'jobDescriptionText'] as const).forEach((key) => { field(key).value = payload![key] ?? '' })
  warnings.textContent = [...payload.warnings, ...(payload.jobDescriptionText ? [] : ['The job description could not be extracted automatically. You can paste it manually or continue without it.'])].join(' ')
  status.textContent = result.supported ? 'Review the capture before sending it to the app.' : 'Unsupported page: the source URL can still be imported for manual entry.'
  form.hidden = false
}
chrome.tabs.query({ active: true, currentWindow: true }, ([tab]: [{ id?: number }]) => {
  void requestCapture(chrome, tab?.id).then((outcome) => {
    if ('result' in outcome) display(outcome.result)
    else chrome.runtime.sendMessage({ type: 'EXTRACT_JOB_FROM_TAB', tabId: tab?.id }, (response: { result?: { text: string | null; url: string | null; source: 'visible_page' | 'unavailable'; warning: string | null }; error?: string }) => response?.result ? displayJob(response.result) : (status.textContent = response?.error ?? outcome.message))
  })
})
form.addEventListener('submit', (event) => { event.preventDefault(); const edited = readForm(); if (!edited) { status.textContent = 'Enter a valid LinkedIn post URL.'; return }; const button = document.querySelector<HTMLButtonElement>('#send')!; button.disabled = true; status.textContent = 'Opening authenticated import…'; chrome.runtime.sendMessage({ type: 'OPEN_IMPORT', payload: edited }, (response: { ok?: boolean; error?: string }) => { button.disabled = false; status.textContent = response?.ok ? 'Import is being confirmed by the application…' : response?.error ?? 'Sending failed. Your reviewed values are still available.' }) })
document.querySelector('#manual')!.addEventListener('click', () => { const edited = readForm(); if (edited) chrome.runtime.sendMessage({ type: 'OPEN_MANUAL', payload: edited }); else chrome.runtime.sendMessage({ type: 'OPEN_MANUAL', payload: { version: 1, sourceUrl: 'https://www.linkedin.com/', jobDescriptionSource: 'unavailable', warnings: ['Manual entry selected.'], capturedAt: new Date().toISOString() } }) })
document.querySelector('#capture-job')!.addEventListener('click', () => { const edited = readForm(); if (!edited?.jobDescriptionUrl) { status.textContent = 'Enter a valid job-description URL first.'; return }; status.textContent = 'Capturing visible job details…'; chrome.tabs.query({ active: true, currentWindow: true }, ([tab]: [{ id?: number }]) => chrome.runtime.sendMessage({ type: 'CAPTURE_JOB_WORKFLOW', payload: edited, originalTabId: tab?.id }, (response: { result?: { text: string | null; linkedinJobUrl?: string; officialJobUrl?: string; warning?: string }; error?: string }) => { if (response?.result) { payload = { ...edited, linkedinJobUrl: response.result.linkedinJobUrl, officialJobUrl: response.result.officialJobUrl, jobDescriptionText: response.result.text ?? undefined, jobDescriptionSource: response.result.text ? 'visible_page' : 'unavailable', jobDescriptionCaptureStatus: response.result.text ? 'captured' : 'unavailable', jobDescriptionCaptureWarning: response.result.warning }; display({ supported: true, fields: {} as ExtractionResult['fields'], payload }); } else status.textContent = response?.error ?? 'Unable to capture visible job details.' })) })
function attachJobDescription(text: string, source: 'visible_page' | 'manual' | 'unavailable') { chrome.runtime.sendMessage({ type: 'ATTACH_JOB_DESCRIPTION', text, source }, (response: { ok?: boolean; error?: string }) => { status.textContent = response?.ok ? 'Opening authenticated import…' : response?.error ?? 'Unable to attach the reviewed text.' }) }
jobForm.addEventListener('submit', (event) => { event.preventDefault(); const text = field('jobDescriptionTextReview').value.trim(); attachJobDescription(text, text ? 'visible_page' : 'unavailable') })
document.querySelector('#continue-without-job')!.addEventListener('click', () => attachJobDescription('', 'unavailable'))
document.querySelector('#close-job')!.addEventListener('click', () => window.close())
document.querySelector('#close')!.addEventListener('click', () => window.close())
