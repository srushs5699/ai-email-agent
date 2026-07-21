import { extractJobDescription } from '../extraction/job-description'
chrome.runtime.onMessage.addListener((message: { type?: string }, _sender: unknown, respond: (response: unknown) => void) => { if (message.type === 'EXTRACT_JOB_DESCRIPTION') respond(extractJobDescription(document)) })
