/**
 * Shared Vite env helpers for tool apps.
 */

/** @param {string} [defaultBase] */
export function getApiBase(defaultBase = '/api') {
  const base = import.meta.env.VITE_API_BASE
  const raw = typeof base === 'string' && base.length > 0 ? base : defaultBase
  return raw.replace(/\/$/, '')
}

/**
 * Join API base with a path segment (e.g. apiUrl('chat') → /api/chat).
 * @param {string} path
 * @param {string} [defaultBase]
 */
export function apiUrl(path, defaultBase = '/api') {
  const segment = path.startsWith('/') ? path.slice(1) : path
  return `${getApiBase(defaultBase)}/${segment}`
}

/** @param {number} [defaultMs] */
export function getPollIntervalMs(defaultMs = 1200) {
  const raw = import.meta.env.VITE_POLL_INTERVAL_MS
  const ms = Number(raw)
  return Number.isFinite(ms) && ms > 0 ? ms : defaultMs
}
