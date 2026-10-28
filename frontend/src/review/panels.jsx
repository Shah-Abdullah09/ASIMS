import { useState } from 'react'
import { api } from '../api.js'
import { FLAG_SECTIONS } from './roles.js'

const when = (d) => new Date(d).toLocaleString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
const todayIso = () => new Date().toLocaleDateString('en-CA') // YYYY-MM-DD in local time
const firstError = (err, key) => {
  const v = err.data?.[key]
  return v ? [].concat(v).join(' ') : ''
}

/** Where a file stands after the Placement Office has looked at it. */
export function ReviewChip({ file }) {
  if (file.review_status === 'verified') return <span className="chip chip-ok">Verified</span>
  if (file.review_status === 'needs_clarification') return <span className="chip chip-warn">Needs clarification</span>
  return <span className="chip">Not reviewed</span>
}

/** Placement marks one file Verified, or Needs clarification with a note the student will see. */
export function FileReview({ appId, file, onChanged }) {
  const [asking, setAsking] = useState(false)
  const [note, setNote] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function send(review_status) {
    setBusy(true)
    setError('')
    try {
      await api(`/scholarships/review/applications/${appId}/documents/${file.id}/review/`,
        { method: 'POST', body: { review_status, note } })
      setAsking(false)
      setNote('')
      await onChanged()
    } catch (err) {
      setError(firstError(err, 'note') || err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="file-review">
      {file.review_status !== 'verified' && (
        <button type="button" className="secondary" disabled={busy} onClick={() => send('verified')}>Verified</button>
      )}
      {!asking ? (
        <button type="button" className="secondary" disabled={busy} onClick={() => setAsking(true)}>Needs clarification</button>
      ) : (
        <span className="inline-form">
          <label className="visually-hidden" htmlFor={`note-${file.id}`}>What is unclear in {file.original_name}?</label>
          <input id={`note-${file.id}`} value={note} maxLength={500} onChange={(e) => setNote(e.target.value)}
            placeholder="What is unclear? The student sees this." />
          <button type="button" disabled={busy} onClick={() => send('needs_clarification')}>Save</button>
          <button type="button" className="secondary" onClick={() => { setAsking(false); setError('') }}>Cancel</button>
        </span>
      )}
      {error && <p className="field-error" role="alert">{error}</p>}
    </div>
  )
}

/** Sections the Placement Office asked the student to correct; open ones can be added and cleared at verification. */
export function FlagsPanel({ app, canEdit, onChanged }) {
  const [section, setSection] = useState(FLAG_SECTIONS[0][0])
  const [note, setNote] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const base = `/scholarships/review/applications/${app.id}/flags/`

  async function call(path, options) {
    setBusy(true)
    setError('')
    try {
      await api(path, options)
      setNote('')
      await onChanged()
    } catch (err) {
      setError(firstError(err, 'note') || firstError(err, 'section') || err.message)
    } finally {
      setBusy(false)
    }
  }

  const flags = app.flags || []
  return (
    <>
      {flags.length === 0 ? <p className="field-hint">No corrections requested.</p> : (
        <ul className="flag-list">
          {flags.map((f) => (
            <li key={f.id} className={f.is_open ? 'flag-open' : 'flag-closed'}>
              <p><strong>{f.section_label}</strong>: {f.note}</p>
              <p className="field-hint">
                {f.flagged_by}, {when(f.flagged_at)}
                {f.is_open ? ' · open' : ` · ${f.resolution === 'resubmitted' ? 'answered by the student' : 'cleared'} ${when(f.resolved_at)}`}
              </p>
              {canEdit && f.is_open && (
                <button type="button" className="secondary" disabled={busy}
                  onClick={() => call(`${base}${f.id}/`, { method: 'DELETE' })}>Clear</button>
              )}
            </li>
          ))}
        </ul>
      )}
      {canEdit && (
        <form className="flag-form" aria-label="Request a correction"
          onSubmit={(e) => { e.preventDefault(); call(base, { method: 'POST', body: { section, note } }) }}>
          <label>
            Section
            <select value={section} onChange={(e) => setSection(e.target.value)}>
              {FLAG_SECTIONS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </label>
          <label className="flag-note">
            What should the student correct?
            <input value={note} maxLength={500} onChange={(e) => setNote(e.target.value)} />
          </label>
          <button type="submit" disabled={busy}>Flag section</button>
        </form>
      )}
      {error && <p className="field-error" role="alert">{error}</p>}
    </>
  )
}

/** The DAC member records the interview before deciding; it can be corrected while the case is at DAC review. */
export function InterviewForm({ app, onSaved }) {
  const [date, setDate] = useState(app.interview_date || todayIso())
  const [remarks, setRemarks] = useState(app.interview_remarks || '')
  const [errors, setErrors] = useState({})
  const [saved, setSaved] = useState(false)
  const [busy, setBusy] = useState(false)

  async function save(e) {
    e.preventDefault()
    setBusy(true)
    setErrors({})
    setSaved(false)
    try {
      const updated = await api(`/scholarships/review/applications/${app.id}/interview/`,
        { method: 'PUT', body: { interview_date: date, interview_remarks: remarks } })
      setSaved(true)
      onSaved(updated)
    } catch (err) {
      setErrors({ date: firstError(err, 'interview_date'), remarks: firstError(err, 'interview_remarks'), detail: err.data?.detail })
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="decision-panel" onSubmit={save} noValidate aria-label="DAC interview">
      <h2>DAC interview</h2>
      <p className="field-hint">Record the interview before shortlisting. These notes are not shown to the student.</p>
      <div className="field">
        <label htmlFor="interview-date">Interview date</label>
        <input id="interview-date" type="date" value={date} max={todayIso()} onChange={(e) => setDate(e.target.value)}
          aria-invalid={errors.date ? true : undefined} />
        {errors.date && <p className="field-error">{errors.date}</p>}
      </div>
      <div className="field">
        <label htmlFor="interview-remarks">Interview remarks</label>
        <textarea id="interview-remarks" rows={4} maxLength={4000} value={remarks} onChange={(e) => setRemarks(e.target.value)}
          aria-invalid={errors.remarks ? true : undefined} />
        {errors.remarks && <p className="field-error">{errors.remarks}</p>}
      </div>
      {errors.detail && <p className="field-error" role="alert">{errors.detail}</p>}
      {saved && <p className="notice-ok" role="status">Interview saved.</p>}
      <button type="submit" disabled={busy}>{app.interview_date ? 'Update interview' : 'Save interview'}</button>
    </form>
  )
}
