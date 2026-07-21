import { validatePayload } from '../shared/validation'

window.addEventListener('message', (event) => {
  if (event.source !== window || event.origin !== window.location.origin || event.data?.type !== 'AI_EMAIL_AGENT_REQUEST_LINKEDIN_IMPORT') return
  chrome.runtime.sendMessage({ type: 'GET_PENDING_IMPORT' }, (response: { payload?: unknown }) => {
    const payload = validatePayload(response?.payload)
    window.postMessage({ type: 'AI_EMAIL_AGENT_LINKEDIN_IMPORT', payload }, window.location.origin)
  })
})

window.addEventListener('message', (event) => {
  if (event.source !== window || event.origin !== window.location.origin || event.data?.type !== 'AI_EMAIL_AGENT_CLEAR_LINKEDIN_IMPORT') return
  chrome.runtime.sendMessage({ type: 'CLEAR_PENDING_IMPORT' })
})
