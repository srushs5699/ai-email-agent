import { describe, expect, it, vi } from 'vitest'

describe('LinkedIn content-script registration', () => {
  it('does not throw outside an extension world', async () => {
    const original = (globalThis as { chrome?: unknown }).chrome
    delete (globalThis as { chrome?: unknown }).chrome
    const module = await import('../src/content/linkedin-content')
    expect(module.registerLinkedInMessageListener()).toBe(false)
    ;(globalThis as { chrome?: unknown }).chrome = original
  })
  it('registers once and responds to active-post messages', async () => {
    const listener = vi.fn()
    ;(globalThis as { chrome?: unknown }).chrome = { runtime: { onMessage: { addListener: listener } } }
    window.__aiEmailAgentLinkedInListenerRegistered = undefined
    const module = await import('../src/content/linkedin-content')
    expect(module.registerLinkedInMessageListener()).toBe(true)
    expect(module.registerLinkedInMessageListener()).toBe(true)
    expect(listener).toHaveBeenCalledTimes(1)
  })
})
