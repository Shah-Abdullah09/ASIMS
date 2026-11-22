// Dates as the screens show them (British order, e.g. 22 Nov 2026).

export const day = (d) => (d ? new Date(d).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }) : '—')
export const when = (d) => new Date(d).toLocaleString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
export const todayIso = () => new Date().toLocaleDateString('en-CA') // YYYY-MM-DD in local time
