import type { ExtractionResult } from '../shared/types'

export type CaptureFailure = 'content-script-unavailable' | 'permission-error' | 'extraction-error' | 'timeout-error'
export type CaptureOutcome = { result: ExtractionResult } | { error: CaptureFailure; message: string }

type ChromeMessaging = { runtime: { lastError?: { message?: string } }; tabs: { sendMessage: (tabId: number, message: unknown, callback: (result?: ExtractionResult) => void) => void } }

export function requestCapture(chromeApi: ChromeMessaging, tabId: number | undefined, timeoutMs = 5000): Promise<CaptureOutcome> {
  if (typeof tabId !== 'number' || !Number.isInteger(tabId)) return Promise.resolve({ error: 'permission-error', message: 'No active tab is available.' })
  return new Promise((resolve) => {
    let complete = false
    const finish = (outcome: CaptureOutcome) => { if (!complete) { complete = true; clearTimeout(timer); resolve(outcome) } }
    const timer = setTimeout(() => finish({ error: 'timeout-error', message: 'Capture timed out. Refresh the LinkedIn tab and try again.' }), timeoutMs)
    try {
      chromeApi.tabs.sendMessage(tabId, { type: 'EXTRACT_ACTIVE_POST' }, (result) => {
        const error = chromeApi.runtime.lastError?.message
        if (error) {
          const unavailable = /Receiving end does not exist|message port closed/i.test(error)
          finish({ error: unavailable ? 'content-script-unavailable' : 'permission-error', message: unavailable ? 'LinkedIn capture is unavailable in this tab. Refresh the LinkedIn page, then try again.' : 'Chrome could not access this tab. Check the extension permission and try again.' })
          return
        }
        if (!result?.payload) { finish({ error: 'extraction-error', message: 'LinkedIn details could not be extracted. Use manual entry or try again.' }); return }
        finish({ result })
      })
    } catch {
      finish({ error: 'permission-error', message: 'Chrome could not start capture for this tab.' })
    }
  })
}
