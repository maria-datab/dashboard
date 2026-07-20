/**
 * Frontend settings — re-export shared helpers with boxout defaults.
 * Prefer VITE_BOXOUT_API_BASE when embedded in the dashboard shell.
 */
import {
  apiUrl as sharedApiUrl,
  getApiBase as sharedGetApiBase,
  getPollIntervalMs,
} from '@dashboard/shared/env.js'

export { getPollIntervalMs }

export function getApiBase() {
  const specific = import.meta.env.VITE_BOXOUT_API_BASE
  if (typeof specific === 'string' && specific.trim()) {
    return specific.trim().replace(/\/$/, '')
  }
  return sharedGetApiBase('/api/app')
}

export function apiUrl(path) {
  const segment = path.startsWith('/') ? path.slice(1) : path
  return `${getApiBase()}/${segment}`
}
