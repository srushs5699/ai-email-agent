import { describe, expect, it, vi } from 'vitest'
import { resolveApplicationOrigin } from '../src/communication/application-origin'
import { requestCapture } from '../src/communication/capture'

const result = { supported: true, fields: {}, payload: { version: 1, sourceUrl: 'https://www.linkedin.com/feed/update/urn:li:activity:1', warnings: [], capturedAt: '2026-07-19T00:00:00Z' } } as never
describe('extension communication safety', () => {
  it('uses the documented local origin when configuration is missing and rejects invalid values', () => { expect(resolveApplicationOrigin(undefined).origin).toBe('http://localhost:5173'); expect(resolveApplicationOrigin('chrome-extension://invalid/').error).toMatch(/http or https|invalid/) })
  it('does not send a message when the active tab URL/id is unavailable', async () => { const sendMessage = vi.fn(); await expect(requestCapture({ runtime: {}, tabs: { sendMessage } }, undefined)).resolves.toMatchObject({ error: 'permission-error' }); expect(sendMessage).not.toHaveBeenCalled() })
  it('reports unavailable content scripts and consumes runtime.lastError', async () => { const api = { runtime: { lastError: { message: 'Could not establish connection. Receiving end does not exist.' } }, tabs: { sendMessage: (_id: number, _message: unknown, callback: () => void) => callback() } }; await expect(requestCapture(api, 1)).resolves.toMatchObject({ error: 'content-script-unavailable' }) })
  it('reports closed message ports instead of leaving loading active', async () => { const api = { runtime: { lastError: { message: 'The message port closed before a response was received.' } }, tabs: { sendMessage: (_id: number, _message: unknown, callback: () => void) => callback() } }; await expect(requestCapture(api, 1)).resolves.toMatchObject({ error: 'content-script-unavailable' }) })
  it('times out a capture request', async () => { vi.useFakeTimers(); const promise = requestCapture({ runtime: {}, tabs: { sendMessage: () => undefined } }, 1, 20); await vi.advanceTimersByTimeAsync(20); await expect(promise).resolves.toMatchObject({ error: 'timeout-error' }); vi.useRealTimers() })
  it('returns valid captures without a network request', async () => { const sendMessage = vi.fn((_id, _message, callback) => callback(result)); await expect(requestCapture({ runtime: {}, tabs: { sendMessage } }, 1)).resolves.toMatchObject({ result }); expect(sendMessage).toHaveBeenCalledOnce() })
})
