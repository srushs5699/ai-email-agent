import type { ExtensionMessage } from '../shared/types'
import { validatePayload } from '../shared/validation'
import { resolveApplicationOrigin } from '../communication/application-origin'
import { classifyJobLink } from '../extraction/job-link'

type Workflow = { id: string; originalTabId?: number; createdTabIds: number[] }
const workflows = new Map<string, Workflow>()
const delay = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms))
async function captureVisibleJob(payload: { linkedinJobUrl?: string; officialJobUrl?: string; jobDescriptionUrl?: string }, originalTabId?: number): Promise<Record<string, unknown>> {
  const url = payload.linkedinJobUrl ?? payload.officialJobUrl ?? payload.jobDescriptionUrl
  const kind = classifyJobLink(url)
  const id = crypto.randomUUID(); const workflow: Workflow = { id, originalTabId, createdTabIds: [] }; workflows.set(id, workflow)
  if (!url || kind === 'missing' || kind === 'unsafe') return { workflowId: id, text: null, source: 'unavailable', warning: 'Job description could not be extracted safely.' }
  try {
    if (kind === 'external_job') {
      const origin = new URL(url).origin + '/*'
      const granted = await chrome.permissions.request({ origins: [origin] })
      if (!granted) return { workflowId: id, text: null, source: 'unavailable', warning: 'Permission to read the official job page was not granted.' }
    }
    const tab = await chrome.tabs.create({ url, active: false }); workflow.createdTabIds.push(tab.id)
    await delay(1500)
    await chrome.scripting.executeScript({ target: { tabId: tab.id }, files: ['content/job-content.js'] })
    const result = await chrome.tabs.sendMessage(tab.id, { type: 'EXTRACT_JOB_DESCRIPTION' })
    return { workflowId: id, ...result, linkedinJobUrl: kind === 'linkedin_job' ? url : payload.linkedinJobUrl, officialJobUrl: kind === 'external_job' ? tab.url : undefined }
  } catch {
    return { workflowId: id, text: null, source: 'unavailable', warning: 'Job page timed out before content loaded', linkedinJobUrl: kind === 'linkedin_job' ? url : payload.linkedinJobUrl, officialJobUrl: kind === 'external_job' ? url : undefined }
  } finally {
    await Promise.all(workflow.createdTabIds.map((tabId) => chrome.tabs.remove(tabId).catch(() => undefined)))
    if (typeof originalTabId === 'number') await chrome.tabs.update(originalTabId, { active: true }).catch(() => undefined)
    workflows.delete(id)
  }
}

async function appOrigin(): Promise<{ origin?: string; error?: string }> {
  const stored = await chrome.storage.local.get('appOrigin')
  return resolveApplicationOrigin(stored.appOrigin)
}

chrome.runtime.onMessage.addListener((message: ExtensionMessage | { type: 'EXTRACT_JOB_FROM_TAB'; tabId?: number }, _sender: unknown, respond: (response: unknown) => void) => {
  if (message.type === 'GET_PENDING_IMPORT') {
    void chrome.storage.session.get('pendingImport').then(({ pendingImport }: { pendingImport?: unknown }) => {
      const payload = validatePayload(pendingImport)
      respond({ payload })
    })
    return true
  }
  if (message.type === 'CLEAR_PENDING_IMPORT') {
    void chrome.storage.session.remove(['pendingImport', 'pendingJobCapture']).then(() => respond({ ok: true }))
    return true
  }
  if (message.type === 'OPEN_JOB_CAPTURE') {
    const payload = validatePayload(message.payload)
    if (!payload?.jobDescriptionUrl) { respond({ ok: false, error: 'A valid job-description URL is required.' }); return }
    void chrome.storage.session.set({ pendingImport: payload, pendingJobCapture: true }).then(() => chrome.tabs.create({ url: payload.jobDescriptionUrl! })).then(() => respond({ ok: true })).catch(() => respond({ ok: false, error: 'The job page could not be opened.' }))
    return true
  }
  if (message.type === 'CAPTURE_JOB_WORKFLOW') {
    const payload = validatePayload(message.payload)
    if (!payload) { respond({ error: 'Invalid capture payload.' }); return }
    void captureVisibleJob(payload, message.originalTabId).then((result) => respond({ result }))
    return true
  }
  if (message.type === 'ATTACH_JOB_DESCRIPTION') {
    void chrome.storage.session.get('pendingImport').then(({ pendingImport }: { pendingImport?: unknown }) => {
      const payload = validatePayload(pendingImport)
      if (!payload) throw new Error('No reviewed capture is available.')
      const text = message.text?.trim() || undefined
      return chrome.storage.session.set({ pendingImport: { ...payload, jobDescriptionText: text, jobDescriptionSource: text ? (message.source === 'manual' ? 'manual' : 'visible_page') : 'unavailable', warnings: text ? payload.warnings : [...payload.warnings, 'The job description could not be extracted automatically. You can paste it manually or continue without it.'] }, pendingJobCapture: false })
    }).then(() => appOrigin()).then((configuration: { origin?: string; error?: string }) => { if (!configuration.origin) throw new Error(configuration.error ?? 'Application origin is not configured.'); return chrome.tabs.create({ url: `${configuration.origin}/extension-import?extensionImport=1` }) }).then(() => respond({ ok: true })).catch((error: unknown) => respond({ ok: false, error: error instanceof Error ? error.message : 'Unable to save job description.' }))
    return true
  }
  if (message.type === 'EXTRACT_JOB_FROM_TAB') {
    if (!message.tabId) { respond({ error: 'No active job page is available.' }); return }
    void chrome.scripting.executeScript({ target: { tabId: message.tabId }, files: ['content/job-content.js'] })
      .then(() => chrome.tabs.sendMessage(message.tabId!, { type: 'EXTRACT_JOB_DESCRIPTION' }))
      .then((result: unknown) => respond({ result }))
      .catch(() => respond({ error: 'Chrome could not read this job page. Open it normally, then try again.' }))
    return true
  }
  if (message.type === 'OPEN_IMPORT' || message.type === 'OPEN_MANUAL') {
    const payload = validatePayload(message.payload)
    if (!payload) { respond({ ok: false, error: 'Invalid capture payload.' }); return }
    // A fresh Send to App replaces every prior capture; no failed/duplicate ID
    // is stored alongside capture data.
    void Promise.all([chrome.storage.session.set({ pendingImport: payload, pendingJobCapture: false }), appOrigin()])
      .then(([, configuration]) => {
        if (!configuration.origin) throw new Error(configuration.error ?? 'Application origin is not configured.')
        // The import route is an authenticated application bridge.  It performs
        // the API request before it navigates to the queue; opening the queue is
        // never treated as a successful import.
        return chrome.tabs.create({ url: `${configuration.origin}/${message.type === 'OPEN_MANUAL' ? 'outreach' : 'extension-import'}?extensionImport=1` })
      })
      .then(() => respond({ ok: true }))
      .catch((error: unknown) => respond({ ok: false, error: error instanceof Error ? error.message : 'Unable to open the application.' }))
    return true
  }
})
