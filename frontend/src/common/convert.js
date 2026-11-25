// Converting between API values and form input values (inputs always hold strings).

export const toInput = (v) => (v === null || v === undefined ? '' : String(v))

// Empty -> null. Anything that is not a number is sent as typed so the server explains the problem.
export const toNumber = (v) => {
  if (v === '' || v === null || v === undefined) return null
  const n = Number(v)
  return Number.isNaN(n) ? v : n
}

export const toBoolInput = (v) => (v === true ? 'yes' : v === false ? 'no' : '')
export const fromBoolInput = (v) => (v === 'yes' ? true : v === 'no' ? false : null)

export const toDate = (v) => (v ? v : null)

// <input type="month"> uses YYYY-MM; the API stores the first day of that month
export const toMonthInput = (v) => (v ? v.slice(0, 7) : '')
export const fromMonthInput = (v) => (v ? `${v}-01` : null)

export const rupees = (n) => `Rs. ${Number(n || 0).toLocaleString('en-PK')}`

/** Pick the error for one field: a list of messages or nothing. */
export function fieldError(errors, name) {
  const e = errors?.[name]
  if (!e) return null
  if (Array.isArray(e)) return e.join(' ')
  if (typeof e === 'string') return e
  return null
}

/** Errors for a table: { rows: {index: {field: [...]}}, list: 'message for the whole table' }. */
export function tableErrors(errors, name) {
  const e = errors?.[name]
  if (!e) return { rows: {}, list: null }
  if (Array.isArray(e)) {
    // a list of messages about the whole table, or (older DRF) one entry per row
    if (e.every((x) => typeof x === 'string')) return { rows: {}, list: e.join(' ') }
    return { rows: Object.fromEntries(e.map((x, i) => [String(i), x])), list: null }
  }
  if (typeof e === 'object') {
    const { non_field_errors: nonField, ...rows } = e
    return { rows, list: nonField ? [].concat(nonField).join(' ') : null }
  }
  return { rows: {}, list: String(e) }
}

/**
 * Keep only rows that have something in them before sending, remembering where each sent row
 * came from so the server's row errors can be shown on the right row.
 */
export function packRows(rows, isEmpty, toApi) {
  const payload = []
  const origin = []
  rows.forEach((row, i) => {
    if (!isEmpty(row)) {
      payload.push(toApi(row))
      origin.push(i)
    }
  })
  return { payload, origin }
}

/** Translate row errors from sent positions back to on-screen positions. */
export function remapRowErrors(errors, name, origin) {
  const e = errors?.[name]
  if (!e || Array.isArray(e) || typeof e !== 'object' || !origin) return errors
  const mapped = {}
  for (const [key, value] of Object.entries(e)) {
    mapped[key === 'non_field_errors' ? key : String(origin[Number(key)] ?? key)] = value
  }
  return { ...errors, [name]: mapped }
}

export const blank = (row, keys) => keys.every((k) => row[k] === '' || row[k] === null || row[k] === undefined)
