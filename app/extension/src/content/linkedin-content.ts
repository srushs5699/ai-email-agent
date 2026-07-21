import { extractLinkedInPost } from '../extraction/extract'

declare global { interface Window { __aiEmailAgentLinkedInListenerRegistered?: boolean } }

export function registerLinkedInMessageListener(): boolean {
  if (typeof chrome === 'undefined' || !chrome.runtime || !chrome.runtime.onMessage) {
    console.warn('LinkedIn content script was loaded outside the Chrome extension isolated world.')
    return false
  }
  if (window.__aiEmailAgentLinkedInListenerRegistered) return true
  window.__aiEmailAgentLinkedInListenerRegistered = true
  chrome.runtime.onMessage.addListener((message: unknown, _sender: unknown, respond: (response: unknown) => void) => {
    if (typeof message === 'object' && message !== null && 'type' in message && (message as { type?: unknown }).type === 'EXTRACT_ACTIVE_POST') respond(extractLinkedInPost(document))
    return false
  })
  return true
}

registerLinkedInMessageListener()
