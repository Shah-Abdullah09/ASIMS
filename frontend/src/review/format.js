/** One line describing what an application still lacks. */
export function completionText(c) {
  if (c.complete) return 'Complete'
  if (!c.form_submitted) return 'Not submitted'
  const missing = []
  if (!c.scans_uploaded) missing.push('Form 2 scan')
  if (!c.physical_copies_received) missing.push('original')
  return `Missing: ${missing.join(', ')}`
}
