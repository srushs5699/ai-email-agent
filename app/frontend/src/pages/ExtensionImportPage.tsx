import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router'

import { importExtensionCapture } from '../api/extensionImport'
import { ApiRequestError, MissingSessionError } from '../api/client'
import type { LinkedInImportPayload } from '../lib/linkedinImport'
import { parseLinkedInImport } from '../lib/linkedinImport'

type View = 'waiting' | 'importing' | 'manual' | 'error'
const clearExtensionCapture = () => window.postMessage({ type: 'AI_EMAIL_AGENT_CLEAR_LINKEDIN_IMPORT' }, window.location.origin)

/** Authenticated bridge: it navigates only after a queue/item identifier is returned. */
export function ExtensionImportPage() {
  const navigate = useNavigate()
  const [view, setView] = useState<View>('waiting')
  const [message, setMessage] = useState('Waiting for the reviewed LinkedIn capture…')
  const [capture, setCapture] = useState<LinkedInImportPayload | null>(null)

  useEffect(() => {
    let handled = false
    const receive = (event: MessageEvent): void => {
      if (handled || event.origin !== window.location.origin || event.source !== window || event.data?.type !== 'AI_EMAIL_AGENT_LINKEDIN_IMPORT') return
      const next = parseLinkedInImport(event.data.payload)
      if (!next || !next.sourceUrl || !next.authorName || !next.postText) {
        setCapture(next); setView('manual'); setMessage('Manual information is required before this capture can be imported.')
        return
      }
      handled = true
      setCapture(next); setView('importing'); setMessage('Importing capture…')
      const idempotencyKey = next.importId ?? crypto.randomUUID()
      void importExtensionCapture({ version: 1, linkedin_post_url: next.sourceUrl, author_name: next.authorName, author_profile_url: next.authorProfileUrl, linkedin_post_text: next.postText, job_description_url: next.jobDescriptionUrl, job_description_text: next.jobDescriptionText, job_description_source: next.jobDescriptionSource ?? 'unavailable', idempotency_key: idempotencyKey, captured_at: next.capturedAt })
        .then((result) => {
          if ((result.outcome === 'queued' || result.outcome === 'existing') && result.queue_id) {
            clearExtensionCapture()
            setMessage(result.outcome === 'queued' ? 'Added to Processing Queue.' : 'Existing item found in Processing Queue.')
            navigate(`/processing-queue?queueId=${encodeURIComponent(result.queue_id)}&itemId=${encodeURIComponent(result.outreach_item_id ?? '')}`, { replace: true })
            return
          }
          if (result.outcome === 'validation_required') { setView('manual'); setMessage(result.reason ?? 'Manual information is required before this capture can be imported.'); return }
          clearExtensionCapture(); setView('error'); setMessage(result.reason ?? 'Import failed. No item was added to the Processing Queue.')
        })
        .catch((error: unknown) => { clearExtensionCapture(); setView('error'); setMessage(error instanceof MissingSessionError ? 'Sign in to the application, then retry Send to App.' : error instanceof ApiRequestError && error.message ? error.message : 'Import failed. No item was added to the Processing Queue.') })
    }
    window.addEventListener('message', receive)
    window.postMessage({ type: 'AI_EMAIL_AGENT_REQUEST_LINKEDIN_IMPORT' }, window.location.origin)
    return () => window.removeEventListener('message', receive)
  }, [navigate])

  return <main className="processing-queue-page"><div className="processing-queue-container"><h1>Import LinkedIn capture</h1><p role="status">{message}</p>{view === 'manual' && <Link className="queue-button queue-button--primary" to="/outreach?extensionImport=1" state={{ extensionCapture: capture }}>Open Manual Entry</Link>}{view === 'error' && <button className="queue-button queue-button--secondary" type="button" onClick={() => { clearExtensionCapture(); navigate('/', { replace: true }) }}>Cancel</button>}</div></main>
}
