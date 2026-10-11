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
  if (!res.ok) throw new Error(errorMessage(data))
  return data
}
