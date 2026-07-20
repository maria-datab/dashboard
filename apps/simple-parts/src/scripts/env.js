/**
 * Frontend settings — re-export shared helpers with simple-parts defaults.
 * Prefer VITE_SIMPLE_PARTS_API_BASE when embedded in the dashboard shell.
 */
import { getApiBase as sharedGetApiBase } from '@dashboard/shared/env.js'

export function getApiBase() {
  const specific = import.meta.env.VITE_SIMPLE_PARTS_API_BASE
  if (typeof specific === 'string' && specific.trim()) {
    return specific.trim().replace(/\/$/, '')
  }
  return sharedGetApiBase('/api')
}

export function apiUrl(path) {
  const segment = path.startsWith('/') ? path.slice(1) : path
  return `${getApiBase()}/${segment}`
}
