/** What the student may change: everything in a draft; only what the Placement Office reopened when returned.
The server's `unlocked` lists are the authority (null = everything). */
export const sectionOpen = (app, key) => app.is_editable || Boolean(app.unlocked?.sections?.includes(key))
export const slotOpen = (app, slot) => app.is_editable || Boolean(app.unlocked?.slots?.includes(slot))
export const isReturned = (app) => app.status === 'returned'

/** Placement's reason for the latest return. */
export function returnReason(app) {
  const last = [...(app.status_history || [])].reverse().find((h) => h.action === 'return')
  return last?.remarks || app.review_remarks || ''
}

/** The approval chain in order, for the student's progress line. */
export const CHAIN = ['placement_verification', 'dac_review', 'awaiting_forwarding', 'director_review',
  'registrar_review', 'vc_review', 'awaiting_fee_adjustment']
