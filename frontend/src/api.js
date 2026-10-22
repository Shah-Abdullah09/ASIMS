const TOKEN_KEY = 'asims_tokens'

export function loadTokens() {
  try {
    return JSON.parse(localStorage.getItem(TOKEN_KEY)) || null
  } catch {
    return null
  }
}

export function saveTokens(tokens) {
  if (tokens) localStorage.setItem(TOKEN_KEY, JSON.stringify(tokens))
  else localStorage.removeItem(TOKEN_KEY)
}

// Turn a DRF error body into one readable line
export function errorMessage(body) {
  if (!body) return 'Something went wrong. Please try again.'
  if (typeof body === 'string') return body
  if (body.detail) return body.detail
  return Object.entries(body)
    .map(([field, msgs]) => `${field}: ${[].concat(msgs).join(' ')}`)
    .join(' | ')
}

// Keeps the server's structured errors (per field, per table row) next to the readable message
export class ApiError extends Error {
  constructor(status, data) {
    super(errorMessage(data))
    this.status = status
    this.data = data
  }
}

export async function api(path, { method = 'GET', body, auth = true } = {}) {
  const headers = { 'Content-Type': 'application/json' }
  const tokens = loadTokens()
  if (auth && tokens?.access) headers.Authorization = `Bearer ${tokens.access}`

  const res = await fetch(`/api/v1${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  })
  const data = await res.json().catch(() => null)
  if (!res.ok) throw new ApiError(res.status, data)
  return data
}

function authHeaders() {
  const tokens = loadTokens()
  return tokens?.access ? { Authorization: `Bearer ${tokens.access}` } : {}
}

/** Send a file (multipart). The browser sets the multipart Content-Type itself. */
export async function apiUpload(path, formData, { method = 'POST' } = {}) {
  const res = await fetch(`/api/v1${path}`, { method, headers: authHeaders(), body: formData })
  const data = await res.json().catch(() => null)
  if (!res.ok) throw new ApiError(res.status, data)
  return data
}

/** Open a protected file in a new tab. Files have no public link, so fetch it with the login token first. */
export async function openProtectedFile(path) {
  const url = path.startsWith('/api/v1') ? path : `/api/v1${path}`
  const res = await fetch(url, { headers: authHeaders() })
  if (!res.ok) throw new ApiError(res.status, await res.json().catch(() => null))
  const objectUrl = URL.createObjectURL(await res.blob())
  const link = document.createElement('a')
  link.href = objectUrl
  link.target = '_blank'
  link.rel = 'noopener'
  link.click()
  setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000)
}
