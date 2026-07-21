const LOCAL_DEFAULT = 'http://localhost:5173'

export function resolveApplicationOrigin(configured: unknown): { origin?: string; error?: string } {
  const value = configured === undefined || configured === null || configured === '' ? LOCAL_DEFAULT : configured
  if (typeof value !== 'string') return { error: 'Application origin configuration must be a URL.' }
  try {
    const url = new URL(value)
    if (!['http:', 'https:'].includes(url.protocol)) return { error: 'Application origin must use http or https.' }
    return { origin: url.origin }
  } catch { return { error: 'Application origin is invalid. Set appOrigin to a valid local application URL.' } }
}
