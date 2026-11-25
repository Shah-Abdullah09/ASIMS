// Dates as the screens show them (British order, e.g. 22 Nov 2026).

export const day = (d) => (d ? new Date(d).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }) : '—')
export const when = (d) => new Date(d).toLocaleString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })

// The university's time zone, as on the server (TIME_ZONE): "today" must not depend on the browser's clock setting,
// or a date entered just after midnight in Pakistan would count as the day before.
const UNIVERSITY_TIME_ZONE = 'Asia/Karachi'

/** Today's date in the university's time zone, as YYYY-MM-DD for date inputs. */
export const todayIso = () => new Date().toLocaleDateString('en-CA', { timeZone: UNIVERSITY_TIME_ZONE })
